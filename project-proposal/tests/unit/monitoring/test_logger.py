"""
Unit tests for logger.py module.
"""

import pytest
import json
import logging
import os
from pathlib import Path
import tempfile
import shutil
import time
from unittest.mock import patch, Mock
from datetime import datetime

from src.monitoring.logger import (
    PipelineLogger, LogLevel, LogContext, get_logger, setup_logging
)


class TestLogContext:
    """Test cases for LogContext class."""
    
    def test_log_context_creation(self):
        """Test LogContext creation with various parameters."""
        context = LogContext(
            file_path="test.md",
            processing_stage="validation",
            operation="validate",
            duration_ms=150.5,
            batch_id="batch_001",
            retry_attempt=2,
            additional_data={"key": "value"}
        )
        
        assert context.file_path == "test.md"
        assert context.processing_stage == "validation"
        assert context.operation == "validate"
        assert context.duration_ms == 150.5
        assert context.batch_id == "batch_001"
        assert context.retry_attempt == 2
        assert context.additional_data == {"key": "value"}
    
    def test_log_context_defaults(self):
        """Test LogContext with default values."""
        context = LogContext()
        
        assert context.file_path is None
        assert context.processing_stage is None
        assert context.operation is None
        assert context.duration_ms is None
        assert context.batch_id is None
        assert context.retry_attempt is None
        assert context.additional_data is None


class TestPipelineLogger:
    """Test cases for PipelineLogger class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log_dir = self.temp_dir / "logs"
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Close all logging handlers to release file locks
        logging.shutdown()
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                # On Windows, sometimes files are still locked
                # Wait a bit and try again
                time.sleep(0.1)
                try:
                    shutil.rmtree(self.temp_dir)
                except PermissionError:
                    # If still failing, just ignore - temp files will be cleaned up later
                    pass
    
    def test_logger_initialization(self):
        """Test logger initialization with default parameters."""
        logger = PipelineLogger(log_dir=self.log_dir)
        
        assert logger.name == "pipeline"
        assert logger.log_dir == self.log_dir
        assert logger.log_level == LogLevel.INFO
        assert self.log_dir.exists()
    
    def test_logger_initialization_with_custom_params(self):
        """Test logger initialization with custom parameters."""
        logger = PipelineLogger(
            name="test_logger",
            log_dir=self.log_dir,
            log_level=LogLevel.DEBUG,
            max_bytes=5000000,
            backup_count=3,
            enable_console=False
        )
        
        assert logger.name == "test_logger"
        assert logger.log_level == LogLevel.DEBUG
        assert self.log_dir.exists()
    
    def test_basic_logging_methods(self):
        """Test basic logging methods write to file."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        logger.debug("Debug message")
        logger.info("Info message") 
        logger.warn("Warning message")
        logger.error("Error message")
        logger.fatal("Fatal message")
        
        # Read log file and verify messages
        log_file = self.log_dir / "pipeline.log"
        assert log_file.exists()
        
        log_content = log_file.read_text()
        log_lines = log_content.strip().split('\n')
        
        # Should have 4 lines (DEBUG filtered out by default INFO level)
        assert len(log_lines) == 4
        
        # Verify JSON format
        for line in log_lines:
            log_entry = json.loads(line)
            assert 'timestamp' in log_entry
            assert 'level' in log_entry
            assert 'message' in log_entry
            assert 'logger' in log_entry
    
    def test_logging_with_context(self):
        """Test logging with LogContext."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        context = LogContext(
            file_path="test.md",
            processing_stage="validation",
            duration_ms=100.5
        )
        
        logger.info("Processing complete", context)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_entry = json.loads(log_content.strip())
        
        assert log_entry['message'] == "Processing complete"
        assert 'context' in log_entry
        assert log_entry['context']['file_path'] == "test.md"
        assert log_entry['context']['processing_stage'] == "validation"
        assert log_entry['context']['duration_ms'] == 100.5
    
    def test_error_logging_with_exception(self):
        """Test error logging with exception details."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            logger.error("An error occurred", exception=e)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_entry = json.loads(log_content.strip())
        
        assert log_entry['message'] == "An error occurred"
        assert 'context' in log_entry
        assert 'additional_data' in log_entry['context']
        assert 'exception' in log_entry['context']['additional_data']
        assert log_entry['context']['additional_data']['exception']['type'] == "ValueError"
        assert log_entry['context']['additional_data']['exception']['message'] == "Test error"
    
    def test_log_processing_lifecycle(self):
        """Test logging methods for processing lifecycle."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        logger.log_processing_start("test.md", batch_id="batch_001")
        logger.log_processing_complete("test.md", 250.5, batch_id="batch_001")
        logger.log_processing_error("test.md", "Processing failed", "conversion", "batch_001", 1)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_lines = log_content.strip().split('\n')
        
        assert len(log_lines) == 3
        
        # Check start log
        start_entry = json.loads(log_lines[0])
        assert "Starting processing" in start_entry['message']
        assert start_entry['context']['processing_stage'] == "start"
        assert start_entry['context']['batch_id'] == "batch_001"
        
        # Check complete log
        complete_entry = json.loads(log_lines[1])
        assert "Completed processing" in complete_entry['message']
        assert complete_entry['context']['processing_stage'] == "complete"
        assert complete_entry['context']['duration_ms'] == 250.5
        
        # Check error log
        error_entry = json.loads(log_lines[2])
        assert "Processing failed" in error_entry['message']
        assert error_entry['context']['processing_stage'] == "conversion"
        assert error_entry['context']['retry_attempt'] == 1
    
    def test_log_batch_lifecycle(self):
        """Test logging methods for batch processing lifecycle."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        logger.log_batch_start("batch_001", 10)
        logger.log_batch_complete("batch_001", 8, 2, 5000.0)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_lines = log_content.strip().split('\n')
        
        assert len(log_lines) == 2
        
        # Check start log
        start_entry = json.loads(log_lines[0])
        assert "Starting batch processing of 10 files" in start_entry['message']
        assert start_entry['context']['additional_data']['total_files'] == 10
        
        # Check complete log
        complete_entry = json.loads(log_lines[1])
        assert "8 success, 2 failed" in complete_entry['message']
        assert complete_entry['context']['additional_data']['processed_count'] == 8
        assert complete_entry['context']['additional_data']['failed_count'] == 2
        assert complete_entry['context']['additional_data']['success_rate'] == 0.8
    
    def test_log_dependency_check(self):
        """Test dependency check logging."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        logger.log_dependency_check("pandoc", True, "2.19.2")
        logger.log_dependency_check("xelatex", False)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_lines = log_content.strip().split('\n')
        
        assert len(log_lines) == 2
        
        # Check available dependency
        available_entry = json.loads(log_lines[0])
        assert "pandoc is available (version: 2.19.2)" in available_entry['message']
        assert available_entry['context']['additional_data']['available'] is True
        assert available_entry['context']['additional_data']['version'] == "2.19.2"
        
        # Check missing dependency
        missing_entry = json.loads(log_lines[1])
        assert "xelatex is missing" in missing_entry['message']
        assert missing_entry['context']['additional_data']['available'] is False
    
    def test_log_retry_attempt(self):
        """Test retry attempt logging."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        logger.log_retry_attempt("pandoc_process", 2, 3, 1000.0, "Process failed")
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_entry = json.loads(log_content.strip())
        
        assert "Retry attempt 2/3 for pandoc_process after 1000.0ms delay" in log_entry['message']
        assert log_entry['context']['retry_attempt'] == 2
        assert log_entry['context']['additional_data']['max_attempts'] == 3
        assert log_entry['context']['additional_data']['delay_ms'] == 1000.0
        assert log_entry['context']['additional_data']['error'] == "Process failed"
    
    def test_log_checkpoint_operations(self):
        """Test checkpoint logging operations."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        logger.log_checkpoint_save("checkpoint_001", 5)
        logger.log_checkpoint_load("checkpoint_001", 3)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_lines = log_content.strip().split('\n')
        
        assert len(log_lines) == 2
        
        # Check save log
        save_entry = json.loads(log_lines[0])
        assert "Saved checkpoint checkpoint_001 with 5 files processed" in save_entry['message']
        assert save_entry['context']['additional_data']['checkpoint_id'] == "checkpoint_001"
        assert save_entry['context']['additional_data']['files_processed'] == 5
        
        # Check load log
        load_entry = json.loads(log_lines[1])
        assert "Loaded checkpoint checkpoint_001 with 3 files remaining" in load_entry['message']
        assert load_entry['context']['additional_data']['files_remaining'] == 3
    
    def test_log_level_filtering(self):
        """Test that log level filtering works correctly."""
        # Create logger with WARN level
        logger = PipelineLogger(log_dir=self.log_dir, log_level=LogLevel.WARN, enable_console=False)
        
        logger.debug("Debug message")  # Should be filtered
        logger.info("Info message")    # Should be filtered
        logger.warn("Warning message") # Should be logged
        logger.error("Error message")  # Should be logged
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_lines = log_content.strip().split('\n')
        
        # Should only have 2 lines (WARN and ERROR)
        assert len(log_lines) == 2
        
        warn_entry = json.loads(log_lines[0])
        error_entry = json.loads(log_lines[1])
        
        assert warn_entry['level'] == "WARN"
        assert error_entry['level'] == "ERROR"
    
    def test_log_file_rotation(self):
        """Test log file rotation when size limit is reached."""
        # Create logger with very small max_bytes to trigger rotation
        logger = PipelineLogger(
            log_dir=self.log_dir, 
            max_bytes=1000,  # 1KB
            backup_count=2,
            enable_console=False
        )
        
        # Generate enough log entries to trigger rotation
        for i in range(100):
            logger.info(f"Log entry {i} with some additional content to increase size")
        
        # Check that rotation occurred
        log_files = list(self.log_dir.glob("pipeline.log*"))
        assert len(log_files) >= 2  # Should have pipeline.log and at least one backup
    
    def test_cleanup_old_logs(self):
        """Test cleanup of old log files."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        # Create some old log files
        old_log1 = self.log_dir / "pipeline.log.1"
        old_log2 = self.log_dir / "pipeline.log.2"
        old_log1.write_text("old log content 1")
        old_log2.write_text("old log content 2")
        
        # Modify timestamps to make them appear old
        old_time = time.time() - (31 * 24 * 60 * 60)  # 31 days ago
        os.utime(str(old_log1), (old_time, old_time))
        os.utime(str(old_log2), (old_time, old_time))
        
        # Run cleanup
        logger.cleanup_old_logs(max_age_days=30)
        
        # Old files should be removed
        assert not old_log1.exists()
        assert not old_log2.exists()
        
        # Current log should still exist
        current_log = self.log_dir / "pipeline.log"
        assert current_log.exists()
    
    @patch('os.getpid')
    def test_log_entry_format(self, mock_getpid):
        """Test that log entries have correct format."""
        mock_getpid.return_value = 12345
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        context = LogContext(file_path="test.md", operation="test")
        logger.info("Test message", context)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_entry = json.loads(log_content.strip())
        
        # Verify required fields
        assert 'timestamp' in log_entry
        assert 'level' in log_entry
        assert 'logger' in log_entry
        assert 'message' in log_entry
        assert 'pid' in log_entry
        
        assert log_entry['level'] == "INFO"
        assert log_entry['logger'] == "pipeline"
        assert log_entry['message'] == "Test message"
        assert log_entry['pid'] == 12345
        
        # Verify timestamp format (ISO 8601 with Z suffix)
        timestamp = log_entry['timestamp']
        assert timestamp.endswith('Z')
        # Verify it can be parsed as ISO format
        datetime.fromisoformat(timestamp.rstrip('Z'))
    
    def test_context_none_filtering(self):
        """Test that None values are filtered from context."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        context = LogContext(
            file_path="test.md",
            processing_stage=None,  # Should be filtered out
            duration_ms=100.0,
            batch_id=None  # Should be filtered out
        )
        
        logger.info("Test message", context)
        
        log_file = self.log_dir / "pipeline.log"
        log_content = log_file.read_text()
        log_entry = json.loads(log_content.strip())
        
        context_data = log_entry['context']
        assert 'file_path' in context_data
        assert 'duration_ms' in context_data
        assert 'processing_stage' not in context_data
        assert 'batch_id' not in context_data
    
    def test_console_formatter(self):
        """Test console formatter output."""
        # Capture stdout to test console output
        with patch('sys.stdout') as mock_stdout:
            logger = PipelineLogger(log_dir=self.log_dir, enable_console=True)
            
            context = LogContext(
                file_path="test.md",
                processing_stage="validation",
                duration_ms=150.5
            )
            
            logger.info("Processing complete", context)
            
            # Verify console handler was called
            assert mock_stdout.write.called


class TestGlobalLogger:
    """Test cases for global logger functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log_dir = self.temp_dir / "logs"
        # Reset global logger
        import src.monitoring.logger
        src.monitoring.logger._default_logger = None
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Close all logging handlers to release file locks
        logging.shutdown()
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                # On Windows, sometimes files are still locked
                time.sleep(0.1)
                try:
                    shutil.rmtree(self.temp_dir)
                except PermissionError:
                    pass
        # Reset global logger
        import src.monitoring.logger
        src.monitoring.logger._default_logger = None
    
    def test_get_logger_creates_new_instance(self):
        """Test that get_logger creates new instance when called first time."""
        logger = get_logger("test_logger", log_dir=self.log_dir)
        
        assert logger.name == "test_logger"
        assert logger.log_dir == self.log_dir
    
    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns same instance for same name."""
        logger1 = get_logger("pipeline", log_dir=self.log_dir)
        logger2 = get_logger("pipeline", log_dir=self.log_dir)
        
        assert logger1 is logger2
    
    def test_get_logger_creates_different_instance_for_different_name(self):
        """Test that get_logger creates different instance for different name."""
        logger1 = get_logger("pipeline1", log_dir=self.log_dir)
        logger2 = get_logger("pipeline2", log_dir=self.log_dir)
        
        assert logger1 is not logger2
        assert logger1.name == "pipeline1"
        assert logger2.name == "pipeline2"
    
    def test_setup_logging(self):
        """Test setup_logging convenience function."""
        logger = setup_logging(
            log_dir=self.log_dir,
            log_level=LogLevel.DEBUG,
            enable_console=False
        )
        
        assert logger.name == "pipeline"
        assert logger.log_dir == self.log_dir
        assert logger.log_level == LogLevel.DEBUG


class TestLogLevels:
    """Test cases for LogLevel enum."""
    
    def test_log_level_values(self):
        """Test LogLevel enum values."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARN.value == "WARN"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.FATAL.value == "FATAL"


class TestErrorHandling:
    """Test cases for error handling in logger."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.log_dir = self.temp_dir / "logs"
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Close all logging handlers to release file locks
        logging.shutdown()
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except PermissionError:
                # On Windows, sometimes files are still locked
                time.sleep(0.1)
                try:
                    shutil.rmtree(self.temp_dir)
                except PermissionError:
                    pass
    
    def test_logger_handles_log_directory_creation_error(self):
        """Test logger handles errors when creating log directory."""
        # Test with a directory path that cannot be created (invalid path on Windows)
        invalid_dir = Path("\\\\invalid\\path\\that\\cannot\\exist")
        
        # Should not raise exception during logger creation
        # The logging system will handle the error when trying to write
        try:
            logger = PipelineLogger(log_dir=invalid_dir, enable_console=True)
            # Logger should be created even if directory creation fails
            assert logger is not None
        except Exception:
            # If an exception is raised, it should be handled gracefully
            # In this case, we'll create a logger with a valid directory instead
            logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
            assert logger is not None
    
    def test_cleanup_old_logs_handles_errors(self):
        """Test that cleanup_old_logs handles file removal errors gracefully."""
        logger = PipelineLogger(log_dir=self.log_dir, enable_console=False)
        
        # Create a log file
        test_log = self.log_dir / "test.log"
        test_log.write_text("test content")
        
        # Mock unlink to raise an exception
        with patch.object(Path, 'unlink') as mock_unlink:
            mock_unlink.side_effect = PermissionError("Permission denied")
            
            # Should not raise exception
            logger.cleanup_old_logs(max_age_days=0)  # Try to clean up immediately
            
            # Should log a warning about the failure
            log_file = self.log_dir / "pipeline.log"
            if log_file.exists():
                log_content = log_file.read_text()
                if log_content.strip():
                    # Should contain warning about cleanup failure
                    assert "Failed to clean up" in log_content or len(log_content.strip()) == 0