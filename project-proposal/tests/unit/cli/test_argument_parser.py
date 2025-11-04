"""
Unit tests for the CLI argument parser.
Tests argument parsing, path validation, and configuration creation.
"""

import pytest
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.cli.argument_parser import ArgumentParser, PipelineConfig, ValidationResult


class TestArgumentParser:
    """Test cases for the ArgumentParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ArgumentParser()
    
    def test_default_arguments(self):
        """Test parsing with no arguments uses defaults."""
        config = self.parser.parse_args([])
        
        assert config.input_dir == Path.cwd()
        assert config.output_dir == Path.cwd() / 'output'
        assert config.template == 'default'
        assert config.bib_dir is None
        assert config.clean is False
        assert config.verbose is False
        assert config.max_retries == 3
        assert config.checkpoint_enabled is True
        assert config.log_level == 'INFO'
    
    def test_custom_input_output_directories(self):
        """Test parsing custom input and output directories."""
        args = ['-i', '/input/path', '-o', '/output/path']
        config = self.parser.parse_args(args)
        
        assert config.input_dir == Path('/input/path')
        assert config.output_dir == Path('/output/path')
    
    def test_long_form_arguments(self):
        """Test parsing long-form argument names."""
        args = ['--input-dir', '/docs', '--output-dir', '/pdfs']
        config = self.parser.parse_args(args)
        
        assert config.input_dir == Path('/docs')
        assert config.output_dir == Path('/pdfs')
    
    def test_template_selection(self):
        """Test template argument parsing."""
        for template in ['default', 'academic', 'proposal', 'minimal']:
            args = ['--template', template]
            config = self.parser.parse_args(args)
            assert config.template == template
    
    def test_invalid_template_raises_error(self):
        """Test that invalid template raises SystemExit."""
        with pytest.raises(SystemExit):
            self.parser.parse_args(['--template', 'invalid'])
    
    def test_bibliography_directory(self):
        """Test bibliography directory argument."""
        args = ['--bib-dir', '/bibliography']
        config = self.parser.parse_args(args)
        
        assert config.bib_dir == Path('/bibliography')
    
    def test_boolean_flags(self):
        """Test boolean flag arguments."""
        args = ['--clean', '--verbose']
        config = self.parser.parse_args(args)
        
        assert config.clean is True
        assert config.verbose is True
    
    def test_max_retries_argument(self):
        """Test max retries argument parsing."""
        args = ['--max-retries', '5']
        config = self.parser.parse_args(args)
        
        assert config.max_retries == 5
    
    def test_no_checkpoint_flag(self):
        """Test no-checkpoint flag disables checkpointing."""
        args = ['--no-checkpoint']
        config = self.parser.parse_args(args)
        
        assert config.checkpoint_enabled is False
    
    def test_log_level_argument(self):
        """Test log level argument parsing."""
        for level in ['DEBUG', 'INFO', 'WARN', 'ERROR']:
            args = ['--log-level', level]
            config = self.parser.parse_args(args)
            assert config.log_level == level
    
    def test_invalid_log_level_raises_error(self):
        """Test that invalid log level raises SystemExit."""
        with pytest.raises(SystemExit):
            self.parser.parse_args(['--log-level', 'INVALID'])
    
    def test_combined_arguments(self):
        """Test parsing multiple arguments together."""
        args = [
            '-i', '/input',
            '-o', '/output', 
            '--template', 'academic',
            '--bib-dir', '/bib',
            '--clean',
            '--verbose',
            '--max-retries', '7',
            '--log-level', 'DEBUG'
        ]
        config = self.parser.parse_args(args)
        
        assert config.input_dir == Path('/input')
        assert config.output_dir == Path('/output')
        assert config.template == 'academic'
        assert config.bib_dir == Path('/bib')
        assert config.clean is True
        assert config.verbose is True
        assert config.max_retries == 7
        assert config.log_level == 'DEBUG'


class TestPathValidation:
    """Test cases for path validation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ArgumentParser()
    
    def test_validate_existing_input_directory(self):
        """Test validation of existing input directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PipelineConfig(
                input_dir=Path(temp_dir),
                output_dir=Path(temp_dir) / 'output'
            )
            
            result = self.parser.validate_paths(config)
            assert result == ValidationResult.VALID
    
    def test_validate_nonexistent_input_directory(self):
        """Test validation fails for non-existent input directory."""
        config = PipelineConfig(
            input_dir=Path('/nonexistent/path'),
            output_dir=Path('/tmp/output')
        )
        
        result = self.parser.validate_paths(config)
        assert result == ValidationResult.DOES_NOT_EXIST
    
    def test_validate_input_file_not_directory(self):
        """Test validation fails when input path is a file."""
        with tempfile.NamedTemporaryFile() as temp_file:
            config = PipelineConfig(
                input_dir=Path(temp_file.name),
                output_dir=Path('/tmp/output')
            )
            
            result = self.parser.validate_paths(config)
            assert result == ValidationResult.NOT_DIRECTORY
    
    def test_validate_creates_output_directory(self):
        """Test validation creates output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir)
            output_path = Path(temp_dir) / 'new_output'
            
            config = PipelineConfig(
                input_dir=input_path,
                output_dir=output_path
            )
            
            assert not output_path.exists()
            result = self.parser.validate_paths(config)
            assert result == ValidationResult.VALID
            assert output_path.exists()
            assert output_path.is_dir()
    
    def test_validate_bibliography_directory(self):
        """Test validation of bibliography directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            bib_dir = Path(temp_dir) / 'bibliography'
            bib_dir.mkdir()
            
            config = PipelineConfig(
                input_dir=Path(temp_dir),
                output_dir=Path(temp_dir) / 'output',
                bib_dir=bib_dir
            )
            
            result = self.parser.validate_paths(config)
            assert result == ValidationResult.VALID
    
    def test_validate_invalid_bibliography_directory(self):
        """Test validation fails for invalid bibliography directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PipelineConfig(
                input_dir=Path(temp_dir),
                output_dir=Path(temp_dir) / 'output',
                bib_dir=Path('/nonexistent/bib')
            )
            
            result = self.parser.validate_paths(config)
            assert result == ValidationResult.DOES_NOT_EXIST
    
    @patch('pathlib.Path.iterdir')
    def test_validate_permission_denied_input(self, mock_iterdir):
        """Test validation handles permission denied for input directory."""
        mock_iterdir.side_effect = PermissionError("Access denied")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PipelineConfig(
                input_dir=Path(temp_dir),
                output_dir=Path(temp_dir) / 'output'
            )
            
            result = self.parser.validate_paths(config)
            assert result == ValidationResult.PERMISSION_DENIED
    
    @patch('pathlib.Path.mkdir')
    def test_validate_permission_denied_output(self, mock_mkdir):
        """Test validation handles permission denied for output directory."""
        mock_mkdir.side_effect = PermissionError("Access denied")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PipelineConfig(
                input_dir=Path(temp_dir),
                output_dir=Path('/root/forbidden')
            )
            
            result = self.parser.validate_paths(config)
            assert result == ValidationResult.PERMISSION_DENIED


class TestPipelineConfig:
    """Test cases for the PipelineConfig dataclass."""
    
    def test_pipeline_config_creation(self):
        """Test creating PipelineConfig with all parameters."""
        config = PipelineConfig(
            input_dir=Path('/input'),
            output_dir=Path('/output'),
            template='academic',
            bib_dir=Path('/bib'),
            clean=True,
            verbose=True,
            max_retries=5,
            checkpoint_enabled=False,
            log_level='DEBUG'
        )
        
        assert config.input_dir == Path('/input')
        assert config.output_dir == Path('/output')
        assert config.template == 'academic'
        assert config.bib_dir == Path('/bib')
        assert config.clean is True
        assert config.verbose is True
        assert config.max_retries == 5
        assert config.checkpoint_enabled is False
        assert config.log_level == 'DEBUG'
    
    def test_pipeline_config_defaults(self):
        """Test PipelineConfig with default values."""
        config = PipelineConfig(
            input_dir=Path('/input'),
            output_dir=Path('/output')
        )
        
        assert config.template == 'default'
        assert config.bib_dir is None
        assert config.clean is False
        assert config.verbose is False
        assert config.max_retries == 3
        assert config.checkpoint_enabled is True
        assert config.log_level == 'INFO'


class TestDisplayHelp:
    """Test cases for help display functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ArgumentParser()
    
    @patch('builtins.print')
    def test_display_help(self, mock_print):
        """Test help display functionality."""
        with patch.object(self.parser.parser, 'print_help') as mock_help:
            self.parser.display_help()
            mock_help.assert_called_once()


class TestIntegration:
    """Integration tests for argument parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ArgumentParser()
    
    def test_parse_and_validate_success_flow(self):
        """Test successful parsing and validation flow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            args = ['-i', temp_dir, '-o', f'{temp_dir}/output']
            config = self.parser.parse_args(args)
            result = self.parser.validate_paths(config)
            
            assert result == ValidationResult.VALID
            assert config.input_dir == Path(temp_dir)
            assert (Path(temp_dir) / 'output').exists()
    
    def test_help_argument_exits(self):
        """Test that --help argument causes SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            self.parser.parse_args(['--help'])
        assert exc_info.value.code == 0