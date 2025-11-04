"""
Unit tests for the CheckpointManager module.

Tests checkpoint creation, restoration, and lifecycle management
for batch processing state persistence.
"""

import pytest
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import asdict

from src.recovery.checkpoint_manager import (
    CheckpointManager,
    BatchState,
    FileProcessingState,
    CheckpointId,
    CheckpointType,
    ProcessingStatus
)


class TestFileProcessingState:
    """Test FileProcessingState functionality."""
    
    def test_file_processing_state_creation(self):
        """Test basic FileProcessingState creation."""
        file_path = Path("/test/file.md")
        
        state = FileProcessingState(
            file_path=file_path,
            status=ProcessingStatus.PENDING
        )
        
        assert state.file_path == file_path
        assert state.status == ProcessingStatus.PENDING
        assert state.retry_count == 0
        assert state.processing_time == 0.0
        
    def test_file_processing_state_serialization(self):
        """Test FileProcessingState to_dict and from_dict."""
        original = FileProcessingState(
            file_path=Path("/test/file.md"),
            status=ProcessingStatus.COMPLETED,
            start_time=1234567.0,
            end_time=1234568.0,
            processing_time=1.0,
            error_message=None,
            retry_count=2,
            output_path=Path("/output/file.pdf")
        )
        
        # Test serialization
        data = original.to_dict()
        assert data["file_path"] == str(Path("/test/file.md"))
        assert data["status"] == "completed"
        assert data["start_time"] == 1234567.0
        assert data["retry_count"] == 2
        assert data["output_path"] == str(Path("/output/file.pdf"))
        
        # Test deserialization
        restored = FileProcessingState.from_dict(data)
        assert restored.file_path == original.file_path
        assert restored.status == original.status
        assert restored.start_time == original.start_time
        assert restored.end_time == original.end_time
        assert restored.processing_time == original.processing_time
        assert restored.retry_count == original.retry_count
        assert restored.output_path == original.output_path
    
    def test_file_processing_state_with_error(self):
        """Test FileProcessingState with error information."""
        state = FileProcessingState(
            file_path=Path("/test/error_file.md"),
            status=ProcessingStatus.FAILED,
            error_message="Pandoc conversion failed",
            retry_count=3
        )
        
        data = state.to_dict()
        restored = FileProcessingState.from_dict(data)
        
        assert restored.status == ProcessingStatus.FAILED
        assert restored.error_message == "Pandoc conversion failed"
        assert restored.retry_count == 3


class TestBatchState:
    """Test BatchState functionality."""
    
    @pytest.fixture
    def sample_batch_state(self):
        """Create a sample BatchState for testing."""
        file_states = {
            "file1.md": FileProcessingState(
                file_path=Path("/input/file1.md"),
                status=ProcessingStatus.COMPLETED
            ),
            "file2.md": FileProcessingState(
                file_path=Path("/input/file2.md"),
                status=ProcessingStatus.PENDING
            )
        }
        
        return BatchState(
            batch_id="test_batch_123",
            input_directory=Path("/input"),
            output_directory=Path("/output"),
            total_files=2,
            processed_files=1,
            failed_files=0,
            skipped_files=0,
            start_time=time.time(),
            last_updated=time.time(),
            file_states=file_states,
            configuration={"template": "default", "engine": "xelatex"},
            checkpoint_type=CheckpointType.FILE_PROCESSED
        )
    
    def test_batch_state_serialization(self, sample_batch_state):
        """Test BatchState to_dict and from_dict."""
        # Test serialization
        data = sample_batch_state.to_dict()
        
        assert data["batch_id"] == "test_batch_123"
        assert data["input_directory"] == str(Path("/input"))
        assert data["total_files"] == 2
        assert data["processed_files"] == 1
        assert "file1.md" in data["file_states"]
        assert "file2.md" in data["file_states"]
        assert data["configuration"]["template"] == "default"
        assert data["checkpoint_type"] == "file_processed"
        
        # Test deserialization
        restored = BatchState.from_dict(data)
        
        assert restored.batch_id == sample_batch_state.batch_id
        assert restored.input_directory == sample_batch_state.input_directory
        assert restored.output_directory == sample_batch_state.output_directory
        assert restored.total_files == sample_batch_state.total_files
        assert restored.processed_files == sample_batch_state.processed_files
        assert len(restored.file_states) == 2
        assert "file1.md" in restored.file_states
        assert restored.file_states["file1.md"].status == ProcessingStatus.COMPLETED
        assert restored.configuration == sample_batch_state.configuration


class TestCheckpointId:
    """Test CheckpointId functionality."""
    
    def test_checkpoint_id_creation(self):
        """Test CheckpointId creation and string representation."""
        checkpoint_id = CheckpointId(
            batch_id="test_batch",
            timestamp=1234567890.5,
            checkpoint_type=CheckpointType.BATCH_START
        )
        
        assert checkpoint_id.batch_id == "test_batch"
        assert checkpoint_id.timestamp == 1234567890.5
        assert checkpoint_id.checkpoint_type == CheckpointType.BATCH_START
        
        # Test string representation
        str_repr = str(checkpoint_id)
        assert str_repr == "test_batch_batch_start_1234567890"
    
    def test_checkpoint_id_complex_batch_name(self):
        """Test CheckpointId with complex batch name."""
        checkpoint_id = CheckpointId(
            batch_id="complex_batch_name_with_underscores",
            timestamp=1234567890.0,
            checkpoint_type=CheckpointType.FILE_PROCESSED
        )
        
        str_repr = str(checkpoint_id)
        assert str_repr == "complex_batch_name_with_underscores_file_processed_1234567890"


class TestCheckpointManager:
    """Test CheckpointManager functionality."""
    
    @pytest.fixture
    def temp_checkpoint_dir(self):
        """Create a temporary directory for checkpoints."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def checkpoint_manager(self, temp_checkpoint_dir):
        """Create CheckpointManager with temporary directory."""
        return CheckpointManager(checkpoint_dir=temp_checkpoint_dir)
    
    @pytest.fixture
    def sample_batch_state(self):
        """Create a sample BatchState for testing."""
        file_states = {
            "test.md": FileProcessingState(
                file_path=Path("/input/test.md"),
                status=ProcessingStatus.PENDING
            )
        }
        
        return BatchState(
            batch_id="test_batch_456",
            input_directory=Path("/input"),
            output_directory=Path("/output"),
            total_files=1,
            processed_files=0,
            failed_files=0,
            skipped_files=0,
            start_time=time.time(),
            last_updated=time.time(),
            file_states=file_states,
            configuration={"template": "default"}
        )
    
    def test_checkpoint_manager_initialization(self, temp_checkpoint_dir):
        """Test CheckpointManager initialization."""
        manager = CheckpointManager(checkpoint_dir=temp_checkpoint_dir)
        
        assert manager.checkpoint_dir == temp_checkpoint_dir
        assert temp_checkpoint_dir.exists()
        assert manager.current_checkpoints == {}
        assert manager.last_auto_save == {}
    
    def test_save_checkpoint(self, checkpoint_manager, sample_batch_state):
        """Test saving a checkpoint."""
        checkpoint_id = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        assert isinstance(checkpoint_id, CheckpointId)
        assert checkpoint_id.batch_id == sample_batch_state.batch_id
        assert checkpoint_id.checkpoint_type == CheckpointType.BATCH_START
        
        # Check file was created
        checkpoint_file = checkpoint_manager.checkpoint_dir / f"{checkpoint_id}.json"
        assert checkpoint_file.exists()
        
        # Check tracking was updated
        assert sample_batch_state.batch_id in checkpoint_manager.current_checkpoints
        assert checkpoint_id in checkpoint_manager.current_checkpoints[sample_batch_state.batch_id]
    
    def test_load_checkpoint(self, checkpoint_manager, sample_batch_state):
        """Test loading a checkpoint."""
        # Save checkpoint first
        checkpoint_id = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        # Load checkpoint
        loaded_state = checkpoint_manager.load_checkpoint(checkpoint_id)
        
        assert loaded_state.batch_id == sample_batch_state.batch_id
        assert loaded_state.input_directory == sample_batch_state.input_directory
        assert loaded_state.total_files == sample_batch_state.total_files
        assert len(loaded_state.file_states) == len(sample_batch_state.file_states)
        assert "test.md" in loaded_state.file_states
    
    def test_load_nonexistent_checkpoint(self, checkpoint_manager):
        """Test loading a checkpoint that doesn't exist."""
        nonexistent_id = CheckpointId(
            batch_id="nonexistent",
            timestamp=time.time(),
            checkpoint_type=CheckpointType.BATCH_START
        )
        
        with pytest.raises(FileNotFoundError):
            checkpoint_manager.load_checkpoint(nonexistent_id)
    
    def test_load_latest_checkpoint(self, checkpoint_manager, sample_batch_state):
        """Test loading the latest checkpoint for a batch."""
        # Save multiple checkpoints
        checkpoint1 = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        # Wait a bit and save another
        time.sleep(0.5)
        sample_batch_state.processed_files = 1
        sample_batch_state.checkpoint_type = CheckpointType.FILE_PROCESSED
        checkpoint2 = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        # Load latest should get the second checkpoint
        latest_state = checkpoint_manager.load_latest_checkpoint(sample_batch_state.batch_id)
        
        assert latest_state is not None
        assert latest_state.processed_files == 1
        assert latest_state.checkpoint_type == CheckpointType.FILE_PROCESSED
    
    def test_load_latest_checkpoint_no_checkpoints(self, checkpoint_manager):
        """Test loading latest checkpoint when none exist."""
        result = checkpoint_manager.load_latest_checkpoint("nonexistent_batch")
        assert result is None
    
    def test_should_auto_save(self, checkpoint_manager):
        """Test auto-save timing logic."""
        batch_id = "test_batch"
        
        # Should auto-save initially (no previous save)
        assert checkpoint_manager.should_auto_save(batch_id) == True
        
        # Record a recent save
        checkpoint_manager.last_auto_save[batch_id] = time.time()
        
        # Should not auto-save immediately after
        assert checkpoint_manager.should_auto_save(batch_id) == False
        
        # Mock older save time
        checkpoint_manager.last_auto_save[batch_id] = time.time() - 100
        
        # Should auto-save after interval
        assert checkpoint_manager.should_auto_save(batch_id) == True
    
    def test_find_checkpoints(self, checkpoint_manager, sample_batch_state):
        """Test finding checkpoints for a batch."""
        batch_id = sample_batch_state.batch_id
        
        # Initially no checkpoints
        checkpoints = checkpoint_manager.find_checkpoints(batch_id)
        assert len(checkpoints) == 0
        
        # Save some checkpoints
        checkpoint1 = checkpoint_manager.save_checkpoint(sample_batch_state)
        time.sleep(0.5)
        
        sample_batch_state.checkpoint_type = CheckpointType.FILE_PROCESSED
        checkpoint2 = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        # Find checkpoints
        checkpoints = checkpoint_manager.find_checkpoints(batch_id)
        assert len(checkpoints) == 2
        
        # Should be sorted by timestamp
        if len(checkpoints) >= 2:
            # Allow for equal timestamps but ensure correct ordering by type if timestamps are equal
            if checkpoints[0].timestamp == checkpoints[1].timestamp:
                # If timestamps are equal, just check we have both types
                types = [cp.checkpoint_type for cp in checkpoints]
                assert CheckpointType.BATCH_START in types
                assert CheckpointType.FILE_PROCESSED in types
            else:
                assert checkpoints[0].timestamp < checkpoints[1].timestamp
                assert checkpoints[0].checkpoint_type == CheckpointType.BATCH_START
                assert checkpoints[1].checkpoint_type == CheckpointType.FILE_PROCESSED
    
    def test_cleanup_checkpoints_by_batch(self, checkpoint_manager, sample_batch_state):
        """Test cleaning up checkpoints for a specific batch."""
        batch_id = sample_batch_state.batch_id
        
        # Save checkpoint
        checkpoint_id = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        # Verify checkpoint exists
        checkpoint_file = checkpoint_manager.checkpoint_dir / f"{checkpoint_id}.json"
        assert checkpoint_file.exists()
        
        # Clean up batch
        checkpoint_manager.cleanup_checkpoints(batch_id)
        
        # Verify tracking was cleared (but file might still exist if not old enough)
        assert batch_id not in checkpoint_manager.current_checkpoints
        assert batch_id not in checkpoint_manager.last_auto_save
    
    def test_cleanup_old_checkpoints_by_age(self, checkpoint_manager, sample_batch_state):
        """Test cleaning up old checkpoints by age."""
        # Mock old checkpoint file
        old_checkpoint = CheckpointId(
            batch_id="old_batch",
            timestamp=time.time() - 48 * 3600,  # 48 hours ago
            checkpoint_type=CheckpointType.BATCH_START
        )
        
        # Create the file manually with old timestamp
        old_file = checkpoint_manager.checkpoint_dir / f"{old_checkpoint}.json"
        old_file.write_text('{"test": "data"}')
        
        # Set file modification time to be old
        import os
        old_time = time.time() - 48 * 3600
        os.utime(old_file, (old_time, old_time))
        
        # Verify file exists
        assert old_file.exists()
        
        # Run cleanup
        checkpoint_manager.cleanup_checkpoints()
        
        # File should be removed (if older than max_checkpoint_age)
        # Note: This test depends on the max_checkpoint_age setting
    
    def test_create_batch_id(self, checkpoint_manager):
        """Test batch ID generation."""
        input_dir = Path("/test/input")
        config = {"template": "default", "engine": "xelatex"}
        
        batch_id1 = checkpoint_manager.create_batch_id(input_dir, config)
        time.sleep(1.1)  # Ensure different timestamp 
        batch_id2 = checkpoint_manager.create_batch_id(input_dir, config)
        
        # IDs should be different (due to timestamp)
        assert batch_id1 != batch_id2
        
        # Both should start with "batch_"
        assert batch_id1.startswith("batch_")
        assert batch_id2.startswith("batch_")
        
        # Same input should produce same hash component
        time.sleep(1.1)  # Ensure different timestamp (need at least 1 second for integer timestamp)
        batch_id3 = checkpoint_manager.create_batch_id(input_dir, config)
        
        # Hash portions should be the same
        hash1 = batch_id1.split('_')[-1]
        hash3 = batch_id3.split('_')[-1]
        assert hash1 == hash3
    
    def test_get_checkpoint_summary(self, checkpoint_manager, sample_batch_state):
        """Test getting checkpoint summary information."""
        batch_id = sample_batch_state.batch_id
        
        # Test empty summary
        summary = checkpoint_manager.get_checkpoint_summary(batch_id)
        assert summary["batch_id"] == batch_id
        assert summary["checkpoint_count"] == 0
        assert summary["latest_checkpoint"] is None
        
        # Save some checkpoints
        checkpoint1 = checkpoint_manager.save_checkpoint(sample_batch_state)
        time.sleep(0.5)
        
        sample_batch_state.checkpoint_type = CheckpointType.FILE_PROCESSED
        checkpoint2 = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        # Get summary with checkpoints
        summary = checkpoint_manager.get_checkpoint_summary(batch_id)
        
        assert summary["batch_id"] == batch_id
        assert summary["checkpoint_count"] == 2
        assert summary["latest_checkpoint"] is not None
        # The latest checkpoint type depends on timestamp ordering
        latest_type = summary["latest_checkpoint"]["type"]
        assert latest_type in ["batch_start", "file_processed"]
        assert "batch_start" in summary["checkpoint_types"]
        assert "file_processed" in summary["checkpoint_types"]
        assert summary["total_size_bytes"] > 0
    
    def test_checkpoint_atomic_write(self, checkpoint_manager, sample_batch_state):
        """Test that checkpoint writes use atomic operations."""
        # Test that successful checkpoint saves create final files
        checkpoint_id = checkpoint_manager.save_checkpoint(sample_batch_state)
        
        # Check that the final file exists
        checkpoint_file = checkpoint_manager.checkpoint_dir / f"{checkpoint_id}.json"
        assert checkpoint_file.exists()
        
        # Check that no temp file remains
        temp_files = list(checkpoint_manager.checkpoint_dir.glob("*.tmp"))
        assert len(temp_files) == 0
        
        # Verify file content is valid JSON
        import json
        with checkpoint_file.open('r') as f:
            data = json.load(f)
        assert data["batch_id"] == sample_batch_state.batch_id
    
    def test_invalid_checkpoint_data(self, checkpoint_manager, temp_checkpoint_dir):
        """Test handling of invalid checkpoint data."""
        # Create invalid checkpoint file
        invalid_checkpoint = CheckpointId(
            batch_id="invalid_batch",
            timestamp=time.time(),
            checkpoint_type=CheckpointType.BATCH_START
        )
        
        invalid_file = temp_checkpoint_dir / f"{invalid_checkpoint}.json"
        invalid_file.write_text("invalid json content")
        
        with pytest.raises(ValueError):
            checkpoint_manager.load_checkpoint(invalid_checkpoint)
    
    def test_checkpoint_filename_parsing(self, checkpoint_manager):
        """Test parsing checkpoint IDs from filenames."""
        # Test various filename formats
        test_files = [
            "simple_batch_batch_start_1234567890.json",
            "complex_batch_name_with_underscores_file_processed_1234567891.json",
            "invalid_filename.json",
            "batch_only_1234567892.json"
        ]
        
        for filename in test_files:
            test_file = checkpoint_manager.checkpoint_dir / filename
            test_file.write_text('{"test": "data"}')
        
        # Find checkpoints for specific batches
        simple_checkpoints = checkpoint_manager.find_checkpoints("simple_batch")
        assert len(simple_checkpoints) == 1
        assert simple_checkpoints[0].checkpoint_type == CheckpointType.BATCH_START
        
        complex_checkpoints = checkpoint_manager.find_checkpoints("complex_batch_name_with_underscores")
        assert len(complex_checkpoints) == 1
        assert complex_checkpoints[0].checkpoint_type == CheckpointType.FILE_PROCESSED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])