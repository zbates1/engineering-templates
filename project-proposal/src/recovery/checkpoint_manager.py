"""
Checkpoint manager for processing state persistence and recovery.

This module provides checkpoint functionality for the markdown-to-PDF pipeline,
allowing batch processing to resume from interruption points and maintain
processing state across restarts.
"""

import json
import time
import hashlib
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Union
import logging
import tempfile
import shutil


class CheckpointType(Enum):
    """Types of checkpoints that can be created."""
    BATCH_START = "batch_start"
    FILE_PROCESSED = "file_processed"
    BATCH_COMPLETE = "batch_complete"
    ERROR_STATE = "error_state"
    RECOVERY_POINT = "recovery_point"


class ProcessingStatus(Enum):
    """Status of file processing in checkpoint."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FileProcessingState:
    """State of individual file processing."""
    file_path: Path
    status: ProcessingStatus
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    processing_time: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    output_path: Optional[Path] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_path": str(self.file_path),
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "output_path": str(self.output_path) if self.output_path else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileProcessingState':
        """Create from dictionary for deserialization."""
        return cls(
            file_path=Path(data["file_path"]),
            status=ProcessingStatus(data["status"]),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            processing_time=data.get("processing_time", 0.0),
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
            output_path=Path(data["output_path"]) if data.get("output_path") else None
        )


@dataclass
class BatchState:
    """Complete state of batch processing operation."""
    batch_id: str
    input_directory: Path
    output_directory: Path
    total_files: int
    processed_files: int
    failed_files: int
    skipped_files: int
    start_time: float
    last_updated: float
    file_states: Dict[str, FileProcessingState]
    configuration: Dict[str, Any]
    checkpoint_type: CheckpointType = CheckpointType.BATCH_START
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "batch_id": self.batch_id,
            "input_directory": str(self.input_directory),
            "output_directory": str(self.output_directory),
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "skipped_files": self.skipped_files,
            "start_time": self.start_time,
            "last_updated": self.last_updated,
            "file_states": {key: state.to_dict() for key, state in self.file_states.items()},
            "configuration": self.configuration,
            "checkpoint_type": self.checkpoint_type.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchState':
        """Create from dictionary for deserialization."""
        file_states = {
            key: FileProcessingState.from_dict(state_data)
            for key, state_data in data["file_states"].items()
        }
        
        return cls(
            batch_id=data["batch_id"],
            input_directory=Path(data["input_directory"]),
            output_directory=Path(data["output_directory"]),
            total_files=data["total_files"],
            processed_files=data["processed_files"],
            failed_files=data["failed_files"],
            skipped_files=data["skipped_files"],
            start_time=data["start_time"],
            last_updated=data["last_updated"],
            file_states=file_states,
            configuration=data["configuration"],
            checkpoint_type=CheckpointType(data["checkpoint_type"])
        )


@dataclass
class CheckpointId:
    """Identifier for a checkpoint."""
    batch_id: str
    timestamp: float
    checkpoint_type: CheckpointType
    
    def __str__(self) -> str:
        """String representation for filename generation."""
        return f"{self.batch_id}_{self.checkpoint_type.value}_{int(self.timestamp)}"


class CheckpointManager:
    """
    Manages processing state persistence and recovery through checkpoints.
    
    This class provides checkpoint functionality for the pipeline including:
    - Saving processing state at configurable intervals
    - Restoring state from checkpoints after interruption
    - Managing checkpoint lifecycle and cleanup
    - Supporting different checkpoint types for various recovery scenarios
    """
    
    def __init__(self, checkpoint_dir: Optional[Path] = None, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.checkpoint_dir = checkpoint_dir or Path(tempfile.gettempdir()) / "pipeline_checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Checkpoint configuration
        self.auto_save_interval = 30.0  # seconds
        self.max_checkpoint_age = 24 * 3600  # 24 hours in seconds
        self.max_checkpoints_per_batch = 10
        
        # Runtime state
        self.current_checkpoints: Dict[str, List[CheckpointId]] = {}
        self.last_auto_save: Dict[str, float] = {}
    
    def save_checkpoint(self, batch_state: BatchState) -> CheckpointId:
        """
        Save a checkpoint of the current batch processing state.
        
        Args:
            batch_state: Current state of batch processing to save
            
        Returns:
            CheckpointId for the saved checkpoint
        """
        checkpoint_id = CheckpointId(
            batch_id=batch_state.batch_id,
            timestamp=time.time(),
            checkpoint_type=batch_state.checkpoint_type
        )
        
        # Update last_updated timestamp
        batch_state.last_updated = checkpoint_id.timestamp
        
        # Create checkpoint file path
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        
        try:
            # Create temporary file first for atomic write
            temp_file = checkpoint_file.with_suffix('.tmp')
            
            # Write checkpoint data
            with temp_file.open('w', encoding='utf-8') as f:
                json.dump(batch_state.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Atomic move to final location
            temp_file.replace(checkpoint_file)
            
            # Update checkpoint tracking
            if batch_state.batch_id not in self.current_checkpoints:
                self.current_checkpoints[batch_state.batch_id] = []
            self.current_checkpoints[batch_state.batch_id].append(checkpoint_id)
            
            # Update auto-save tracking
            self.last_auto_save[batch_state.batch_id] = checkpoint_id.timestamp
            
            # Cleanup old checkpoints if needed
            self._cleanup_old_checkpoints(batch_state.batch_id)
            
            self.logger.info(f"Checkpoint saved: {checkpoint_id}")
            return checkpoint_id
            
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint {checkpoint_id}: {e}")
            raise
    
    def load_checkpoint(self, checkpoint_id: CheckpointId) -> BatchState:
        """
        Load batch processing state from a checkpoint.
        
        Args:
            checkpoint_id: Identifier of checkpoint to load
            
        Returns:
            BatchState restored from checkpoint
            
        Raises:
            FileNotFoundError: If checkpoint file doesn't exist
            ValueError: If checkpoint data is invalid
        """
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_file}")
        
        try:
            with checkpoint_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            batch_state = BatchState.from_dict(data)
            
            self.logger.info(f"Checkpoint loaded: {checkpoint_id}")
            return batch_state
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            raise ValueError(f"Invalid checkpoint data in {checkpoint_file}: {e}")
    
    def load_latest_checkpoint(self, batch_id: str) -> Optional[BatchState]:
        """
        Load the most recent checkpoint for a batch.
        
        Args:
            batch_id: ID of the batch to find checkpoint for
            
        Returns:
            Latest BatchState for the batch, or None if no checkpoints exist
        """
        checkpoints = self.find_checkpoints(batch_id)
        
        if not checkpoints:
            return None
        
        # Sort by timestamp descending and take the most recent
        latest_checkpoint = max(checkpoints, key=lambda c: c.timestamp)
        
        try:
            return self.load_checkpoint(latest_checkpoint)
        except (FileNotFoundError, ValueError):
            self.logger.warning(f"Latest checkpoint {latest_checkpoint} is invalid, trying next")
            # Remove invalid checkpoint and try next
            self._remove_checkpoint(latest_checkpoint)
            checkpoints.remove(latest_checkpoint)
            
            if checkpoints:
                next_latest = max(checkpoints, key=lambda c: c.timestamp)
                return self.load_checkpoint(next_latest)
            
            return None
    
    def should_auto_save(self, batch_id: str) -> bool:
        """
        Check if an auto-save checkpoint should be created for the batch.
        
        Args:
            batch_id: ID of the batch to check
            
        Returns:
            True if auto-save is due
        """
        if batch_id not in self.last_auto_save:
            return True
        
        time_since_last_save = time.time() - self.last_auto_save[batch_id]
        return time_since_last_save >= self.auto_save_interval
    
    def find_checkpoints(self, batch_id: str) -> List[CheckpointId]:
        """
        Find all checkpoints for a specific batch.
        
        Args:
            batch_id: ID of the batch to find checkpoints for
            
        Returns:
            List of CheckpointIds for the batch
        """
        checkpoints = []
        pattern = f"{batch_id}_*.json"
        
        for checkpoint_file in self.checkpoint_dir.glob(pattern):
            try:
                # Parse checkpoint ID from filename
                filename = checkpoint_file.stem
                parts = filename.split('_')
                
                if len(parts) >= 3:
                    # Find the checkpoint type - should be one of the enum values
                    checkpoint_type = None
                    timestamp = None
                    
                    # Timestamp should be the last part
                    try:
                        timestamp = float(parts[-1])
                    except ValueError:
                        continue  # Skip if last part is not a valid timestamp
                    
                    # Work backwards to find valid checkpoint type
                    valid_types = [ct.value for ct in CheckpointType]
                    for i in range(len(parts) - 2, 0, -1):
                        # Try both single part and multi-part checkpoint types
                        potential_type = parts[i]
                        if potential_type in valid_types:
                            checkpoint_type = potential_type
                            file_batch_id = '_'.join(parts[:i])
                            break
                        
                        # Try two-part type (e.g., batch_start)
                        if i > 0:
                            potential_type = f"{parts[i-1]}_{parts[i]}"
                            if potential_type in valid_types:
                                checkpoint_type = potential_type
                                file_batch_id = '_'.join(parts[:i-1])
                                break
                    
                    if checkpoint_type and timestamp and file_batch_id == batch_id:
                        checkpoints.append(CheckpointId(
                            batch_id=file_batch_id,
                            timestamp=timestamp,
                            checkpoint_type=CheckpointType(checkpoint_type)
                        ))
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Invalid checkpoint filename: {checkpoint_file.name}")
        
        return sorted(checkpoints, key=lambda c: c.timestamp)
    
    def cleanup_checkpoints(self, batch_id: Optional[str] = None) -> None:
        """
        Clean up old or completed checkpoint files.
        
        Args:
            batch_id: Optional specific batch to clean up. If None, cleans all old checkpoints.
        """
        current_time = time.time()
        
        if batch_id:
            # Clean up specific batch
            checkpoints = self.find_checkpoints(batch_id)
            for checkpoint in checkpoints:
                if current_time - checkpoint.timestamp > self.max_checkpoint_age:
                    self._remove_checkpoint(checkpoint)
            
            # Remove from tracking
            if batch_id in self.current_checkpoints:
                del self.current_checkpoints[batch_id]
            if batch_id in self.last_auto_save:
                del self.last_auto_save[batch_id]
        else:
            # Clean up all old checkpoints
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                try:
                    file_age = current_time - checkpoint_file.stat().st_mtime
                    if file_age > self.max_checkpoint_age:
                        checkpoint_file.unlink()
                        self.logger.debug(f"Removed old checkpoint: {checkpoint_file.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove checkpoint {checkpoint_file}: {e}")
    
    def create_batch_id(self, input_dir: Path, config: Dict[str, Any]) -> str:
        """
        Create a unique batch ID based on input parameters.
        
        Args:
            input_dir: Input directory path
            config: Processing configuration
            
        Returns:
            Unique batch identifier
        """
        # Create hash of input directory and configuration
        hasher = hashlib.md5()
        hasher.update(str(input_dir).encode('utf-8'))
        hasher.update(json.dumps(config, sort_keys=True).encode('utf-8'))
        
        # Combine with timestamp for uniqueness
        timestamp = int(time.time())
        hash_suffix = hasher.hexdigest()[:8]
        
        return f"batch_{timestamp}_{hash_suffix}"
    
    def get_checkpoint_summary(self, batch_id: str) -> Dict[str, Any]:
        """
        Get summary information about checkpoints for a batch.
        
        Args:
            batch_id: ID of the batch
            
        Returns:
            Dictionary with checkpoint summary information
        """
        checkpoints = self.find_checkpoints(batch_id)
        
        if not checkpoints:
            return {
                "batch_id": batch_id,
                "checkpoint_count": 0,
                "latest_checkpoint": None,
                "checkpoint_types": []
            }
        
        latest = max(checkpoints, key=lambda c: c.timestamp)
        checkpoint_types = list(set(c.checkpoint_type.value for c in checkpoints))
        
        return {
            "batch_id": batch_id,
            "checkpoint_count": len(checkpoints),
            "latest_checkpoint": {
                "timestamp": latest.timestamp,
                "type": latest.checkpoint_type.value,
                "age_seconds": time.time() - latest.timestamp
            },
            "checkpoint_types": checkpoint_types,
            "oldest_checkpoint": min(checkpoints, key=lambda c: c.timestamp).timestamp,
            "total_size_bytes": sum(
                (self.checkpoint_dir / f"{c}.json").stat().st_size
                for c in checkpoints
                if (self.checkpoint_dir / f"{c}.json").exists()
            )
        }
    
    def _cleanup_old_checkpoints(self, batch_id: str) -> None:
        """Clean up old checkpoints for a specific batch to maintain limits."""
        if batch_id not in self.current_checkpoints:
            return
        
        checkpoints = self.current_checkpoints[batch_id]
        
        # Sort by timestamp and keep only the most recent
        checkpoints.sort(key=lambda c: c.timestamp, reverse=True)
        
        # Remove excess checkpoints
        while len(checkpoints) > self.max_checkpoints_per_batch:
            old_checkpoint = checkpoints.pop()
            self._remove_checkpoint(old_checkpoint)
        
        self.current_checkpoints[batch_id] = checkpoints
    
    def _remove_checkpoint(self, checkpoint_id: CheckpointId) -> None:
        """Remove a specific checkpoint file."""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        
        try:
            if checkpoint_file.exists():
                checkpoint_file.unlink()
                self.logger.debug(f"Removed checkpoint: {checkpoint_id}")
        except Exception as e:
            self.logger.warning(f"Failed to remove checkpoint {checkpoint_id}: {e}")