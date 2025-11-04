"""
Comprehensive unit tests for pipeline_runner.py.
Tests pipeline orchestration, robustness features, and integration points.
"""

import asyncio
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import shutil

from src.cli.pipeline_runner import (
    PipelineRunner,
    PipelineStatus,
    BatchProcessingResult,
    PipelineStatistics
)
from src.cli.argument_parser import PipelineConfig
from src.processors.pandoc_processor import ProcessingResult, ProcessingStatus
from src.monitoring.health_checker import HealthStatus, HealthCheckResult
from src.recovery.error_handler import ProcessingError, ErrorCategory, ErrorSeverity


class TestPipelineStatistics:
    """Test PipelineStatistics dataclass."""
    
    def test_default_statistics(self):
        """Test default statistics values."""
        stats = PipelineStatistics()
        assert stats.files_processed == 0
        assert stats.files_successful == 0
        assert stats.files_failed == 0
        assert stats.files_skipped == 0
        assert stats.total_processing_time == 0.0
        assert stats.average_processing_time == 0.0
        assert stats.error_count == 0
        assert stats.retry_count == 0


class TestBatchProcessingResult:
    """Test BatchProcessingResult dataclass."""
    
    def test_batch_result_creation(self):
        """Test creating batch processing result."""
        results = [
            ProcessingResult(
                input_path=Path("test1.md"),
                output_path=Path("test1.pdf"),
                status=ProcessingStatus.SUCCESS,
                processing_time=1.0
            )
        ]
        
        batch_result = BatchProcessingResult(
            total_files=1,
            successful=1,
            failed=0,
            skipped=0,
            processing_time=1.5,
            results=results,
            errors=[]
        )
        
        assert batch_result.total_files == 1
        assert batch_result.successful == 1
        assert batch_result.processing_time == 1.5
        assert len(batch_result.results) == 1


class TestPipelineRunner:
    """Test PipelineRunner class."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary input and output directories."""
        input_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())
        
        yield input_dir, output_dir
        
        # Cleanup
        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
    
    @pytest.fixture
    def config(self, temp_dirs):
        """Create test pipeline configuration."""
        input_dir, output_dir = temp_dirs
        return PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            template="default",
            verbose=True,
            max_retries=2,
            log_level="DEBUG"
        )
    
    @pytest.fixture
    def mock_components(self):
        """Mock all pipeline components."""
        with patch.multiple(
            'src.cli.pipeline_runner',
            PipelineLogger=Mock(),
            FileValidator=Mock(),
            PandocProcessor=Mock(),
            FileManager=Mock(),
            TemplateLoader=Mock(),
            ProgressTracker=Mock(),
            HealthChecker=Mock(),
            ErrorHandler=Mock(),
            RetryManager=Mock()
        ) as mocks:
            yield mocks
    
    def test_initialization(self, config, mock_components):
        """Test PipelineRunner initialization."""
        runner = PipelineRunner(config)
        
        assert runner.config == config
        assert runner.status == PipelineStatus.NOT_STARTED
        assert isinstance(runner.statistics, PipelineStatistics)
        
        # Verify components are initialized
        assert hasattr(runner, 'logger')
        assert hasattr(runner, 'file_validator')
        assert hasattr(runner, 'pandoc_processor')
        assert hasattr(runner, 'retry_manager')
    
    @patch('src.cli.pipeline_runner.PipelineLogger')
    def test_logger_configuration(self, mock_logger_class, config):
        """Test logger is configured with correct parameters."""
        runner = PipelineRunner(config)
        
        from src.monitoring.logger import LogLevel
        expected_log_level = LogLevel.DEBUG if config.log_level == 'DEBUG' else LogLevel.INFO
        mock_logger_class.assert_called_once_with(
            name="pipeline_runner",
            log_level=expected_log_level,
            log_dir=config.output_dir / "logs"
        )
    
    def test_output_path_generation(self, config, mock_components):
        """Test output path generation for input files."""
        runner = PipelineRunner(config)
        
        input_path = Path("test_document.md")
        expected_output = config.output_dir / "test_document.pdf"
        
        output_path = runner._get_output_path(input_path)
        assert output_path == expected_output
    
    def test_statistics_update_success(self, config, mock_components):
        """Test statistics update with successful result."""
        runner = PipelineRunner(config)
        
        result = ProcessingResult(
            input_path=Path("test.md"),
            output_path=Path("test.pdf"),
            status=ProcessingStatus.SUCCESS,
            processing_time=2.5
        )
        
        runner._update_statistics(result)
        
        assert runner.statistics.files_processed == 1
        assert runner.statistics.files_successful == 1
        assert runner.statistics.files_failed == 0
        assert runner.statistics.total_processing_time == 2.5
        assert runner.statistics.average_processing_time == 2.5
    
    def test_statistics_update_failure(self, config, mock_components):
        """Test statistics update with failed result."""
        runner = PipelineRunner(config)
        
        result = ProcessingResult(
            input_path=Path("test.md"),
            output_path=Path("test.pdf"),
            status=ProcessingStatus.ERROR,
            processing_time=1.0
        )
        
        runner._update_statistics(result)
        
        assert runner.statistics.files_processed == 1
        assert runner.statistics.files_successful == 0
        assert runner.statistics.files_failed == 1
        assert runner.statistics.error_count == 1
    
    def test_create_empty_result(self, config, mock_components):
        """Test creating empty result when no files to process."""
        runner = PipelineRunner(config)
        
        result = runner._create_empty_result()
        
        assert result.total_files == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.processing_time == 0.0
        assert len(result.results) == 0
        assert len(result.errors) == 0


class TestPipelineExecution:
    """Test pipeline execution workflow."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories with test files."""
        input_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())
        
        # Create test markdown files
        (input_dir / "test1.md").write_text("# Test Document 1\n\nContent here.")
        (input_dir / "test2.md").write_text("# Test Document 2\n\nMore content.")
        
        yield input_dir, output_dir
        
        # Cleanup
        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
    
    @pytest.fixture
    def config(self, temp_dirs):
        """Create test configuration."""
        input_dir, output_dir = temp_dirs
        return PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            template="default",
            max_retries=1,
            log_level="INFO"
        )
    
    def test_health_checks_success(self, config):
        """Test successful health checks."""
        with patch('src.cli.pipeline_runner.HealthChecker') as mock_health_checker:
            # Mock healthy system
            mock_instance = mock_health_checker.return_value
            mock_instance.perform_full_health_check.return_value = HealthCheckResult(
                overall_status=HealthStatus.HEALTHY,
                dependencies={},
                resources=Mock(),
                environment=Mock(),
                summary="All healthy",
                recommendations=[]
            )
            mock_instance.check_system_resources.return_value = Mock(disk_space_mb=1000)
            mock_instance.validate_environment.return_value = Mock(permissions_valid=True)
            
            runner = PipelineRunner(config)
            runner._perform_health_checks()  # Should not raise
            
            mock_instance.perform_full_health_check.assert_called_once()
    
    def test_health_checks_failure(self, config):
        """Test health check failure."""
        with patch('src.cli.pipeline_runner.HealthChecker') as mock_health_checker:
            # Mock unhealthy system
            mock_instance = mock_health_checker.return_value
            mock_instance.perform_full_health_check.return_value = HealthCheckResult(
                overall_status=HealthStatus.CRITICAL,
                dependencies={},
                resources=Mock(),
                environment=Mock(),
                summary="Pandoc not found",
                recommendations=[]
            )
            
            runner = PipelineRunner(config)
            
            with pytest.raises(RuntimeError, match="Health check failed"):
                runner._perform_health_checks()
    
    def test_file_discovery(self, config):
        """Test markdown file discovery."""
        with patch('src.cli.pipeline_runner.FileManager') as mock_file_manager:
            expected_files = [Path("test1.md"), Path("test2.md")]
            mock_instance = mock_file_manager.return_value
            mock_instance.discover_md_files.return_value = expected_files
            
            runner = PipelineRunner(config)
            files = runner._discover_markdown_files()
            
            assert files == expected_files
            mock_instance.discover_md_files.assert_called_once_with(config.input_dir)
    
    def test_file_validation(self, config):
        """Test file validation process."""
        files = [Path("valid.md"), Path("invalid.md")]
        
        with patch('src.cli.pipeline_runner.FileValidator') as mock_validator:
            mock_instance = mock_validator.return_value
            
            # Mock validation results
            def mock_validate(file_path):
                if "valid" in str(file_path):
                    return Mock(is_valid=True, errors=[])
                else:
                    return Mock(is_valid=False, errors=["syntax error"])
            
            mock_instance.validate_markdown.side_effect = mock_validate
            
            runner = PipelineRunner(config)
            valid_files = runner._validate_files(files)
            
            assert len(valid_files) == 1
            assert Path("valid.md") in valid_files
            assert Path("invalid.md") not in valid_files
    
    def test_process_single_file_success(self, config):
        """Test successful single file processing."""
        file_path = Path("test.md")
        
        with patch.multiple(
            'src.cli.pipeline_runner',
            TemplateLoader=Mock(),
            RetryManager=Mock()
        ):
            runner = PipelineRunner(config)
            
            # Mock successful processing result
            success_result = ProcessingResult(
                input_path=file_path,
                output_path=config.output_dir / "test.pdf",
                status=ProcessingStatus.SUCCESS,
                processing_time=1.5
            )
            
            # Mock retry manager to return successful operation
            runner.retry_manager.execute_with_retry.return_value = Mock(
                success=True,
                result=success_result
            )
            
            result = runner._process_single_file_with_retry(file_path)
            
            assert result == success_result
            assert runner.retry_manager.execute_with_retry.called
    
    def test_process_single_file_failure(self, config):
        """Test failed single file processing after retries."""
        file_path = Path("test.md")
        
        with patch.multiple(
            'src.cli.pipeline_runner',
            TemplateLoader=Mock(),
            RetryManager=Mock()
        ):
            runner = PipelineRunner(config)
            
            # Mock retry failure
            runner.retry_manager.execute_with_retry.return_value = Mock(
                success=False,
                attempts=3,
                total_time=5.0,
                error=Exception("Processing failed")
            )
            
            result = runner._process_single_file_with_retry(file_path)
            
            assert result.status == ProcessingStatus.ERROR
            assert "Processing failed after 3 attempts" in result.message
            assert result.processing_time == 5.0
    
    def test_batch_processing(self, config):
        """Test batch processing of multiple files."""
        files = [Path("test1.md"), Path("test2.md")]
        
        with patch.multiple(
            'src.cli.pipeline_runner',
            TemplateLoader=Mock(),
            ProgressTracker=Mock(),
            RetryManager=Mock()
        ):
            runner = PipelineRunner(config)
            
            # Mock successful processing for both files
            def mock_process_with_retry(file_path):
                return ProcessingResult(
                    input_path=file_path,
                    output_path=config.output_dir / f"{file_path.stem}.pdf",
                    status=ProcessingStatus.SUCCESS,
                    processing_time=1.0
                )
            
            runner._process_single_file_with_retry = Mock(side_effect=mock_process_with_retry)
            
            results = runner.process_batch(files)
            
            assert len(results) == 2
            assert all(r.status == ProcessingStatus.SUCCESS for r in results)
            
            # Verify progress tracking
            runner.progress_tracker.start_tracking.assert_called_once_with(2)
            assert runner.progress_tracker.update_progress.call_count == 2


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    @pytest.fixture
    def temp_setup(self):
        """Create realistic test environment."""
        input_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())
        
        # Create test files with different scenarios
        (input_dir / "valid.md").write_text("# Valid Document\n\nContent here.")
        (input_dir / "with_bib.md").write_text("# Document with Bibliography\n\nCite [@test].")
        (input_dir / "empty.md").write_text("")
        
        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            template="academic",
            max_retries=2
        )
        
        yield config, input_dir, output_dir
        
        # Cleanup
        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
    
    def test_full_pipeline_success(self, temp_setup):
        """Test complete successful pipeline execution."""
        config, input_dir, output_dir = temp_setup
        
        with patch.multiple(
            'src.cli.pipeline_runner',
            HealthChecker=Mock(),
            FileManager=Mock(),
            FileValidator=Mock(),
            TemplateLoader=Mock(),
            PandocProcessor=Mock(),
            ProgressTracker=Mock(),
            RetryManager=Mock(),
            ErrorHandler=Mock(),
            PipelineLogger=Mock()
        ) as mocks:
            
            # Setup mocks for successful execution
            health_mock = mocks['HealthChecker'].return_value
            health_mock.check_dependencies.return_value = Mock(overall_status=HealthStatus.HEALTHY)
            health_mock.check_system_resources.return_value = Mock(disk_space_mb=1000)
            health_mock.validate_environment.return_value = Mock(permissions_valid=True)
            
            file_manager_mock = mocks['FileManager'].return_value
            file_manager_mock.discover_md_files.return_value = [
                input_dir / "valid.md",
                input_dir / "with_bib.md"
            ]
            
            validator_mock = mocks['FileValidator'].return_value
            validator_mock.validate_markdown.return_value = Mock(is_valid=True, errors=[])
            
            # Mock successful processing
            retry_mock = mocks['RetryManager'].return_value
            retry_mock.execute_with_retry.return_value = Mock(
                success=True,
                result=ProcessingResult(
                    input_path=Path("test.md"),
                    output_path=Path("test.pdf"),
                    status=ProcessingStatus.SUCCESS,
                    processing_time=1.0
                )
            )
            
            runner = PipelineRunner(config)
            result = runner.run(config)
            
            assert result.successful == 2
            assert result.failed == 0
            assert runner.status == PipelineStatus.COMPLETED
    
    def test_pipeline_with_mixed_results(self, temp_setup):
        """Test pipeline with some successes and failures."""
        config, input_dir, output_dir = temp_setup
        
        with patch.multiple(
            'src.cli.pipeline_runner',
            HealthChecker=Mock(),
            FileManager=Mock(), 
            FileValidator=Mock(),
            TemplateLoader=Mock(),
            PandocProcessor=Mock(),
            ProgressTracker=Mock(),
            RetryManager=Mock(),
            ErrorHandler=Mock(),
            PipelineLogger=Mock()
        ) as mocks:
            
            # Setup mocks
            health_mock = mocks['HealthChecker'].return_value
            health_mock.check_dependencies.return_value = Mock(overall_status=HealthStatus.HEALTHY)
            health_mock.check_system_resources.return_value = Mock(disk_space_mb=1000)
            health_mock.validate_environment.return_value = Mock(permissions_valid=True)
            
            file_manager_mock = mocks['FileManager'].return_value
            file_manager_mock.discover_md_files.return_value = [
                input_dir / "valid.md",
                input_dir / "with_bib.md"
            ]
            
            validator_mock = mocks['FileValidator'].return_value
            validator_mock.validate_markdown.return_value = Mock(is_valid=True, errors=[])
            
            # Mock mixed results - first succeeds, second fails
            retry_mock = mocks['RetryManager'].return_value
            retry_results = [
                Mock(success=True, result=ProcessingResult(
                    input_path=input_dir / "valid.md",
                    output_path=output_dir / "valid.pdf",
                    status=ProcessingStatus.SUCCESS,
                    processing_time=1.0
                )),
                Mock(success=False, attempts=2, total_time=3.0,
                     error=Exception("Processing failed"))
            ]
            retry_mock.execute_with_retry.side_effect = retry_results
            
            runner = PipelineRunner(config)
            result = runner.run(config)
            
            assert result.total_files == 2
            assert result.successful == 1
            assert result.failed == 1
            assert runner.status == PipelineStatus.COMPLETED
    
    def test_pipeline_early_failure(self, temp_setup):
        """Test pipeline that fails during health checks."""
        config, input_dir, output_dir = temp_setup
        
        with patch('src.cli.pipeline_runner.HealthChecker') as mock_health_checker:
            health_mock = mock_health_checker.return_value
            health_mock.check_dependencies.return_value = Mock(
                overall_status=HealthStatus.UNHEALTHY,
                message="Pandoc not available"
            )
            
            runner = PipelineRunner(config)
            result = runner.run(config)
            
            assert result.failed == 1
            assert result.successful == 0
            assert runner.status == PipelineStatus.FAILED
            assert len(result.errors) == 1


class TestReportGeneration:
    """Test status reporting and output generation."""
    
    def test_report_status_success(self, capsys):
        """Test status reporting for successful batch."""
        results = [
            ProcessingResult(
                input_path=Path("test1.md"),
                output_path=Path("test1.pdf"),
                status=ProcessingStatus.SUCCESS,
                processing_time=1.0
            ),
            ProcessingResult(
                input_path=Path("test2.md"),
                output_path=Path("test2.pdf"),
                status=ProcessingStatus.SUCCESS,
                processing_time=1.5
            )
        ]
        
        batch_result = BatchProcessingResult(
            total_files=2,
            successful=2,
            failed=0,
            skipped=0,
            processing_time=3.0,
            results=results,
            errors=[]
        )
        
        with patch('src.cli.pipeline_runner.ProgressTracker') as mock_progress:
            mock_progress.return_value.get_progress_report.return_value = Mock(
                total_files=2,
                completed_files=2,
                success_rate=100.0,
                estimated_time_remaining=0.0
            )
            
            config = PipelineConfig(
                input_dir=Path("/tmp"),
                output_dir=Path("/tmp/output")
            )
            runner = PipelineRunner(config)
            runner.report_status(batch_result)
        
        captured = capsys.readouterr()
        assert "Total files processed: 2" in captured.out
        assert "Successful: 2" in captured.out
        assert "Failed: 0" in captured.out
        assert "Success rate: 100.0%" in captured.out
    
    def test_report_status_with_errors(self, capsys):
        """Test status reporting with errors."""
        error = ProcessingError(
            category=ErrorCategory.PROCESSING_ERROR,
            severity=ErrorSeverity.ERROR,
            message="Test error",
            file_path="test.md",
            stage="processing"
        )
        
        batch_result = BatchProcessingResult(
            total_files=1,
            successful=0,
            failed=1,
            skipped=0,
            processing_time=2.0,
            results=[],
            errors=[error]
        )
        
        with patch('src.cli.pipeline_runner.ProgressTracker') as mock_progress:
            mock_progress.return_value.get_progress_report.return_value = Mock(
                total_files=1,
                completed_files=1,
                success_rate=0.0,
                estimated_time_remaining=None
            )
            
            config = PipelineConfig(
                input_dir=Path("/tmp"),
                output_dir=Path("/tmp/output")
            )
            runner = PipelineRunner(config)
            runner.report_status(batch_result)
        
        captured = capsys.readouterr()
        assert "Errors encountered: 1" in captured.out
        assert "processing_error: Test error" in captured.out


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return PipelineConfig(
            input_dir=Path("/tmp/input"),
            output_dir=Path("/tmp/output"),
            max_retries=2
        )
    
    def test_exception_during_processing(self, config):
        """Test handling of unexpected exceptions."""
        with patch.multiple(
            'src.cli.pipeline_runner',
            HealthChecker=Mock(),
            ErrorHandler=Mock(),
            PipelineLogger=Mock()
        ) as mocks:
            
            # Make health checks raise an exception
            health_mock = mocks['HealthChecker'].return_value
            health_mock.check_dependencies.side_effect = RuntimeError("System error")
            
            error_handler_mock = mocks['ErrorHandler'].return_value
            error_handler_mock.create_processing_error.return_value = Mock()
            
            runner = PipelineRunner(config)
            result = runner.run(config)
            
            assert result.failed == 1
            assert result.successful == 0
            assert runner.status == PipelineStatus.FAILED
            
            # Verify error was logged
            error_handler_mock.create_processing_error.assert_called_once()
            error_handler_mock.log_error.assert_called_once()


# Performance and edge case tests
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_input_directory(self):
        """Test handling of empty input directory."""
        config = PipelineConfig(
            input_dir=Path("/tmp/empty"),
            output_dir=Path("/tmp/output")
        )
        
        with patch.multiple(
            'src.cli.pipeline_runner',
            HealthChecker=Mock(),
            FileManager=Mock(),
            PipelineLogger=Mock()
        ) as mocks:
            
            # Setup healthy system but no files
            health_mock = mocks['HealthChecker'].return_value
            health_mock.check_dependencies.return_value = Mock(overall_status=HealthStatus.HEALTHY)
            health_mock.check_system_resources.return_value = Mock(disk_space_mb=1000)
            health_mock.validate_environment.return_value = Mock(permissions_valid=True)
            
            file_manager_mock = mocks['FileManager'].return_value
            file_manager_mock.discover_md_files.return_value = []
            
            runner = PipelineRunner(config)
            result = runner.run(config)
            
            assert result.total_files == 0
            assert result.successful == 0
            assert result.failed == 0
            assert runner.status == PipelineStatus.COMPLETED
    
    def test_large_batch_processing(self):
        """Test processing large number of files."""
        config = PipelineConfig(
            input_dir=Path("/tmp/input"),
            output_dir=Path("/tmp/output"),
            checkpoint_enabled=True
        )
        
        # Create large file list
        large_file_list = [Path(f"test_{i}.md") for i in range(100)]
        
        with patch.multiple(
            'src.cli.pipeline_runner',
            HealthChecker=Mock(),
            FileManager=Mock(),
            FileValidator=Mock(),
            ProgressTracker=Mock(),
            RetryManager=Mock(),
            PipelineLogger=Mock()
        ) as mocks:
            
            # Setup mocks
            health_mock = mocks['HealthChecker'].return_value
            health_mock.check_dependencies.return_value = Mock(overall_status=HealthStatus.HEALTHY)
            health_mock.check_system_resources.return_value = Mock(disk_space_mb=1000)
            health_mock.validate_environment.return_value = Mock(permissions_valid=True)
            
            file_manager_mock = mocks['FileManager'].return_value
            file_manager_mock.discover_md_files.return_value = large_file_list
            
            validator_mock = mocks['FileValidator'].return_value
            validator_mock.validate_markdown.return_value = Mock(is_valid=True, errors=[])
            
            # Mock successful processing for all files
            retry_mock = mocks['RetryManager'].return_value
            retry_mock.execute_with_retry.return_value = Mock(
                success=True,
                result=ProcessingResult(
                    input_path=Path("test.md"),
                    output_path=Path("test.pdf"),
                    status=ProcessingStatus.SUCCESS,
                    processing_time=0.1
                )
            )
            
            runner = PipelineRunner(config)
            result = runner.run(config)
            
            assert result.total_files == 100
            assert result.successful == 100
            assert result.failed == 0
            
            # Verify progress tracking was initialized correctly
            mocks['ProgressTracker'].return_value.start_tracking.assert_called_with(100)