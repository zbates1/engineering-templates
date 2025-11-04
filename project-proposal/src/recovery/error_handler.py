"""
Error handling and recovery strategies for the markdown-to-PDF pipeline.

This module provides comprehensive error classification, recovery strategy determination,
and structured error logging for robust pipeline operation.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import logging
import traceback
import time


class ErrorCategory(Enum):
    """Categories of processing errors."""
    DEPENDENCY_ERROR = "dependency_error"
    FILE_ERROR = "file_error"
    PROCESSING_ERROR = "processing_error"
    SYSTEM_ERROR = "system_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT_ERROR = "timeout_error"
    RESOURCE_ERROR = "resource_error"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RecoveryAction(Enum):
    """Possible recovery actions for different error types."""
    RETRY = "retry"
    SKIP_FILE = "skip_file"
    ABORT_BATCH = "abort_batch"
    FAIL_FAST = "fail_fast"
    IGNORE = "ignore"
    USER_INTERVENTION = "user_intervention"


@dataclass
class ProcessingError:
    """Structured representation of a processing error."""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception: Optional[Exception] = None
    file_path: Optional[Path] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0
    error_id: Optional[str] = None
    stack_trace: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        
        if self.exception and not self.stack_trace:
            self.stack_trace = traceback.format_exception(
                type(self.exception), self.exception, self.exception.__traceback__
            )


@dataclass
class RecoveryStrategy:
    """Strategy for recovering from a processing error."""
    action: RecoveryAction
    max_retries: int = 0
    retry_delay: float = 0.0
    skip_similar: bool = False
    log_level: str = "ERROR"
    user_message: Optional[str] = None
    cleanup_actions: Optional[List[Callable]] = None


class ErrorHandler:
    """
    Handles error classification, recovery strategy determination, and structured logging.
    
    This class provides the central error handling logic for the pipeline, including:
    - Error classification by category and severity
    - Recovery strategy recommendation based on error type
    - Structured error logging with context
    - Error pattern tracking for similar issues
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_patterns = self._initialize_error_patterns()
        self.recovery_strategies = self._initialize_recovery_strategies()
        self.error_history: List[ProcessingError] = []
        self.pattern_counters: Dict[str, int] = {}
        
    def handle_error(self, error: ProcessingError) -> RecoveryStrategy:
        """
        Process an error and determine the appropriate recovery strategy.
        
        Args:
            error: ProcessingError to handle
            
        Returns:
            RecoveryStrategy with recommended recovery action
        """
        # Log the error
        self.log_error(error)
        
        # Add to error history
        self.error_history.append(error)
        
        # Determine recovery strategy
        strategy = self._determine_recovery_strategy(error)
        
        # Update pattern counters
        pattern_key = f"{error.category.value}_{error.severity.value}"
        self.pattern_counters[pattern_key] = self.pattern_counters.get(pattern_key, 0) + 1
        
        return strategy
    
    def log_error(self, error: ProcessingError) -> None:
        """
        Log an error with appropriate level and structured information.
        
        Args:
            error: ProcessingError to log
        """
        log_data = {
            "error_id": error.error_id,
            "category": error.category.value,
            "severity": error.severity.value,
            "message": error.message,
            "file_path": str(error.file_path) if error.file_path else None,
            "timestamp": error.timestamp,
            "context": error.context
        }
        
        # Choose log level based on severity
        if error.severity == ErrorSeverity.FATAL:
            self.logger.critical(f"FATAL ERROR: {error.message}", extra=log_data)
        elif error.severity == ErrorSeverity.ERROR:
            self.logger.error(f"ERROR: {error.message}", extra=log_data)
        elif error.severity == ErrorSeverity.WARNING:
            self.logger.warning(f"WARNING: {error.message}", extra=log_data)
        else:
            self.logger.info(f"INFO: {error.message}", extra=log_data)
            
        # Log exception details if available
        if error.exception:
            self.logger.debug(f"Exception details: {error.exception}", exc_info=error.exception)
    
    def should_retry(self, error: ProcessingError) -> bool:
        """
        Determine if an error type is retryable.
        
        Args:
            error: ProcessingError to evaluate
            
        Returns:
            True if the error type supports retry operations
        """
        retryable_categories = {
            ErrorCategory.TIMEOUT_ERROR,
            ErrorCategory.SYSTEM_ERROR,
            ErrorCategory.RESOURCE_ERROR,
            ErrorCategory.PROCESSING_ERROR
        }
        
        # Don't retry fatal errors or validation errors
        if error.severity == ErrorSeverity.FATAL:
            return False
        
        if error.category == ErrorCategory.VALIDATION_ERROR:
            return False
        
        if error.category == ErrorCategory.FILE_ERROR:
            # Only retry if file might become available (e.g., permission issues)
            return "permission" in error.message.lower() or "access" in error.message.lower()
            
        return error.category in retryable_categories
    
    def classify_error(self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> ProcessingError:
        """
        Classify an exception into a ProcessingError with appropriate category and severity.
        
        Args:
            exception: Exception to classify
            context: Optional context information
            
        Returns:
            ProcessingError with classification
        """
        error_message = str(exception)
        error_lower = error_message.lower()
        
        # File-related errors
        if isinstance(exception, FileNotFoundError):
            return ProcessingError(
                category=ErrorCategory.FILE_ERROR,
                severity=ErrorSeverity.ERROR,
                message=f"File not found: {error_message}",
                exception=exception,
                context=context
            )
        
        if isinstance(exception, PermissionError):
            return ProcessingError(
                category=ErrorCategory.FILE_ERROR,
                severity=ErrorSeverity.ERROR,
                message=f"Permission denied: {error_message}",
                exception=exception,
                context=context
            )
        
        # Timeout errors
        if isinstance(exception, TimeoutError) or "timeout" in error_lower:
            return ProcessingError(
                category=ErrorCategory.TIMEOUT_ERROR,
                severity=ErrorSeverity.WARNING,
                message=f"Operation timed out: {error_message}",
                exception=exception,
                context=context
            )
        
        # Dependency errors
        if "pandoc" in error_lower or "xelatex" in error_lower or "command not found" in error_lower:
            return ProcessingError(
                category=ErrorCategory.DEPENDENCY_ERROR,
                severity=ErrorSeverity.FATAL,
                message=f"Missing dependency: {error_message}",
                exception=exception,
                context=context
            )
        
        # Processing errors (Pandoc/XeLaTeX specific)
        if any(keyword in error_lower for keyword in ["latex error", "compilation failed", "undefined control"]):
            return ProcessingError(
                category=ErrorCategory.PROCESSING_ERROR,
                severity=ErrorSeverity.ERROR,
                message=f"Document processing failed: {error_message}",
                exception=exception,
                context=context
            )
        
        # Memory/Resource errors
        if any(keyword in error_lower for keyword in ["memory", "disk space", "resource"]):
            return ProcessingError(
                category=ErrorCategory.RESOURCE_ERROR,
                severity=ErrorSeverity.ERROR,
                message=f"Resource constraint: {error_message}",
                exception=exception,
                context=context
            )
        
        # Default to system error
        return ProcessingError(
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.ERROR,
            message=f"Unexpected error: {error_message}",
            exception=exception,
            context=context
        )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of errors encountered during processing.
        
        Returns:
            Dictionary with error statistics and patterns
        """
        if not self.error_history:
            return {"total_errors": 0, "patterns": {}, "recent_errors": []}
        
        total_errors = len(self.error_history)
        recent_errors = self.error_history[-10:]  # Last 10 errors
        
        category_counts = {}
        severity_counts = {}
        
        for error in self.error_history:
            category_counts[error.category.value] = category_counts.get(error.category.value, 0) + 1
            severity_counts[error.severity.value] = severity_counts.get(error.severity.value, 0) + 1
        
        return {
            "total_errors": total_errors,
            "patterns": {
                "by_category": category_counts,
                "by_severity": severity_counts,
                "pattern_counters": self.pattern_counters
            },
            "recent_errors": [
                {
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "message": error.message,
                    "timestamp": error.timestamp
                }
                for error in recent_errors
            ]
        }
    
    def _determine_recovery_strategy(self, error: ProcessingError) -> RecoveryStrategy:
        """Determine recovery strategy based on error characteristics."""
        strategy_key = f"{error.category.value}_{error.severity.value}"
        
        if strategy_key in self.recovery_strategies:
            return self.recovery_strategies[strategy_key]
        
        # Default strategies by category
        if error.category == ErrorCategory.DEPENDENCY_ERROR:
            return RecoveryStrategy(
                action=RecoveryAction.FAIL_FAST,
                user_message="Missing required dependencies (Pandoc/XeLaTeX)"
            )
        
        if error.category == ErrorCategory.FILE_ERROR:
            return RecoveryStrategy(
                action=RecoveryAction.SKIP_FILE,
                log_level="WARNING"
            )
        
        if error.category == ErrorCategory.VALIDATION_ERROR:
            return RecoveryStrategy(
                action=RecoveryAction.SKIP_FILE,
                log_level="WARNING"
            )
        
        if error.category in [ErrorCategory.TIMEOUT_ERROR, ErrorCategory.SYSTEM_ERROR]:
            return RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=3,
                retry_delay=1.0
            )
        
        # Default strategy
        return RecoveryStrategy(
            action=RecoveryAction.SKIP_FILE,
            log_level="ERROR"
        )
    
    def _initialize_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize patterns for error classification."""
        return {
            "pandoc_not_found": {
                "keywords": ["pandoc", "command not found", "not recognized"],
                "category": ErrorCategory.DEPENDENCY_ERROR,
                "severity": ErrorSeverity.FATAL
            },
            "xelatex_error": {
                "keywords": ["xelatex", "latex error", "compilation failed"],
                "category": ErrorCategory.PROCESSING_ERROR,
                "severity": ErrorSeverity.ERROR
            },
            "file_not_found": {
                "keywords": ["no such file", "file not found", "does not exist"],
                "category": ErrorCategory.FILE_ERROR,
                "severity": ErrorSeverity.ERROR
            },
            "permission_denied": {
                "keywords": ["permission denied", "access denied", "cannot write"],
                "category": ErrorCategory.FILE_ERROR,
                "severity": ErrorSeverity.ERROR
            },
            "timeout": {
                "keywords": ["timeout", "timed out", "time limit"],
                "category": ErrorCategory.TIMEOUT_ERROR,
                "severity": ErrorSeverity.WARNING
            }
        }
    
    def _initialize_recovery_strategies(self) -> Dict[str, RecoveryStrategy]:
        """Initialize recovery strategies for different error types."""
        return {
            "dependency_error_fatal": RecoveryStrategy(
                action=RecoveryAction.FAIL_FAST,
                user_message="Critical dependencies missing. Check Pandoc/XeLaTeX installation."
            ),
            "file_error_error": RecoveryStrategy(
                action=RecoveryAction.SKIP_FILE,
                log_level="WARNING"
            ),
            "processing_error_error": RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=2,
                retry_delay=0.5
            ),
            "timeout_error_warning": RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=3,
                retry_delay=2.0
            ),
            "system_error_error": RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=2,
                retry_delay=1.0
            ),
            "resource_error_error": RecoveryStrategy(
                action=RecoveryAction.ABORT_BATCH,
                user_message="Insufficient system resources. Free up memory/disk space."
            ),
            "validation_error_error": RecoveryStrategy(
                action=RecoveryAction.SKIP_FILE,
                log_level="WARNING"
            )
        }