"""
Pipeline runner orchestrating the full markdown-to-PDF processing pipeline.

This module integrates all pipeline components with comprehensive robustness features
including error handling, retry logic, progress tracking, and health monitoring.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
import logging

from .argument_parser import PipelineConfig, ValidationResult
from ..validators.file_validator import FileValidator, ValidationResult as FileValidationResult
from ..processors.pandoc_processor import PandocProcessor, ProcessingResult, ProcessingStatus
from ..utils.file_manager import FileManager
from ..utils.template_loader import TemplateLoader
from ..monitoring.logger import PipelineLogger, LogLevel
from ..monitoring.progress_tracker import ProgressTracker, ProcessingStatus as ProgressStatus
from ..monitoring.health_checker import HealthChecker, HealthStatus, HealthCheckResult
from ..recovery.error_handler import ErrorHandler, ProcessingError, RecoveryAction
from ..recovery.retry_manager import RetryManager, RetryConfig


class PipelineStatus(Enum):
    """Overall status of pipeline execution."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchProcessingResult:
    """Result of processing multiple files."""
    total_files: int
    successful: int
    failed: int
    skipped: int
    processing_time: float
    results: List[ProcessingResult]
    errors: List[ProcessingError]


@dataclass
class PipelineStatistics:
    """Statistics about pipeline execution."""
    files_processed: int = 0
    files_successful: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    error_count: int = 0
    retry_count: int = 0


class PipelineRunner:
    """
    Orchestrates the full markdown-to-PDF processing pipeline.
    
    Integrates all pipeline components with robustness features including:
    - Health checks and dependency validation
    - Error handling and recovery strategies
    - Retry logic with exponential backoff
    - Progress tracking and reporting
    - Structured logging and monitoring
    - Batch processing with checkpointing
    """
    
    def __init__(self, config: PipelineConfig):
        """
        Initialize the pipeline runner with configuration.
        
        Args:
            config: PipelineConfig with processing parameters
        """
        self.config = config
        self.status = PipelineStatus.NOT_STARTED
        self.statistics = PipelineStatistics()
        
        # Initialize components
        # Map string log level to enum
        log_level_map = {
            'DEBUG': LogLevel.DEBUG,
            'INFO': LogLevel.INFO,
            'WARN': LogLevel.WARN,
            'ERROR': LogLevel.ERROR,
            'FATAL': LogLevel.FATAL
        }
        log_level = log_level_map.get(config.log_level, LogLevel.INFO)
        
        self.logger = PipelineLogger(
            name="pipeline_runner",
            log_level=log_level,
            log_dir=config.output_dir / "logs"
        )
        
        self.file_validator = FileValidator()
        self.pandoc_processor = PandocProcessor()
        self.file_manager = FileManager()
        self.template_loader = TemplateLoader()
        self.progress_tracker = ProgressTracker()
        self.health_checker = HealthChecker()
        self.error_handler = ErrorHandler()
        
        # Configure retry manager based on config
        retry_config = RetryConfig(
            max_attempts=config.max_retries,
            base_delay=1.0,
            max_delay=30.0
        )
        self.retry_manager = RetryManager(retry_config)
        
        from ..monitoring.logger import LogContext
        self.logger.info("Pipeline runner initialized", LogContext(
            additional_data={
                "input_dir": str(config.input_dir),
                "output_dir": str(config.output_dir),
                "template": config.template,
                "max_retries": config.max_retries
            }
        ))
    
    def run(self, config: PipelineConfig) -> BatchProcessingResult:
        """
        Execute the full processing pipeline.
        
        Args:
            config: PipelineConfig with processing parameters
            
        Returns:
            BatchProcessingResult with processing summary and details
        """
        self.status = PipelineStatus.RUNNING
        start_time = time.perf_counter()
        
        try:
            self.logger.info("Starting pipeline execution")
            
            # Phase 1: Health checks and initialization
            self._perform_health_checks()
            self._initialize_output_directory()
            
            # Phase 2: File discovery and validation
            files = self._discover_markdown_files()
            valid_files = self._validate_files(files)
            
            if not valid_files:
                self.logger.warn("No valid markdown files found for processing")
                return self._create_empty_result()
            
            # Phase 3: Process files with robustness features
            results = self._process_files_with_robustness(valid_files)
            
            # Phase 4: Generate final report
            total_time = time.perf_counter() - start_time
            batch_result = self._create_batch_result(results, total_time)
            
            self.status = PipelineStatus.COMPLETED
            self._log_final_summary(batch_result)
            
            return batch_result
            
        except Exception as e:
            self.status = PipelineStatus.FAILED
            error = self.error_handler.create_processing_error(
                original_error=e,
                context={"stage": "pipeline_execution"}
            )
            self.error_handler.log_error(error)
            
            # Return partial results if any processing occurred
            total_time = time.perf_counter() - start_time
            return BatchProcessingResult(
                total_files=0,
                successful=0,
                failed=1,
                skipped=0,
                processing_time=total_time,
                results=[],
                errors=[error]
            )
    
    def process_batch(self, files: List[Path]) -> List[ProcessingResult]:
        """
        Process a batch of markdown files.
        
        Args:
            files: List of markdown file paths to process
            
        Returns:
            List of ProcessingResult objects for each file
        """
        self.logger.info(f"Processing batch of {len(files)} files")
        
        results = []
        self.progress_tracker.start_tracking(len(files))
        
        for i, file_path in enumerate(files):
            try:
                self.logger.debug(f"Processing file {i+1}/{len(files)}: {file_path}")
                
                # Process single file with retry logic
                result = self._process_single_file_with_retry(file_path)
                results.append(result)
                
                # Update progress tracking
                status = ProgressStatus.SUCCESS if result.status == ProcessingStatus.SUCCESS else ProgressStatus.FAILED
                self.progress_tracker.update_progress(str(file_path), status)
                
                # Update statistics
                self._update_statistics(result)
                
            except Exception as e:
                error = self.error_handler.create_processing_error(
                    original_error=e,
                    context={"file": str(file_path), "batch_index": i}
                )
                
                # Create failed result
                failed_result = ProcessingResult(
                    input_path=file_path,
                    output_path=self._get_output_path(file_path),
                    status=ProcessingStatus.ERROR,
                    message=str(e),
                    error_details=str(e)
                )
                results.append(failed_result)
                
                self.progress_tracker.update_progress(str(file_path), ProgressStatus.FAILED)
                self.logger.error(f"Failed to process file: {file_path}", LogContext(additional_data={"error": str(e)}))
        
        return results
    
    def report_status(self, results: BatchProcessingResult) -> None:
        """
        Display processing summary and status report.
        
        Args:
            results: BatchProcessingResult to report on
        """
        print("\n" + "="*60)
        print("MARKDOWN TO PDF PROCESSING REPORT")
        print("="*60)
        
        print(f"Total files processed: {results.total_files}")
        print(f"Successful: {results.successful}")
        print(f"Failed: {results.failed}")
        print(f"Skipped: {results.skipped}")
        print(f"Processing time: {results.processing_time:.2f} seconds")
        
        if results.successful > 0:
            avg_time = results.processing_time / results.total_files
            print(f"Average time per file: {avg_time:.2f} seconds")
        
        print(f"Success rate: {(results.successful / results.total_files * 100):.1f}%")
        
        if results.errors:
            print(f"\nErrors encountered: {len(results.errors)}")
            for error in results.errors[:5]:  # Show first 5 errors
                print(f"  - {error.category.value}: {error.message}")
            if len(results.errors) > 5:
                print(f"  ... and {len(results.errors) - 5} more errors")
        
        # Progress report
        progress_report = self.progress_tracker.get_progress_report()
        if progress_report.total_files > 0:
            print(f"\nProgress Summary:")
            print(f"  Files completed: {progress_report.completed_files}")
            print(f"  Success rate: {progress_report.success_rate:.1f}%")
            if progress_report.estimated_time_remaining:
                print(f"  Time remaining: {progress_report.estimated_time_remaining:.1f}s")
        
        print("="*60)
    
    def _perform_health_checks(self) -> None:
        """Perform system health checks before processing."""
        self.logger.info("Performing health checks")
        
        # Perform full health check
        health_result = self.health_checker.perform_full_health_check()
        
        if health_result.overall_status == HealthStatus.CRITICAL:
            raise RuntimeError(f"Health check failed: {health_result.summary}")
        
        # Log warnings for non-critical issues
        if health_result.overall_status == HealthStatus.WARNING:
            self.logger.warn("Health check warnings detected", LogContext(
                additional_data={
                    "status": health_result.overall_status.value,
                    "summary": health_result.summary,
                    "recommendations": health_result.recommendations
                }
            ))
        
        # Check system resources specifically for disk space
        resource_status = self.health_checker.check_system_resources()
        if resource_status.disk_free_gb < 0.1:  # Less than 100MB
            self.logger.warn("Low disk space detected", LogContext(additional_data={"disk_free_gb": resource_status.disk_free_gb}))
        
        self.logger.info("Health checks completed successfully")
    
    def _initialize_output_directory(self) -> None:
        """Initialize output directory structure."""
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        (self.config.output_dir / "logs").mkdir(exist_ok=True)
        
        self.logger.info(f"Output directory initialized: {self.config.output_dir}")
    
    def _discover_markdown_files(self) -> List[Path]:
        """Discover markdown files in input directory."""
        self.logger.info(f"Discovering markdown files in: {self.config.input_dir}")
        
        files = self.file_manager.discover_md_files(self.config.input_dir)
        self.logger.info(f"Found {len(files)} markdown files")
        
        return files
    
    def _validate_files(self, files: List[Path]) -> List[Path]:
        """Validate markdown files before processing."""
        self.logger.info("Validating markdown files")
        
        valid_files = []
        for file_path in files:
            validation_result = self.file_validator.validate_markdown(file_path)
            
            if validation_result.is_valid:
                valid_files.append(file_path)
            else:
                self.logger.warn(f"Invalid file skipped: {file_path}", LogContext(
                    additional_data={"errors": validation_result.errors}
                ))
        
        self.logger.info(f"Validated {len(valid_files)} out of {len(files)} files")
        return valid_files
    
    def _process_files_with_robustness(self, files: List[Path]) -> List[ProcessingResult]:
        """Process files with full robustness features."""
        self.logger.info(f"Starting robust processing of {len(files)} files")
        
        results = []
        
        # Use checkpoint manager if available and enabled
        if hasattr(self, 'checkpoint_manager') and self.config.checkpoint_enabled:
            results = self._process_with_checkpoints(files)
        else:
            results = self.process_batch(files)
        
        return results
    
    def _process_single_file_with_retry(self, file_path: Path) -> ProcessingResult:
        """Process a single file with retry logic."""
        output_path = self._get_output_path(file_path)
        
        def processing_operation() -> ProcessingResult:
            # Load template and metadata
            template = self.template_loader.load_template(self.config.template)
            metadata = self.template_loader.load_metadata(file_path)
            processing_config = self.template_loader.merge_config(template, metadata)
            
            # Process with Pandoc
            return self.pandoc_processor.process_file(
                file_path, 
                output_path, 
                processing_config
            )
        
        # Execute with retry logic
        operation_result = self.retry_manager.execute_with_retry(processing_operation)
        
        if operation_result.success:
            return operation_result.result
        else:
            # Create failed result from retry failure
            return ProcessingResult(
                input_path=file_path,
                output_path=output_path,
                status=ProcessingStatus.ERROR,
                message=f"Processing failed after {operation_result.attempts} attempts",
                processing_time=operation_result.total_time,
                error_details=str(operation_result.error)
            )
    
    def _get_output_path(self, input_path: Path) -> Path:
        """Generate output path for input file."""
        return self.config.output_dir / f"{input_path.stem}.pdf"
    
    def _update_statistics(self, result: ProcessingResult) -> None:
        """Update pipeline statistics with result."""
        self.statistics.files_processed += 1
        self.statistics.total_processing_time += result.processing_time
        
        if result.status == ProcessingStatus.SUCCESS:
            self.statistics.files_successful += 1
        elif result.status == ProcessingStatus.FAILED:
            self.statistics.files_failed += 1
        elif result.status == ProcessingStatus.SKIPPED:
            self.statistics.files_skipped += 1
        elif result.status == ProcessingStatus.ERROR:
            self.statistics.files_failed += 1
            self.statistics.error_count += 1
        
        if self.statistics.files_processed > 0:
            self.statistics.average_processing_time = (
                self.statistics.total_processing_time / self.statistics.files_processed
            )
    
    def _create_batch_result(self, results: List[ProcessingResult], total_time: float) -> BatchProcessingResult:
        """Create BatchProcessingResult from individual results."""
        successful = sum(1 for r in results if r.status == ProcessingStatus.SUCCESS)
        failed = sum(1 for r in results if r.status in [ProcessingStatus.FAILED, ProcessingStatus.ERROR])
        skipped = sum(1 for r in results if r.status == ProcessingStatus.SKIPPED)
        
        # Extract any errors from failed results
        errors = []
        for result in results:
            if result.status in [ProcessingStatus.FAILED, ProcessingStatus.ERROR] and result.error_details:
                error = self.error_handler.create_processing_error(
                    original_error=Exception(result.error_details),
                    context={"file": str(result.input_path)}
                )
                errors.append(error)
        
        return BatchProcessingResult(
            total_files=len(results),
            successful=successful,
            failed=failed,
            skipped=skipped,
            processing_time=total_time,
            results=results,
            errors=errors
        )
    
    def _create_empty_result(self) -> BatchProcessingResult:
        """Create empty result when no files to process."""
        return BatchProcessingResult(
            total_files=0,
            successful=0,
            failed=0,
            skipped=0,
            processing_time=0.0,
            results=[],
            errors=[]
        )
    
    def _log_final_summary(self, result: BatchProcessingResult) -> None:
        """Log final processing summary."""
        self.logger.info("Pipeline execution completed", LogContext(
            additional_data={
                "total_files": result.total_files,
                "successful": result.successful,
                "failed": result.failed,
                "skipped": result.skipped,
                "processing_time": result.processing_time,
                "success_rate": result.successful / max(result.total_files, 1) * 100
            }
        ))
    
    def _process_with_checkpoints(self, files: List[Path]) -> List[ProcessingResult]:
        """Process files with checkpoint support (placeholder for future implementation)."""
        # This would integrate with checkpoint_manager when T011 is completed
        self.logger.info("Checkpoint processing not yet implemented, using standard batch processing")
        return self.process_batch(files)