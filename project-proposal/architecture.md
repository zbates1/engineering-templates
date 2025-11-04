# Project Architecture

This file defines the system structure, component interactions, and data flow for the markdown-to-PDF processing pipeline.

## Directory Structure

```
markdown-pdf-pipeline/
├── src/
│   ├── cli/             # Command-line interface and argument parsing
│   ├── processors/      # Document processing engines
│   ├── validators/      # Input validation and file checking
│   ├── utils/           # File operations and helper functions
│   ├── monitoring/      # Logging, progress tracking, health checks
│   ├── recovery/        # Error handling, retry logic, checkpointing
│   └── main.py          # CLI entry point
├── tests/
│   ├── unit/            # Unit tests for individual components
│   ├── integration/     # End-to-end pipeline tests
│   ├── robustness/      # Error handling and recovery tests
│   └── fixtures/        # Test .md files and expected outputs
├── templates/           # LaTeX templates and styles
├── examples/
│   ├── input/           # Sample .md files for testing
│   └── output/          # Example generated PDFs
├── logs/                # Pipeline execution logs and metrics
└── docs/                # Usage documentation
```

## Component Map

**Core Processing Flow:**
- `main.py` → `cli/argument_parser.py` → `cli/pipeline_runner.py`
- `pipeline_runner.py` → `validators/file_validator.py` → `processors/pandoc_processor.py`
- `pandoc_processor.py` → `utils/file_manager.py` → `utils/template_loader.py`
- `pipeline_runner.py` → `utils/batch_processor.py` → `processors/pandoc_processor.py`

**Robustness Layer:**
- `pipeline_runner.py` → `monitoring/logger.py` → `monitoring/progress_tracker.py`
- `processors/pandoc_processor.py` → `recovery/error_handler.py` → `recovery/retry_manager.py`
- `validators/file_validator.py` → `monitoring/health_checker.py`
- `utils/batch_processor.py` → `recovery/checkpoint_manager.py`

## Interface Definitions

### CLI Interfaces

**ArgumentParser**
- `parse_args() -> PipelineConfig`: Parse command-line arguments
- `validate_paths(config) -> ValidationResult`: Check input/output paths
- `display_help() -> None`: Show usage information

**PipelineRunner**
- `run(config: PipelineConfig) -> ProcessingResult`: Execute full pipeline
- `process_batch(files: List[Path]) -> List[ProcessingResult]`: Handle multiple files
- `report_status(results) -> None`: Display processing summary

### Processing Interfaces

**PandocProcessor**
- `process_file(md_path: Path, output_path: Path) -> ProcessingResult`: Convert single file
- `configure_pandoc(template, bibliography) -> PandocConfig`: Set up conversion options
- `validate_dependencies() -> DependencyCheck`: Verify Pandoc/XeLaTeX availability

**FileValidator**
- `validate_markdown(path: Path) -> ValidationResult`: Check .md file validity
- `check_references(md_path: Path) -> ReferenceCheck`: Verify image/bib file paths
- `ensure_output_directory(path: Path) -> bool`: Create output directory if needed

### Utility Interfaces

**FileManager**
- `discover_md_files(directory: Path) -> List[Path]`: Find all .md files in directory
- `copy_assets(source_dir, target_dir) -> CopyResult`: Transfer images/bibliography files
- `cleanup_temp_files() -> None`: Remove temporary processing files

**TemplateLoader**
- `load_template(name: str) -> Template`: Get LaTeX template
- `load_metadata(md_path: Path) -> Metadata`: Extract YAML frontmatter
- `merge_config(template, metadata) -> ProcessingConfig`: Combine settings

### Robustness Interfaces

**ErrorHandler**
- `handle_error(error: ProcessingError) -> RecoveryAction`: Determine recovery strategy
- `log_error(error: ProcessingError) -> None`: Record error details
- `should_retry(error: ProcessingError) -> bool`: Check if error is retryable

**RetryManager**
- `execute_with_retry(operation: Callable) -> OperationResult`: Execute with retry logic
- `configure_retry_policy(max_attempts: int, backoff: str) -> None`: Set retry parameters
- `get_retry_delay(attempt: int) -> float`: Calculate backoff delay

**CheckpointManager**
- `save_checkpoint(batch_state: BatchState) -> CheckpointId`: Save processing state
- `load_checkpoint(checkpoint_id: CheckpointId) -> BatchState`: Restore from checkpoint
- `cleanup_checkpoints() -> None`: Remove old checkpoint files

**ProgressTracker**
- `start_tracking(total_files: int) -> None`: Initialize progress tracking
- `update_progress(file_processed: str, status: ProcessingStatus) -> None`: Update progress
- `get_progress_report() -> ProgressReport`: Generate status report

**HealthChecker**
- `check_dependencies() -> HealthStatus`: Verify Pandoc, XeLaTeX availability
- `check_system_resources() -> ResourceStatus`: Monitor disk space, memory
- `validate_environment() -> EnvironmentStatus`: Check file permissions, paths

## Data Flow

### Standard Processing Pipeline

1. **Initialization Stage**
   - Parse command-line arguments (input-dir, output-dir)
   - Perform health checks on dependencies and system resources
   - Initialize logging and progress tracking
   - Validate paths and create output directories
   - Discover .md files in input directory

2. **Pre-Processing Stage**
   - Check each .md file for syntax issues
   - Verify referenced assets (images, bibliography)
   - Create batch processing checkpoint
   - Estimate processing time and resource requirements

3. **Processing Stage with Resilience**
   - Load templates and metadata for each file
   - Execute with retry logic: .md → Pandoc → XeLaTeX → PDF
   - Handle processing errors gracefully
   - Update progress tracking after each file
   - Save checkpoints for large batches

4. **Output Stage**
   - Save PDFs to output directory
   - Copy assets to maintain relative paths
   - Generate comprehensive processing report
   - Clean up temporary files and checkpoints

### Error Recovery Flow

1. **Error Detection**
   - Capture processing errors at each stage
   - Classify error types (recoverable vs fatal)
   - Log detailed error information

2. **Recovery Strategy**
   - For retryable errors: Apply exponential backoff retry
   - For file-specific errors: Skip file, continue batch
   - For system errors: Pause processing, attempt recovery
   - For fatal errors: Save progress, graceful shutdown

3. **Checkpoint Recovery**
   - Resume from last successful checkpoint
   - Replay processing from interruption point
   - Validate recovered state before continuing

## Integration Points

### Core Integration Points
- **CLI → Processor**: Command-line config must map to Pandoc options
- **Asset Management**: Images/bibliography files must be accessible during processing
- **Template System**: LaTeX templates must integrate with Pandoc pipeline
- **Batch Processing**: Individual file errors shouldn't stop entire batch

### Robustness Integration Points
- **Error Handling Pipeline**: All components must use structured error reporting
- **Retry Integration**: Processors must support retry-aware operations
- **Checkpoint System**: Batch operations must support state persistence
- **Progress Monitoring**: All long-running operations must report progress
- **Health Monitoring**: System dependencies checked before and during processing
- **Logging Integration**: All components must use centralized logging
- **Resource Management**: Processing must respect system resource limits

## Testing Requirements

### Core Functionality Tests
- **Unit Tests**: Each processor and validator component tested independently
- **Integration Tests**: Full pipeline tests with sample .md files
- **Template Tests**: Verify LaTeX template compatibility with various content types
- **CLI Tests**: Command-line argument parsing and error handling
- **Asset Tests**: Verify proper handling of images and bibliography files

### Robustness Tests
- **Error Handling Tests**: Verify proper error classification and recovery
- **Retry Logic Tests**: Test exponential backoff and retry limits
- **Checkpoint Tests**: Validate state persistence and recovery
- **Progress Tracking Tests**: Verify accurate progress reporting
- **Health Check Tests**: Test dependency and resource validation
- **Failure Mode Tests**: Simulate system failures and verify graceful degradation
- **Performance Tests**: Validate processing under resource constraints
- **Concurrency Tests**: Test batch processing with multiple files

### Test Data Requirements
- **Valid Test Files**: Sample .md files with various content types
- **Invalid Test Files**: Files with syntax errors, missing assets
- **Large Batch Tests**: Test with 100+ files for checkpoint validation
- **Resource Constraint Tests**: Test under low memory/disk space conditions
- **Network Failure Tests**: Test with unreachable bibliography sources

## Monitoring and Observability

### Logging Strategy
- **Structured Logging**: JSON format for programmatic parsing
- **Log Levels**: DEBUG, INFO, WARN, ERROR, FATAL with appropriate filtering
- **Log Rotation**: Automatic cleanup of old log files
- **Contextual Information**: Include file paths, processing stages, timing data

### Progress Tracking
- **Real-time Progress**: Live updates during batch processing
- **ETA Calculation**: Estimated time remaining based on processing speed
- **File-level Status**: Individual file success/failure tracking
- **Batch Statistics**: Total files, success rate, average processing time

### Health Monitoring
- **Dependency Checks**: Pandoc and XeLaTeX availability validation
- **Resource Monitoring**: Disk space, memory usage, CPU utilization
- **Performance Metrics**: Processing speed, error rates, retry counts
- **System Status**: Overall pipeline health and operational status

### Error Reporting
- **Error Classification**: Categorize errors by type and severity
- **Error Context**: Capture full context around error occurrence
- **Recovery Actions**: Log attempted recovery strategies
- **Error Aggregation**: Summary of common error patterns