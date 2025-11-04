"""
Unit tests for the ErrorHandler module.

Tests comprehensive error classification, recovery strategy determination,
and error logging functionality.
"""

import pytest
import logging
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import asdict

from src.recovery.error_handler import (
    ErrorHandler,
    ProcessingError,
    ErrorCategory,
    ErrorSeverity,
    RecoveryAction,
    RecoveryStrategy
)


class TestProcessingError:
    """Test ProcessingError dataclass functionality."""
    
    def test_processing_error_creation(self):
        """Test basic ProcessingError creation."""
        error = ProcessingError(
            category=ErrorCategory.FILE_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Test error message"
        )
        
        assert error.category == ErrorCategory.FILE_ERROR
        assert error.severity == ErrorSeverity.ERROR
        assert error.message == "Test error message"
        assert error.timestamp > 0  # Should be set automatically
        
    def test_processing_error_with_exception(self):
        """Test ProcessingError with exception details."""
        test_exception = ValueError("Test exception")
        
        error = ProcessingError(
            category=ErrorCategory.PROCESSING_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Error with exception",
            exception=test_exception
        )
        
        assert error.exception == test_exception
        assert error.stack_trace is not None
        assert len(error.stack_trace) > 0
        
    def test_processing_error_with_context(self):
        """Test ProcessingError with context information."""
        context = {
            "file_path": "/test/file.md",
            "processing_stage": "pandoc_conversion"
        }
        
        error = ProcessingError(
            category=ErrorCategory.PROCESSING_ERROR,
            severity=ErrorSeverity.WARNING,
            message="Context test",
            context=context
        )
        
        assert error.context == context


class TestErrorHandler:
    """Test ErrorHandler functionality."""
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        return Mock(spec=logging.Logger)
    
    @pytest.fixture
    def error_handler(self, mock_logger):
        """Create ErrorHandler instance with mock logger."""
        return ErrorHandler(logger=mock_logger)
    
    def test_error_handler_initialization(self, error_handler):
        """Test ErrorHandler initialization."""
        assert error_handler.error_patterns is not None
        assert error_handler.recovery_strategies is not None
        assert error_handler.error_history == []
        assert error_handler.pattern_counters == {}
    
    def test_classify_file_not_found_error(self, error_handler):
        """Test classification of FileNotFoundError."""
        exception = FileNotFoundError("test.md not found")
        
        error = error_handler.classify_error(exception)
        
        assert error.category == ErrorCategory.FILE_ERROR
        assert error.severity == ErrorSeverity.ERROR
        assert "File not found" in error.message
        assert error.exception == exception
    
    def test_classify_permission_error(self, error_handler):
        """Test classification of PermissionError."""
        exception = PermissionError("Access denied to output directory")
        
        error = error_handler.classify_error(exception)
        
        assert error.category == ErrorCategory.FILE_ERROR
        assert error.severity == ErrorSeverity.ERROR
        assert "Permission denied" in error.message
    
    def test_classify_timeout_error(self, error_handler):
        """Test classification of timeout errors."""
        exception = TimeoutError("Operation timed out after 300 seconds")
        
        error = error_handler.classify_error(exception)
        
        assert error.category == ErrorCategory.TIMEOUT_ERROR
        assert error.severity == ErrorSeverity.WARNING
        assert "Operation timed out" in error.message
    
    def test_classify_dependency_error(self, error_handler):
        """Test classification of dependency errors."""
        exception = Exception("pandoc: command not found")
        
        error = error_handler.classify_error(exception)
        
        assert error.category == ErrorCategory.DEPENDENCY_ERROR
        assert error.severity == ErrorSeverity.FATAL
        assert "Missing dependency" in error.message
    
    def test_classify_processing_error(self, error_handler):
        """Test classification of processing errors."""
        exception = Exception("LaTeX Error: Undefined control sequence")
        
        error = error_handler.classify_error(exception)
        
        assert error.category == ErrorCategory.PROCESSING_ERROR
        assert error.severity == ErrorSeverity.ERROR
        assert "Document processing failed" in error.message
    
    def test_classify_resource_error(self, error_handler):
        """Test classification of resource errors."""
        exception = Exception("Insufficient memory for operation")
        
        error = error_handler.classify_error(exception)
        
        assert error.category == ErrorCategory.RESOURCE_ERROR
        assert error.severity == ErrorSeverity.ERROR
        assert "Resource constraint" in error.message
    
    def test_classify_generic_error(self, error_handler):
        """Test classification of generic exceptions."""
        exception = Exception("Some unexpected error")
        
        error = error_handler.classify_error(exception)
        
        assert error.category == ErrorCategory.SYSTEM_ERROR
        assert error.severity == ErrorSeverity.ERROR
        assert "Unexpected error" in error.message
    
    def test_should_retry_logic(self, error_handler):
        """Test retry decision logic for different error types."""
        # Should retry timeout errors
        timeout_error = ProcessingError(
            category=ErrorCategory.TIMEOUT_ERROR,
            severity=ErrorSeverity.WARNING,
            message="Timeout"
        )
        assert error_handler.should_retry(timeout_error) == True
        
        # Should retry system errors
        system_error = ProcessingError(
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.ERROR,
            message="System error"
        )
        assert error_handler.should_retry(system_error) == True
        
        # Should not retry fatal errors
        fatal_error = ProcessingError(
            category=ErrorCategory.DEPENDENCY_ERROR,
            severity=ErrorSeverity.FATAL,
            message="Fatal error"
        )
        assert error_handler.should_retry(fatal_error) == False
        
        # Should not retry validation errors
        validation_error = ProcessingError(
            category=ErrorCategory.VALIDATION_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Validation failed"
        )
        assert error_handler.should_retry(validation_error) == False
        
        # Should retry file permission errors
        permission_error = ProcessingError(
            category=ErrorCategory.FILE_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Permission denied access"
        )
        assert error_handler.should_retry(permission_error) == True
        
        # Should not retry other file errors
        file_error = ProcessingError(
            category=ErrorCategory.FILE_ERROR,
            severity=ErrorSeverity.ERROR,
            message="File corrupted"
        )
        assert error_handler.should_retry(file_error) == False
    
    def test_handle_error_logging(self, error_handler, mock_logger):
        """Test error handling and logging."""
        error = ProcessingError(
            category=ErrorCategory.PROCESSING_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Test processing error"
        )
        
        strategy = error_handler.handle_error(error)
        
        # Check that error was logged
        mock_logger.error.assert_called_once()
        
        # Check that error was added to history
        assert len(error_handler.error_history) == 1
        assert error_handler.error_history[0] == error
        
        # Check that pattern counter was updated
        pattern_key = "processing_error_error"
        assert error_handler.pattern_counters[pattern_key] == 1
        
        # Check that strategy was returned
        assert isinstance(strategy, RecoveryStrategy)
    
    def test_recovery_strategy_determination(self, error_handler):
        """Test recovery strategy determination for different error types."""
        # Dependency error should fail fast
        dep_error = ProcessingError(
            category=ErrorCategory.DEPENDENCY_ERROR,
            severity=ErrorSeverity.FATAL,
            message="Missing pandoc"
        )
        strategy = error_handler._determine_recovery_strategy(dep_error)
        assert strategy.action == RecoveryAction.FAIL_FAST
        
        # File error should skip
        file_error = ProcessingError(
            category=ErrorCategory.FILE_ERROR,
            severity=ErrorSeverity.ERROR,
            message="File not found"
        )
        strategy = error_handler._determine_recovery_strategy(file_error)
        assert strategy.action == RecoveryAction.SKIP_FILE
        
        # Timeout error should retry
        timeout_error = ProcessingError(
            category=ErrorCategory.TIMEOUT_ERROR,
            severity=ErrorSeverity.WARNING,
            message="Timeout occurred"
        )
        strategy = error_handler._determine_recovery_strategy(timeout_error)
        assert strategy.action == RecoveryAction.RETRY
        assert strategy.max_retries == 3
    
    def test_log_error_severity_levels(self, error_handler, mock_logger):
        """Test that different error severities use appropriate log levels."""
        # Fatal error
        fatal_error = ProcessingError(
            category=ErrorCategory.DEPENDENCY_ERROR,
            severity=ErrorSeverity.FATAL,
            message="Fatal error"
        )
        error_handler.log_error(fatal_error)
        mock_logger.critical.assert_called_once()
        
        # Reset mock
        mock_logger.reset_mock()
        
        # Regular error
        regular_error = ProcessingError(
            category=ErrorCategory.FILE_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Regular error"
        )
        error_handler.log_error(regular_error)
        mock_logger.error.assert_called_once()
        
        # Reset mock
        mock_logger.reset_mock()
        
        # Warning
        warning_error = ProcessingError(
            category=ErrorCategory.TIMEOUT_ERROR,
            severity=ErrorSeverity.WARNING,
            message="Warning error"
        )
        error_handler.log_error(warning_error)
        mock_logger.warning.assert_called_once()
        
        # Reset mock
        mock_logger.reset_mock()
        
        # Info
        info_error = ProcessingError(
            category=ErrorCategory.PROCESSING_ERROR,
            severity=ErrorSeverity.INFO,
            message="Info error"
        )
        error_handler.log_error(info_error)
        mock_logger.info.assert_called_once()
    
    def test_error_summary_generation(self, error_handler):
        """Test error summary generation."""
        # Add some test errors
        errors = [
            ProcessingError(ErrorCategory.FILE_ERROR, ErrorSeverity.ERROR, "Error 1"),
            ProcessingError(ErrorCategory.FILE_ERROR, ErrorSeverity.WARNING, "Error 2"),
            ProcessingError(ErrorCategory.PROCESSING_ERROR, ErrorSeverity.ERROR, "Error 3"),
            ProcessingError(ErrorCategory.TIMEOUT_ERROR, ErrorSeverity.WARNING, "Error 4")
        ]
        
        for error in errors:
            error_handler.error_history.append(error)
            pattern_key = f"{error.category.value}_{error.severity.value}"
            error_handler.pattern_counters[pattern_key] = error_handler.pattern_counters.get(pattern_key, 0) + 1
        
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 4
        assert summary["patterns"]["by_category"]["file_error"] == 2
        assert summary["patterns"]["by_category"]["processing_error"] == 1
        assert summary["patterns"]["by_category"]["timeout_error"] == 1
        assert summary["patterns"]["by_severity"]["error"] == 2
        assert summary["patterns"]["by_severity"]["warning"] == 2
        assert len(summary["recent_errors"]) == 4
    
    def test_error_summary_empty_history(self, error_handler):
        """Test error summary with no errors."""
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 0
        assert summary["patterns"] == {}
        assert summary["recent_errors"] == []
    
    def test_error_summary_recent_limit(self, error_handler):
        """Test error summary limits recent errors to 10."""
        # Add 15 errors
        for i in range(15):
            error = ProcessingError(
                ErrorCategory.PROCESSING_ERROR,
                ErrorSeverity.ERROR,
                f"Error {i}"
            )
            error_handler.error_history.append(error)
        
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 15
        assert len(summary["recent_errors"]) == 10
        # Check that it's the last 10 errors
        assert summary["recent_errors"][0]["message"] == "Error 5"  # 15 - 10 = 5
        assert summary["recent_errors"][-1]["message"] == "Error 14"
    
    def test_error_with_file_path(self, error_handler):
        """Test error handling with file path context."""
        file_path = Path("/test/document.md")
        
        error = ProcessingError(
            category=ErrorCategory.VALIDATION_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Invalid markdown syntax",
            file_path=file_path
        )
        
        error_handler.log_error(error)
        
        # Check that file path was included in log data
        call_args = error_handler.logger.error.call_args
        extra_data = call_args[1]['extra']
        assert extra_data['file_path'] == str(file_path)
    
    def test_multiple_error_pattern_tracking(self, error_handler):
        """Test pattern tracking across multiple similar errors."""
        # Create multiple similar errors
        for i in range(3):
            error = ProcessingError(
                ErrorCategory.PROCESSING_ERROR,
                ErrorSeverity.ERROR,
                f"Processing error {i}"
            )
            error_handler.handle_error(error)
        
        # Check pattern counter
        pattern_key = "processing_error_error"
        assert error_handler.pattern_counters[pattern_key] == 3
        
        # Check error history
        assert len(error_handler.error_history) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])