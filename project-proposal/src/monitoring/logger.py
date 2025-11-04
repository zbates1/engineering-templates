"""
Structured logging module for markdown-to-PDF pipeline.

This module provides comprehensive logging capabilities with JSON formatting,
log rotation, and contextual information for pipeline operations.
"""

import json
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import os
import sys


class LogLevel(Enum):
    """Log levels for pipeline events."""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


@dataclass
class LogContext:
    """Context information for log entries."""
    file_path: Optional[str] = None
    processing_stage: Optional[str] = None
    operation: Optional[str] = None
    duration_ms: Optional[float] = None
    batch_id: Optional[str] = None
    retry_attempt: Optional[int] = None
    additional_data: Optional[Dict[str, Any]] = None


class PipelineLogger:
    """
    Structured logger for the markdown-to-PDF processing pipeline.
    
    Provides JSON-formatted logging with automatic rotation, contextual information,
    and integration with the pipeline's monitoring and recovery systems.
    """
    
    def __init__(self, 
                 name: str = "pipeline", 
                 log_dir: Path = Path("logs"),
                 log_level: LogLevel = LogLevel.INFO,
                 max_bytes: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5,
                 enable_console: bool = True):
        """
        Initialize the pipeline logger.
        
        Args:
            name: Logger name identifier
            log_dir: Directory for log files
            log_level: Minimum log level to record
            max_bytes: Maximum bytes per log file before rotation
            backup_count: Number of backup files to keep
            enable_console: Whether to also log to console
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Python logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, log_level.value))
        
        # Clear any existing handlers to avoid duplicates
        self._logger.handlers.clear()
        
        # Set up file handler with rotation
        log_file = self.log_dir / f"{name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(self._create_formatter())
        self._logger.addHandler(file_handler)
        
        # Set up console handler if enabled
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self._create_console_formatter())
            self._logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        self._logger.propagate = False
    
    def debug(self, message: str, context: Optional[LogContext] = None) -> None:
        """Log debug message with optional context."""
        self._log(LogLevel.DEBUG, message, context)
    
    def info(self, message: str, context: Optional[LogContext] = None) -> None:
        """Log info message with optional context."""
        self._log(LogLevel.INFO, message, context)
    
    def warn(self, message: str, context: Optional[LogContext] = None) -> None:
        """Log warning message with optional context."""
        self._log(LogLevel.WARN, message, context)
    
    def error(self, message: str, context: Optional[LogContext] = None, exception: Optional[Exception] = None) -> None:
        """Log error message with optional context and exception details."""
        if exception:
            if not context:
                context = LogContext()
            if not context.additional_data:
                context.additional_data = {}
            context.additional_data['exception'] = {
                'type': type(exception).__name__,
                'message': str(exception),
                'args': exception.args
            }
        self._log(LogLevel.ERROR, message, context)
    
    def fatal(self, message: str, context: Optional[LogContext] = None, exception: Optional[Exception] = None) -> None:
        """Log fatal error message with optional context and exception details."""
        if exception:
            if not context:
                context = LogContext()
            if not context.additional_data:
                context.additional_data = {}
            context.additional_data['exception'] = {
                'type': type(exception).__name__,
                'message': str(exception),
                'args': exception.args
            }
        self._log(LogLevel.FATAL, message, context)
    
    def log_processing_start(self, file_path: Union[str, Path], batch_id: Optional[str] = None) -> None:
        """Log the start of file processing."""
        context = LogContext(
            file_path=str(file_path),
            processing_stage="start",
            operation="process_file",
            batch_id=batch_id
        )
        self.info(f"Starting processing of {file_path}", context)
    
    def log_processing_complete(self, file_path: Union[str, Path], duration_ms: float, batch_id: Optional[str] = None) -> None:
        """Log successful completion of file processing."""
        context = LogContext(
            file_path=str(file_path),
            processing_stage="complete",
            operation="process_file",
            duration_ms=duration_ms,
            batch_id=batch_id
        )
        self.info(f"Completed processing of {file_path} in {duration_ms:.1f}ms", context)
    
    def log_processing_error(self, file_path: Union[str, Path], error_message: str, 
                           stage: str = "unknown", batch_id: Optional[str] = None,
                           retry_attempt: Optional[int] = None) -> None:
        """Log processing error with context."""
        context = LogContext(
            file_path=str(file_path),
            processing_stage=stage,
            operation="process_file",
            batch_id=batch_id,
            retry_attempt=retry_attempt
        )
        self.error(f"Processing failed for {file_path}: {error_message}", context)
    
    def log_batch_start(self, batch_id: str, total_files: int) -> None:
        """Log the start of batch processing."""
        context = LogContext(
            batch_id=batch_id,
            processing_stage="start",
            operation="batch_processing",
            additional_data={"total_files": total_files}
        )
        self.info(f"Starting batch processing of {total_files} files", context)
    
    def log_batch_complete(self, batch_id: str, processed: int, failed: int, duration_ms: float) -> None:
        """Log completion of batch processing."""
        context = LogContext(
            batch_id=batch_id,
            processing_stage="complete", 
            operation="batch_processing",
            duration_ms=duration_ms,
            additional_data={
                "processed_count": processed,
                "failed_count": failed,
                "success_rate": processed / (processed + failed) if (processed + failed) > 0 else 0
            }
        )
        self.info(f"Batch processing complete: {processed} success, {failed} failed", context)
    
    def log_dependency_check(self, dependency: str, available: bool, version: Optional[str] = None) -> None:
        """Log dependency availability check."""
        context = LogContext(
            operation="dependency_check",
            processing_stage="validation",
            additional_data={
                "dependency": dependency,
                "available": available,
                "version": version
            }
        )
        status = "available" if available else "missing"
        version_info = f" (version: {version})" if version else ""
        self.info(f"Dependency {dependency} is {status}{version_info}", context)
    
    def log_retry_attempt(self, operation: str, attempt: int, max_attempts: int, 
                         delay_ms: float, error: Optional[str] = None) -> None:
        """Log retry attempt."""
        context = LogContext(
            operation=operation,
            processing_stage="retry",
            retry_attempt=attempt,
            additional_data={
                "max_attempts": max_attempts,
                "delay_ms": delay_ms,
                "error": error
            }
        )
        self.warn(f"Retry attempt {attempt}/{max_attempts} for {operation} after {delay_ms}ms delay", context)
    
    def log_checkpoint_save(self, checkpoint_id: str, files_processed: int) -> None:
        """Log checkpoint save operation."""
        context = LogContext(
            operation="checkpoint_save",
            processing_stage="checkpoint",
            additional_data={
                "checkpoint_id": checkpoint_id,
                "files_processed": files_processed
            }
        )
        self.info(f"Saved checkpoint {checkpoint_id} with {files_processed} files processed", context)
    
    def log_checkpoint_load(self, checkpoint_id: str, files_remaining: int) -> None:
        """Log checkpoint load operation."""
        context = LogContext(
            operation="checkpoint_load",
            processing_stage="checkpoint",
            additional_data={
                "checkpoint_id": checkpoint_id,
                "files_remaining": files_remaining
            }
        )
        self.info(f"Loaded checkpoint {checkpoint_id} with {files_remaining} files remaining", context)
    
    def cleanup_old_logs(self, max_age_days: int = 30) -> None:
        """
        Clean up log files older than specified age.
        
        Args:
            max_age_days: Maximum age of log files to keep
        """
        if not self.log_dir.exists():
            return
        
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        
        cleaned_count = 0
        for log_file in self.log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                self.warn(f"Failed to clean up log file {log_file}: {e}")
        
        if cleaned_count > 0:
            self.info(f"Cleaned up {cleaned_count} old log files")
    
    def _log(self, level: LogLevel, message: str, context: Optional[LogContext] = None) -> None:
        """Internal logging method."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.value,
            "logger": self.name,
            "message": message,
            "pid": os.getpid()
        }
        
        if context:
            context_dict = asdict(context)
            # Remove None values to keep logs clean
            context_dict = {k: v for k, v in context_dict.items() if v is not None}
            if context_dict:
                log_entry["context"] = context_dict
        
        # Convert to logging level and emit
        python_level = getattr(logging, level.value)
        self._logger.log(python_level, json.dumps(log_entry))
    
    def _create_formatter(self) -> logging.Formatter:
        """Create formatter for file logging (JSON format)."""
        return logging.Formatter('%(message)s')
    
    def _create_console_formatter(self) -> logging.Formatter:
        """Create formatter for console logging (human-readable)."""
        class ConsoleFormatter(logging.Formatter):
            def format(self, record):
                try:
                    # Parse JSON log entry for console display
                    log_data = json.loads(record.getMessage())
                    timestamp = log_data.get('timestamp', '')
                    level = log_data.get('level', '')
                    message = log_data.get('message', '')
                    
                    # Format for console readability
                    console_msg = f"[{timestamp[:19]}] {level:<5} {message}"
                    
                    # Add context info if available
                    if 'context' in log_data:
                        context = log_data['context']
                        if 'file_path' in context:
                            console_msg += f" | file: {context['file_path']}"
                        if 'processing_stage' in context:
                            console_msg += f" | stage: {context['processing_stage']}"
                        if 'duration_ms' in context:
                            console_msg += f" | duration: {context['duration_ms']:.1f}ms"
                    
                    return console_msg
                except (json.JSONDecodeError, KeyError):
                    # Fallback to original message if parsing fails
                    return record.getMessage()
        
        return ConsoleFormatter()


# Global logger instance for convenience
_default_logger = None

def get_logger(name: str = "pipeline", **kwargs) -> PipelineLogger:
    """
    Get or create a logger instance.
    
    Args:
        name: Logger name
        **kwargs: Additional arguments passed to PipelineLogger constructor
        
    Returns:
        PipelineLogger instance
    """
    global _default_logger
    if _default_logger is None or _default_logger.name != name:
        _default_logger = PipelineLogger(name, **kwargs)
    return _default_logger


def setup_logging(log_dir: Path = Path("logs"), 
                 log_level: LogLevel = LogLevel.INFO,
                 enable_console: bool = True) -> PipelineLogger:
    """
    Set up default logging configuration for the pipeline.
    
    Args:
        log_dir: Directory for log files
        log_level: Minimum log level to record
        enable_console: Whether to also log to console
        
    Returns:
        Configured PipelineLogger instance
    """
    return get_logger(
        "pipeline",
        log_dir=log_dir,
        log_level=log_level,
        enable_console=enable_console
    )