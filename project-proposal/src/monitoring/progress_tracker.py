"""
Progress tracking for the markdown-to-PDF processing pipeline.

This module provides real-time progress monitoring, ETA calculation,
file-level status tracking, and batch processing statistics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, NamedTuple, Any
from pathlib import Path
import time
import threading
from collections import defaultdict
import math


class ProcessingStatus(Enum):
    """Status of individual file processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class ProgressReport(NamedTuple):
    """Comprehensive progress report data."""
    total_files: int
    completed_files: int
    success_count: int
    failed_count: int
    skipped_count: int
    progress_percentage: float
    elapsed_time: float
    estimated_time_remaining: Optional[float]
    current_file: Optional[str]
    processing_speed: float  # files per second
    error_rate: float  # percentage of failed files


@dataclass
class FileProgress:
    """Progress information for a single file."""
    file_path: Path
    status: ProcessingStatus
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    processing_duration: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    file_size: Optional[int] = None


@dataclass 
class BatchStatistics:
    """Statistics for batch processing operations."""
    total_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    total_processing_time: float = 0.0
    average_file_time: float = 0.0
    total_file_size: int = 0
    processing_speed_fps: float = 0.0  # files per second
    processing_speed_bps: float = 0.0  # bytes per second
    error_rate: float = 0.0
    retry_attempts: int = 0
    status_distribution: Dict[ProcessingStatus, int] = field(default_factory=dict)


class ProgressTracker:
    """
    Tracks processing progress for batch markdown-to-PDF operations.
    
    Features:
    - Real-time progress updates
    - ETA calculation based on processing speed
    - Individual file status tracking
    - Batch statistics and error rates
    - Thread-safe operations for concurrent processing
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._files: Dict[str, FileProgress] = {}
        self._start_time: Optional[float] = None
        self._total_files: int = 0
        self._current_file: Optional[str] = None
        self._processing_times: List[float] = []
        self._file_sizes: List[int] = []
        
    def start_tracking(self, total_files: int) -> None:
        """
        Initialize progress tracking for a batch operation.
        
        Args:
            total_files: Total number of files to process
        """
        with self._lock:
            self._total_files = total_files
            self._start_time = time.time()
            self._files.clear()
            self._processing_times.clear()
            self._file_sizes.clear()
            self._current_file = None
    
    def update_progress(self, file_processed: str, status: ProcessingStatus, 
                       error_message: Optional[str] = None,
                       file_size: Optional[int] = None) -> None:
        """
        Update progress for a specific file.
        
        Args:
            file_processed: Path of the file being processed
            status: Current processing status
            error_message: Error message if status is FAILED
            file_size: Size of file in bytes for speed calculations
        """
        with self._lock:
            current_time = time.time()
            
            # Initialize file progress if not exists
            if file_processed not in self._files:
                self._files[file_processed] = FileProgress(
                    file_path=Path(file_processed),
                    status=ProcessingStatus.PENDING,
                    file_size=file_size
                )
            
            file_progress = self._files[file_processed]
            old_status = file_progress.status
            
            # Update file progress
            file_progress.status = status
            file_progress.error_message = error_message
            if file_size:
                file_progress.file_size = file_size
                
            # Handle status transitions
            if old_status == ProcessingStatus.PENDING and status == ProcessingStatus.PROCESSING:
                file_progress.start_time = current_time
                self._current_file = file_processed
                
            elif status in [ProcessingStatus.SUCCESS, ProcessingStatus.FAILED, ProcessingStatus.SKIPPED]:
                file_progress.end_time = current_time
                if file_progress.start_time:
                    duration = current_time - file_progress.start_time
                    file_progress.processing_duration = duration
                    self._processing_times.append(duration)
                    
                    if file_progress.file_size:
                        self._file_sizes.append(file_progress.file_size)
                
                # Clear current file if it's the one being completed
                if self._current_file == file_processed:
                    self._current_file = None
                    
            elif status == ProcessingStatus.RETRYING:
                file_progress.retry_count += 1
    
    def get_progress_report(self) -> ProgressReport:
        """
        Generate comprehensive progress report.
        
        Returns:
            ProgressReport with current statistics and estimates
        """
        with self._lock:
            if not self._start_time:
                return self._empty_report()
            
            current_time = time.time()
            elapsed_time = current_time - self._start_time
            
            # Count statuses
            status_counts = defaultdict(int)
            for file_progress in self._files.values():
                status_counts[file_progress.status] += 1
                
            completed_count = (status_counts[ProcessingStatus.SUCCESS] + 
                             status_counts[ProcessingStatus.FAILED] +
                             status_counts[ProcessingStatus.SKIPPED])
            
            success_count = status_counts[ProcessingStatus.SUCCESS]
            failed_count = status_counts[ProcessingStatus.FAILED]
            skipped_count = status_counts[ProcessingStatus.SKIPPED]
            
            # Calculate progress percentage
            progress_percentage = (completed_count / self._total_files * 100) if self._total_files > 0 else 0.0
            
            # Calculate processing speed and ETA
            processing_speed = completed_count / elapsed_time if elapsed_time > 0 else 0.0
            remaining_files = self._total_files - completed_count
            estimated_time_remaining = (remaining_files / processing_speed) if processing_speed > 0 else None
            
            # Calculate error rate
            error_rate = (failed_count / completed_count * 100) if completed_count > 0 else 0.0
            
            return ProgressReport(
                total_files=self._total_files,
                completed_files=completed_count,
                success_count=success_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                progress_percentage=progress_percentage,
                elapsed_time=elapsed_time,
                estimated_time_remaining=estimated_time_remaining,
                current_file=self._current_file,
                processing_speed=processing_speed,
                error_rate=error_rate
            )
    
    def get_batch_statistics(self) -> BatchStatistics:
        """
        Get detailed batch processing statistics.
        
        Returns:
            BatchStatistics with comprehensive metrics
        """
        with self._lock:
            if not self._start_time:
                return BatchStatistics()
                
            current_time = time.time()
            elapsed_time = current_time - self._start_time
            
            # Count statuses
            status_counts = defaultdict(int)
            total_retry_attempts = 0
            
            for file_progress in self._files.values():
                status_counts[file_progress.status] += 1
                total_retry_attempts += file_progress.retry_count
            
            successful_files = status_counts[ProcessingStatus.SUCCESS]
            failed_files = status_counts[ProcessingStatus.FAILED]
            skipped_files = status_counts[ProcessingStatus.SKIPPED]
            completed_files = successful_files + failed_files + skipped_files
            
            # Calculate processing metrics
            total_processing_time = sum(self._processing_times)
            average_file_time = (total_processing_time / len(self._processing_times) 
                               if self._processing_times else 0.0)
            
            total_file_size = sum(self._file_sizes)
            processing_speed_fps = completed_files / elapsed_time if elapsed_time > 0 else 0.0
            processing_speed_bps = total_file_size / elapsed_time if elapsed_time > 0 else 0.0
            
            error_rate = (failed_files / completed_files * 100) if completed_files > 0 else 0.0
            
            return BatchStatistics(
                total_files=self._total_files,
                successful_files=successful_files,
                failed_files=failed_files,
                skipped_files=skipped_files,
                total_processing_time=total_processing_time,
                average_file_time=average_file_time,
                total_file_size=total_file_size,
                processing_speed_fps=processing_speed_fps,
                processing_speed_bps=processing_speed_bps,
                error_rate=error_rate,
                retry_attempts=total_retry_attempts,
                status_distribution=dict(status_counts)
            )
    
    def get_file_status(self, file_path: str) -> Optional[FileProgress]:
        """
        Get progress information for a specific file.
        
        Args:
            file_path: Path of the file to query
            
        Returns:
            FileProgress object or None if file not tracked
        """
        with self._lock:
            return self._files.get(file_path)
    
    def get_failed_files(self) -> List[FileProgress]:
        """
        Get list of files that failed processing.
        
        Returns:
            List of FileProgress objects for failed files
        """
        with self._lock:
            return [fp for fp in self._files.values() 
                   if fp.status == ProcessingStatus.FAILED]
    
    def get_pending_files(self) -> List[FileProgress]:
        """
        Get list of files still pending processing.
        
        Returns:
            List of FileProgress objects for pending files
        """
        with self._lock:
            return [fp for fp in self._files.values() 
                   if fp.status == ProcessingStatus.PENDING]
    
    def reset(self) -> None:
        """Reset all progress tracking state."""
        with self._lock:
            self._files.clear()
            self._start_time = None
            self._total_files = 0
            self._current_file = None
            self._processing_times.clear()
            self._file_sizes.clear()
    
    def _empty_report(self) -> ProgressReport:
        """Create an empty progress report."""
        return ProgressReport(
            total_files=0,
            completed_files=0,
            success_count=0,
            failed_count=0,
            skipped_count=0,
            progress_percentage=0.0,
            elapsed_time=0.0,
            estimated_time_remaining=None,
            current_file=None,
            processing_speed=0.0,
            error_rate=0.0
        )
    
    def format_progress_display(self, show_detailed: bool = False) -> str:
        """
        Format progress information for display.
        
        Args:
            show_detailed: Whether to include detailed statistics
            
        Returns:
            Formatted progress string
        """
        report = self.get_progress_report()
        
        # Basic progress bar
        bar_width = 40
        filled = int(bar_width * report.progress_percentage / 100)
        bar = '█' * filled + '░' * (bar_width - filled)
        
        # Format time values
        elapsed_str = self._format_duration(report.elapsed_time)
        eta_str = self._format_duration(report.estimated_time_remaining) if report.estimated_time_remaining else "?"
        
        # Basic display
        result = (f"Progress: [{bar}] {report.progress_percentage:.1f}%\n"
                 f"Files: {report.completed_files}/{report.total_files} "
                 f"(✓{report.success_count} ✗{report.failed_count} ⊝{report.skipped_count})\n"
                 f"Time: {elapsed_str} elapsed, ~{eta_str} remaining\n"
                 f"Speed: {report.processing_speed:.2f} files/sec")
        
        if report.current_file:
            result += f"\nCurrent: {Path(report.current_file).name}"
            
        if show_detailed:
            stats = self.get_batch_statistics()
            result += (f"\n\nDetailed Statistics:"
                      f"\n• Error rate: {stats.error_rate:.1f}%"
                      f"\n• Retry attempts: {stats.retry_attempts}"
                      f"\n• Average file time: {stats.average_file_time:.2f}s"
                      f"\n• Total processing time: {self._format_duration(stats.total_processing_time)}")
            
            if stats.total_file_size > 0:
                result += f"\n• Processing speed: {self._format_bytes_per_sec(stats.processing_speed_bps)}"
        
        return result
    
    def _format_duration(self, seconds: Optional[float]) -> str:
        """Format duration in human-readable format."""
        if seconds is None:
            return "?"
            
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def _format_bytes_per_sec(self, bps: float) -> str:
        """Format bytes per second in human-readable format."""
        if bps < 1024:
            return f"{bps:.1f} B/s"
        elif bps < 1024**2:
            return f"{bps/1024:.1f} KB/s"
        elif bps < 1024**3:
            return f"{bps/(1024**2):.1f} MB/s"
        else:
            return f"{bps/(1024**3):.1f} GB/s"