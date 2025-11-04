"""
Integration tests for PandocProcessor interactions with other components.
Tests the processor working with CLI argument parsing and file validation.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from src.cli.argument_parser import ArgumentParser, PipelineConfig
from src.processors.pandoc_processor import PandocProcessor, PandocConfig, ProcessingStatus


class TestPandocProcessorWithArgumentParser:
    """Test PandocProcessor integration with CLI argument parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.arg_parser = ArgumentParser()
        self.processor = PandocProcessor()
    
    def test_processor_with_parsed_config(self):
        """Test processor using configuration from argument parser."""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / 'input'
            output_dir = Path(temp_dir) / 'output'
            input_dir.mkdir()
            
            # Create test markdown file
            test_file = input_dir / 'test.md'
            test_file.write_text("# Test Document\n\nThis is a test document.")
            
            # Parse arguments
            args = ['-i', str(input_dir), '-o', str(output_dir), '--template', 'academic']
            config = self.arg_parser.parse_args(args)
            
            # Validate paths
            validation_result = self.arg_parser.validate_paths(config)
            assert validation_result.name == "VALID"
            
            # Configure processor based on parsed arguments
            pandoc_config = self.processor.configure_pandoc(config.template)
            
            # Verify configuration matches parsed arguments
            assert pandoc_config.template == 'academic'
            assert '--variable' in pandoc_config.extra_args
            assert 'fontsize:11pt' in pandoc_config.extra_args
    
    @patch('subprocess.run')
    def test_processor_with_bibliography_config(self, mock_run):
        """Test processor with bibliography configuration from CLI."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / 'input'
            output_dir = Path(temp_dir) / 'output'
            bib_dir = Path(temp_dir) / 'bib'
            
            input_dir.mkdir()
            bib_dir.mkdir()
            
            # Create test files
            test_file = input_dir / 'test.md'
            test_file.write_text("# Test Document\n\nThis is a test [@citation].")
            
            bib_file = bib_dir / 'references.bib'
            bib_file.write_text("@article{citation,\n  title={Test Article},\n  author={Author}\n}")
            
            # Parse arguments with bibliography
            args = [
                '-i', str(input_dir),
                '-o', str(output_dir),
                '--bib-dir', str(bib_dir),
                '--template', 'academic'
            ]
            config = self.arg_parser.parse_args(args)
            
            # Configure processor with bibliography
            pandoc_config = self.processor.configure_pandoc(
                config.template,
                bib_file  # Use the specific bibliography file
            )
            
            # Process file
            output_file = output_dir / 'test.pdf'
            result = self.processor.process_file(test_file, output_file, pandoc_config)
            
            assert result.status == ProcessingStatus.SUCCESS
            
            # Verify bibliography arguments were included
            call_args = mock_run.call_args[0][0]
            assert '--bibliography' in call_args
            assert str(bib_file) in call_args
            assert '--citeproc' in call_args
    
    def test_processor_with_all_cli_options(self):
        """Test processor configuration with all CLI options."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Parse comprehensive configuration
            args = [
                '-i', str(temp_dir),
                '-o', str(temp_dir) + '/output',
                '--template', 'proposal',
                '--clean',
                '--verbose',
                '--max-retries', '5',
                '--log-level', 'DEBUG'
            ]
            config = self.arg_parser.parse_args(args)
            
            # Configure processor
            pandoc_config = self.processor.configure_pandoc(config.template)
            
            # Verify all configurations are properly mapped
            assert pandoc_config.template == 'proposal'
            assert config.clean is True
            assert config.verbose is True
            assert config.max_retries == 5
            assert config.log_level == 'DEBUG'
            
            # Verify template-specific settings
            expected_args = [
                "--variable", "fontsize:12pt",
                "--variable", "geometry:margin=1.25in",
                "--variable", "documentclass:report"
            ]
            for arg in expected_args:
                assert arg in pandoc_config.extra_args


class TestPandocProcessorWithFileValidator:
    """Test PandocProcessor integration with file validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    def test_processor_validates_file_existence(self):
        """Test processor handles non-existent files gracefully."""
        non_existent_file = Path('/nonexistent/path/file.md')
        output_file = Path('/output/file.pdf')
        
        result = self.processor.process_file(non_existent_file, output_file)
        
        assert result.status == ProcessingStatus.ERROR
        assert "does not exist" in result.message
    
    def test_processor_validates_file_extension(self):
        """Test processor skips non-markdown files."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_file.write(b"This is not markdown")
            temp_path = Path(temp_file.name)
            
            try:
                result = self.processor.process_file(temp_path, Path('/output/file.pdf'))
                
                assert result.status == ProcessingStatus.SKIPPED
                assert "Not a Markdown file" in result.message
            finally:
                temp_path.unlink()
    
    @patch('subprocess.run')
    def test_processor_handles_valid_markdown_file(self, mock_run):
        """Test processor properly processes valid markdown files."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Valid Markdown\n\nThis is valid content.")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                
                try:
                    result = self.processor.process_file(temp_path, output_path)
                    
                    assert result.status == ProcessingStatus.SUCCESS
                    assert "Successfully converted" in result.message
                    assert result.processing_time > 0.0
                finally:
                    temp_path.unlink()


class TestPandocProcessorDependencyIntegration:
    """Test PandocProcessor dependency validation integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    @patch('subprocess.run')
    def test_dependency_validation_before_processing(self, mock_run):
        """Test dependency validation integrated with processing workflow."""
        # Mock dependency check (both available)
        mock_run.side_effect = [
            Mock(returncode=0, stdout="pandoc 2.19.2"),
            Mock(returncode=0, stdout="XeTeX 3.141592653"),
            Mock(returncode=0, stderr="")  # successful processing
        ]
        
        # Validate dependencies first
        deps = self.processor.validate_dependencies()
        
        assert deps.pandoc_status.name == "AVAILABLE"
        assert deps.xelatex_status.name == "AVAILABLE"
        
        # Only proceed if dependencies are available
        if (deps.pandoc_status.name == "AVAILABLE" and 
            deps.xelatex_status.name == "AVAILABLE"):
            
            with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
                temp_file.write(b"# Test Document")
                temp_path = Path(temp_file.name)
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_path = Path(temp_dir) / 'output.pdf'
                    
                    try:
                        result = self.processor.process_file(temp_path, output_path)
                        assert result.status == ProcessingStatus.SUCCESS
                    finally:
                        temp_path.unlink()
    
    @patch('subprocess.run')
    def test_processing_fails_when_dependencies_missing(self, mock_run):
        """Test processing behavior when dependencies are missing."""
        # Mock dependency check (pandoc missing)
        mock_run.side_effect = [
            FileNotFoundError(),  # pandoc not found
            Mock(returncode=0, stdout="XeTeX 3.141592653")
        ]
        
        deps = self.processor.validate_dependencies()
        
        assert deps.pandoc_status.name == "MISSING"
        assert "Pandoc not available" in deps.error_message
        
        # In a real integration, this would prevent processing
        # Here we verify the dependency check detected the issue


class TestProcessorTemplateIntegration:
    """Test PandocProcessor template system integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    def test_template_configuration_integration(self):
        """Test different template configurations produce different outputs."""
        templates = ['default', 'academic', 'proposal', 'minimal']
        
        for template in templates:
            config = self.processor.configure_pandoc(template)
            
            assert config.template == template
            
            # Verify template-specific arguments are added
            if template == 'academic':
                assert '--variable' in config.extra_args
                assert 'fontsize:11pt' in config.extra_args
            elif template == 'proposal':
                assert '--variable' in config.extra_args
                assert 'fontsize:12pt' in config.extra_args
            elif template == 'minimal':
                assert '--variable' in config.extra_args
                assert 'fontsize:10pt' in config.extra_args
    
    @patch('subprocess.run')
    def test_template_arguments_passed_to_pandoc(self, mock_run):
        """Test template arguments are correctly passed to Pandoc."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                
                # Test academic template
                config = self.processor.configure_pandoc('academic')
                
                try:
                    result = self.processor.process_file(temp_path, output_path, config)
                    
                    assert result.status == ProcessingStatus.SUCCESS
                    
                    # Verify template arguments were passed to Pandoc
                    call_args = mock_run.call_args[0][0]
                    assert '--variable' in call_args
                    assert 'fontsize:11pt' in call_args
                    assert 'documentclass:article' in call_args
                finally:
                    temp_path.unlink()


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.arg_parser = ArgumentParser()
        self.processor = PandocProcessor()
    
    @patch('subprocess.run')
    def test_complete_processing_workflow(self, mock_run):
        """Test complete workflow from CLI args to PDF generation."""
        # Mock all subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0, stdout="pandoc 2.19.2"),    # dependency check
            Mock(returncode=0, stdout="XeTeX 3.141592653"),
            Mock(returncode=0, stderr="")                   # processing
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up directory structure
            input_dir = Path(temp_dir) / 'input'
            output_dir = Path(temp_dir) / 'output'
            input_dir.mkdir()
            
            # Create test content
            test_file = input_dir / 'document.md'
            test_file.write_text("""# Test Document

This is a test document with:

- Lists
- **Bold text**
- *Italic text*

And a paragraph with some content.
""")
            
            # Step 1: Parse command line arguments
            args = ['-i', str(input_dir), '-o', str(output_dir), '--template', 'academic']
            config = self.arg_parser.parse_args(args)
            
            # Step 2: Validate paths
            validation_result = self.arg_parser.validate_paths(config)
            assert validation_result.name == "VALID"
            
            # Step 3: Validate dependencies
            deps = self.processor.validate_dependencies()
            assert deps.pandoc_status.name == "AVAILABLE"
            assert deps.xelatex_status.name == "AVAILABLE"
            
            # Step 4: Configure processor
            pandoc_config = self.processor.configure_pandoc(config.template)
            
            # Step 5: Process file
            output_file = output_dir / 'document.pdf'
            result = self.processor.process_file(test_file, output_file, pandoc_config)
            
            # Verify successful processing
            assert result.status == ProcessingStatus.SUCCESS
            assert result.input_path == test_file
            assert result.output_path == output_file
            assert result.processing_time > 0.0
            
            # Verify correct Pandoc command was built
            processing_call = mock_run.call_args_list[2]  # Third call is processing
            cmd = processing_call[0][0]
            
            assert 'pandoc' == cmd[0]
            assert '--standalone' in cmd
            assert '--pdf-engine' in cmd
            assert 'xelatex' in cmd
            assert str(test_file) in cmd
            assert str(output_file) in cmd
    
    def test_error_handling_integration(self):
        """Test error handling across integrated components."""
        # Test with invalid input directory
        args = ['-i', '/nonexistent', '-o', '/tmp/output']
        config = self.arg_parser.parse_args(args)
        
        validation_result = self.arg_parser.validate_paths(config)
        assert validation_result.name == "DOES_NOT_EXIST"
        
        # In integrated system, processing wouldn't proceed
        # This demonstrates the validation catches errors before processing
    
    @patch('subprocess.run') 
    def test_processing_with_retries_integration(self, mock_run):
        """Test processing integration with retry configuration from CLI."""
        # Mock Pandoc failure then success
        mock_run.side_effect = [
            Mock(returncode=1, stderr="LaTeX Error"),  # First attempt fails
            Mock(returncode=0, stderr="")              # Retry succeeds
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir)
            
            # Create test file
            test_file = input_dir / 'test.md'
            test_file.write_text("# Test")
            
            # Parse arguments with retry configuration
            args = ['-i', str(input_dir), '--max-retries', '3']
            config = self.arg_parser.parse_args(args)
            
            # The processor itself doesn't implement retries yet,
            # but the CLI config is available for retry logic
            assert config.max_retries == 3
            
            # This demonstrates the configuration is properly parsed
            # and available for retry implementation in pipeline runner