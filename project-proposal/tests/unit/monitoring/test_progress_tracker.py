"""
Unit tests for the progress tracking module.
Tests progress monitoring, ETA calculation, file status tracking, and batch statistics.
"""

import pytest
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.monitoring.progress_tracker import (
    ProgressTracker,
    ProcessingStatus,
    ProgressReport,
    FileProgress,
    BatchStatistics
)


class TestProgressTracker:
    """Test cases for the ProgressTracker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ProgressTracker()
    
    def test_initialization(self):
        """Test progress tracker initialization."""
        assert isinstance(self.tracker, ProgressTracker)
        assert self.tracker._total_files == 0
        assert self.tracker._start_time is None
        assert self.tracker._current_file is None
        assert len(self.tracker._files) == 0
    
    def test_start_tracking(self):
        """Test starting progress tracking."""
        total_files = 5
        self.tracker.start_tracking(total_files)
        
        assert self.tracker._total_files == total_files
        assert self.tracker._start_time is not None
        assert isinstance(self.tracker._start_time, float)
        assert len(self.tracker._files) == 0
    
    def test_update_progress_new_file(self):
        """Test updating progress for a new file."""
        self.tracker.start_tracking(3)
        file_path = "test/file1.md"
        
        self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING)
        
        assert file_path in self.tracker._files
        file_progress = self.tracker._files[file_path]
        assert file_progress.status == ProcessingStatus.PROCESSING
        assert file_progress.file_path == Path(file_path)
        assert file_progress.start_time is not None
        assert self.tracker._current_file == file_path
    
    def test_update_progress_file_completion(self):
        """Test updating progress when file completes successfully."""
        self.tracker.start_tracking(1)
        file_path = "test/file1.md"
        file_size = 1024
        
        # Start processing
        self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING, file_size=file_size)
        
        # Small delay to ensure measurable duration
        time.sleep(0.01)
        
        # Complete processing
        self.tracker.update_progress(file_path, ProcessingStatus.SUCCESS)
        
        file_progress = self.tracker._files[file_path]
        assert file_progress.status == ProcessingStatus.SUCCESS
        assert file_progress.end_time is not None
        assert file_progress.processing_duration is not None
        assert file_progress.processing_duration > 0
        assert len(self.tracker._processing_times) == 1
    
    def test_update_progress_file_failure(self):
        """Test updating progress when file fails."""
        self.tracker.start_tracking(1)
        file_path = "test/file1.md"
        error_msg = "Pandoc conversion failed"
        
        self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING)
        time.sleep(0.01)
        self.tracker.update_progress(file_path, ProcessingStatus.FAILED, error_message=error_msg)
        
        file_progress = self.tracker._files[file_path]
        assert file_progress.status == ProcessingStatus.FAILED
        assert file_progress.error_message == error_msg
        assert file_progress.processing_duration is not None
    
    def test_update_progress_retry_increment(self):
        """Test that retry count increments correctly."""
        self.tracker.start_tracking(1)
        file_path = "test/file1.md"
        
        # Initial processing attempt
        self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING)
        
        # First retry
        self.tracker.update_progress(file_path, ProcessingStatus.RETRYING)
        assert self.tracker._files[file_path].retry_count == 1
        
        # Second retry  
        self.tracker.update_progress(file_path, ProcessingStatus.RETRYING)
        assert self.tracker._files[file_path].retry_count == 2
    
    def test_get_progress_report_empty(self):
        """Test progress report with no tracking started."""
        report = self.tracker.get_progress_report()
        
        assert report.total_files == 0
        assert report.completed_files == 0
        assert report.progress_percentage == 0.0
        assert report.estimated_time_remaining is None
        assert report.processing_speed == 0.0
    
    def test_get_progress_report_with_files(self):
        """Test progress report with processed files."""
        self.tracker.start_tracking(3)
        
        # Process files with different statuses
        self.tracker.update_progress("file1.md", ProcessingStatus.PROCESSING)
        time.sleep(0.01)
        self.tracker.update_progress("file1.md", ProcessingStatus.SUCCESS)
        
        self.tracker.update_progress("file2.md", ProcessingStatus.PROCESSING) 
        time.sleep(0.01)
        self.tracker.update_progress("file2.md", ProcessingStatus.FAILED, error_message="Error")
        
        self.tracker.update_progress("file3.md", ProcessingStatus.SKIPPED)
        
        report = self.tracker.get_progress_report()
        
        assert report.total_files == 3
        assert report.completed_files == 3
        assert report.success_count == 1
        assert report.failed_count == 1
        assert report.skipped_count == 1
        assert report.progress_percentage == 100.0
        assert report.error_rate == (1/3)*100  # 1 failed out of 3 completed
        assert report.processing_speed > 0
    
    def test_get_progress_report_eta_calculation(self):
        """Test ETA calculation in progress report."""
        self.tracker.start_tracking(4)
        
        # Complete 2 files
        for i in range(2):
            self.tracker.update_progress(f"file{i}.md", ProcessingStatus.PROCESSING)
            time.sleep(0.01)
            self.tracker.update_progress(f"file{i}.md", ProcessingStatus.SUCCESS)
        
        report = self.tracker.get_progress_report()
        
        assert report.estimated_time_remaining is not None
        assert report.estimated_time_remaining > 0
        assert report.processing_speed > 0
    
    def test_get_batch_statistics(self):
        """Test comprehensive batch statistics."""
        self.tracker.start_tracking(4)
        file_sizes = [1024, 2048, 512, 4096]
        
        # Process files with different outcomes
        for i, size in enumerate(file_sizes):
            file_path = f"file{i}.md"
            self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING, file_size=size)
            time.sleep(0.01)
            
            if i < 2:
                self.tracker.update_progress(file_path, ProcessingStatus.SUCCESS)
            elif i == 2:
                self.tracker.update_progress(file_path, ProcessingStatus.RETRYING)
                self.tracker.update_progress(file_path, ProcessingStatus.FAILED, error_message="Failed")
            else:
                self.tracker.update_progress(file_path, ProcessingStatus.SKIPPED)
        
        stats = self.tracker.get_batch_statistics()
        
        assert stats.total_files == 4
        assert stats.successful_files == 2
        assert stats.failed_files == 1
        assert stats.skipped_files == 1
        assert stats.retry_attempts == 1
        assert stats.total_file_size == sum(file_sizes)
        assert stats.processing_speed_fps > 0
        assert stats.processing_speed_bps > 0
        assert stats.error_rate > 0
        assert ProcessingStatus.SUCCESS in stats.status_distribution
    
    def test_get_file_status(self):
        """Test retrieving individual file status."""
        self.tracker.start_tracking(2)
        file_path = "test.md"
        
        # File not yet tracked
        assert self.tracker.get_file_status(file_path) is None
        
        # Track file
        self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING)
        file_progress = self.tracker.get_file_status(file_path)
        
        assert file_progress is not None
        assert file_progress.status == ProcessingStatus.PROCESSING
        assert file_progress.file_path == Path(file_path)
    
    def test_get_failed_files(self):
        """Test retrieving failed files list."""
        self.tracker.start_tracking(3)
        
        # Create files with different statuses
        self.tracker.update_progress("success.md", ProcessingStatus.SUCCESS)
        self.tracker.update_progress("failed1.md", ProcessingStatus.FAILED, error_message="Error 1")
        self.tracker.update_progress("failed2.md", ProcessingStatus.FAILED, error_message="Error 2")
        
        failed_files = self.tracker.get_failed_files()
        
        assert len(failed_files) == 2
        failed_paths = [fp.file_path.name for fp in failed_files]
        assert "failed1.md" in failed_paths
        assert "failed2.md" in failed_paths
        assert all(fp.status == ProcessingStatus.FAILED for fp in failed_files)
    
    def test_get_pending_files(self):
        """Test retrieving pending files list."""
        self.tracker.start_tracking(3)
        
        # Create files with different statuses
        self.tracker.update_progress("completed.md", ProcessingStatus.SUCCESS)
        self.tracker.update_progress("pending1.md", ProcessingStatus.PENDING)
        self.tracker.update_progress("pending2.md", ProcessingStatus.PENDING)
        
        pending_files = self.tracker.get_pending_files()
        
        assert len(pending_files) == 2
        pending_paths = [fp.file_path.name for fp in pending_files]
        assert "pending1.md" in pending_paths
        assert "pending2.md" in pending_paths
        assert all(fp.status == ProcessingStatus.PENDING for fp in pending_files)
    
    def test_reset(self):
        """Test resetting progress tracker state."""
        self.tracker.start_tracking(2)
        self.tracker.update_progress("test.md", ProcessingStatus.SUCCESS)
        
        # Verify tracker has data
        assert self.tracker._total_files > 0
        assert len(self.tracker._files) > 0
        assert self.tracker._start_time is not None
        
        # Reset and verify clean state
        self.tracker.reset()
        
        assert self.tracker._total_files == 0
        assert len(self.tracker._files) == 0
        assert self.tracker._start_time is None
        assert self.tracker._current_file is None
        assert len(self.tracker._processing_times) == 0
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        self.tracker.start_tracking(100)
        
        def worker(start_idx, count):
            for i in range(start_idx, start_idx + count):
                file_path = f"file{i}.md"
                self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING)
                time.sleep(0.001)  # Small delay to simulate processing
                self.tracker.update_progress(file_path, ProcessingStatus.SUCCESS)
        
        # Create multiple threads
        threads = []
        for i in range(4):
            thread = threading.Thread(target=worker, args=(i*25, 25))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify results
        report = self.tracker.get_progress_report()
        assert report.total_files == 100
        assert report.completed_files == 100
        assert report.success_count == 100
        assert len(self.tracker._files) == 100
    
    def test_format_progress_display_basic(self):
        """Test basic progress display formatting."""
        self.tracker.start_tracking(4)
        
        # Complete some files
        self.tracker.update_progress("file1.md", ProcessingStatus.SUCCESS)
        self.tracker.update_progress("file2.md", ProcessingStatus.FAILED, error_message="Error")
        self.tracker.update_progress("file3.md", ProcessingStatus.PROCESSING)
        
        display = self.tracker.format_progress_display(show_detailed=False)
        
        assert "Progress:" in display
        assert "Files:" in display
        assert "Time:" in display
        assert "Speed:" in display
        assert "file3.md" in display  # current file
        assert "75.0%" in display or "50.0%" in display  # progress percentage
    
    def test_format_progress_display_detailed(self):
        """Test detailed progress display formatting."""
        self.tracker.start_tracking(3)
        
        # Add some processing with retries
        self.tracker.update_progress("file1.md", ProcessingStatus.PROCESSING)
        self.tracker.update_progress("file1.md", ProcessingStatus.RETRYING)
        self.tracker.update_progress("file1.md", ProcessingStatus.SUCCESS)
        
        display = self.tracker.format_progress_display(show_detailed=True)
        
        assert "Detailed Statistics:" in display
        assert "Error rate:" in display
        assert "Retry attempts:" in display
        assert "Average file time:" in display
    
    def test_format_duration_helper(self):
        """Test duration formatting helper method."""
        # Test different time ranges
        assert self.tracker._format_duration(30.5) == "30.5s"
        assert self.tracker._format_duration(90) == "1m 30s"
        assert self.tracker._format_duration(3661) == "1h 1m"
        assert self.tracker._format_duration(None) == "?"
    
    def test_format_bytes_per_sec_helper(self):
        """Test bytes per second formatting helper method."""
        assert "B/s" in self.tracker._format_bytes_per_sec(500)
        assert "KB/s" in self.tracker._format_bytes_per_sec(1536)  # 1.5 KB/s
        assert "MB/s" in self.tracker._format_bytes_per_sec(1572864)  # 1.5 MB/s
        assert "GB/s" in self.tracker._format_bytes_per_sec(1610612736)  # 1.5 GB/s


class TestProgressReportNamedTuple:
    """Test cases for ProgressReport NamedTuple."""
    
    def test_progress_report_creation(self):
        """Test creating ProgressReport instances."""
        report = ProgressReport(
            total_files=10,
            completed_files=7,
            success_count=5,
            failed_count=2,
            skipped_count=0,
            progress_percentage=70.0,
            elapsed_time=120.0,
            estimated_time_remaining=51.4,
            current_file="processing.md",
            processing_speed=0.058,
            error_rate=28.6
        )
        
        assert report.total_files == 10
        assert report.completed_files == 7
        assert report.success_count == 5
        assert report.failed_count == 2
        assert report.current_file == "processing.md"
        assert report.error_rate == 28.6


class TestFileProgress:
    """Test cases for FileProgress dataclass."""
    
    def test_file_progress_creation(self):
        """Test creating FileProgress instances."""
        file_path = Path("test.md")
        progress = FileProgress(
            file_path=file_path,
            status=ProcessingStatus.PROCESSING,
            start_time=time.time(),
            file_size=2048
        )
        
        assert progress.file_path == file_path
        assert progress.status == ProcessingStatus.PROCESSING
        assert progress.start_time is not None
        assert progress.file_size == 2048
        assert progress.retry_count == 0
        assert progress.error_message is None


class TestBatchStatistics:
    """Test cases for BatchStatistics dataclass."""
    
    def test_batch_statistics_defaults(self):
        """Test BatchStatistics with default values."""
        stats = BatchStatistics()
        
        assert stats.total_files == 0
        assert stats.successful_files == 0
        assert stats.processing_speed_fps == 0.0
        assert stats.error_rate == 0.0
        assert isinstance(stats.status_distribution, dict)
    
    def test_batch_statistics_with_values(self):
        """Test BatchStatistics with specific values."""
        status_dist = {ProcessingStatus.SUCCESS: 3, ProcessingStatus.FAILED: 1}
        stats = BatchStatistics(
            total_files=4,
            successful_files=3,
            failed_files=1,
            error_rate=25.0,
            status_distribution=status_dist
        )
        
        assert stats.total_files == 4
        assert stats.successful_files == 3
        assert stats.failed_files == 1
        assert stats.error_rate == 25.0
        assert stats.status_distribution == status_dist


class TestProcessingStatus:
    """Test cases for ProcessingStatus enum."""
    
    def test_processing_status_values(self):
        """Test ProcessingStatus enum values."""
        assert ProcessingStatus.PENDING.value == "pending"
        assert ProcessingStatus.PROCESSING.value == "processing"
        assert ProcessingStatus.SUCCESS.value == "success"
        assert ProcessingStatus.FAILED.value == "failed"
        assert ProcessingStatus.SKIPPED.value == "skipped"
        assert ProcessingStatus.RETRYING.value == "retrying"
    
    def test_processing_status_comparison(self):
        """Test ProcessingStatus enum comparisons."""
        status1 = ProcessingStatus.SUCCESS
        status2 = ProcessingStatus.SUCCESS
        status3 = ProcessingStatus.FAILED
        
        assert status1 == status2
        assert status1 != status3


class TestProgressTrackerEdgeCases:
    """Test edge cases and error conditions for ProgressTracker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ProgressTracker()
    
    def test_progress_report_without_start(self):
        """Test progress report before starting tracking."""
        report = self.tracker.get_progress_report()
        
        assert report.total_files == 0
        assert report.processing_speed == 0.0
        assert report.estimated_time_remaining is None
    
    def test_batch_statistics_without_start(self):
        """Test batch statistics before starting tracking."""
        stats = self.tracker.get_batch_statistics()
        
        assert stats.total_files == 0
        assert stats.processing_speed_fps == 0.0
        assert stats.total_processing_time == 0.0
    
    def test_zero_division_handling(self):
        """Test handling of zero division in calculations."""
        self.tracker.start_tracking(0)  # Zero files
        
        report = self.tracker.get_progress_report()
        stats = self.tracker.get_batch_statistics()
        
        # Should not raise division by zero errors
        assert report.progress_percentage == 0.0
        assert stats.processing_speed_fps == 0.0
    
    def test_multiple_start_tracking_calls(self):
        """Test calling start_tracking multiple times."""
        self.tracker.start_tracking(5)
        self.tracker.update_progress("file1.md", ProcessingStatus.SUCCESS)
        
        # Start tracking again - should reset state
        self.tracker.start_tracking(3)
        
        assert self.tracker._total_files == 3
        assert len(self.tracker._files) == 0
        assert len(self.tracker._processing_times) == 0
    
    def test_update_progress_same_file_multiple_times(self):
        """Test updating progress for the same file multiple times."""
        self.tracker.start_tracking(1)
        file_path = "test.md"
        
        # Multiple updates should update the same FileProgress object
        self.tracker.update_progress(file_path, ProcessingStatus.PENDING)
        self.tracker.update_progress(file_path, ProcessingStatus.PROCESSING)
        self.tracker.update_progress(file_path, ProcessingStatus.SUCCESS)
        
        assert len(self.tracker._files) == 1
        assert self.tracker._files[file_path].status == ProcessingStatus.SUCCESS
    
    def test_negative_file_size_handling(self):
        """Test handling of invalid file sizes."""
        self.tracker.start_tracking(1)
        
        # Should handle negative or invalid file sizes gracefully
        self.tracker.update_progress("test.md", ProcessingStatus.PROCESSING, file_size=-100)
        
        file_progress = self.tracker._files["test.md"]
        assert file_progress.file_size == -100  # Store as provided, validation elsewhere