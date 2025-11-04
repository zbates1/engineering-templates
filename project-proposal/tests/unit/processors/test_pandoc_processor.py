"""
Unit tests for the PandocProcessor.
Tests file processing, dependency validation, and configuration management.
"""

import pytest
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

from src.processors.pandoc_processor import (
    PandocProcessor,
    PandocConfig,
    ProcessingResult,
    ProcessingStatus,
    DependencyCheck,
    DependencyStatus
)


class TestPandocProcessor:
    """Test cases for the PandocProcessor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    def test_processor_initialization(self):
        """Test processor initializes with default arguments."""
        assert self.processor.default_pandoc_args == [
            "--standalone",
            "--number-sections", 
            "--toc",
            "--highlight-style=pygments"
        ]


class TestProcessFile:
    """Test cases for the process_file method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    def test_process_nonexistent_file(self):
        """Test processing returns error for non-existent file."""
        md_path = Path('/nonexistent/file.md')
        output_path = Path('/output/file.pdf')
        
        result = self.processor.process_file(md_path, output_path)
        
        assert result.status == ProcessingStatus.ERROR
        assert result.input_path == md_path
        assert result.output_path == output_path
        assert "does not exist" in result.message
        assert result.processing_time == 0.0
    
    def test_process_non_markdown_file(self):
        """Test processing skips non-markdown files."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=True) as temp_file:
            temp_path = Path(temp_file.name)
            output_path = Path('/output/file.pdf')
            
            result = self.processor.process_file(temp_path, output_path)
            
            assert result.status == ProcessingStatus.SKIPPED
            assert "Not a Markdown file" in result.message
            assert result.processing_time == 0.0
    
    @patch('subprocess.run')
    def test_process_file_success(self, mock_run):
        """Test successful file processing."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document\n\nThis is a test.")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                
                try:
                    result = self.processor.process_file(temp_path, output_path)
                    
                    assert result.status == ProcessingStatus.SUCCESS
                    assert result.input_path == temp_path
                    assert result.output_path == output_path
                    assert "Successfully converted" in result.message
                    assert result.processing_time > 0.0
                    assert mock_run.called
                finally:
                    temp_path.unlink()
    
    @patch('subprocess.run')
    def test_process_file_pandoc_failure(self, mock_run):
        """Test handling of Pandoc processing failure."""
        mock_run.return_value = Mock(
            returncode=1,
            stderr="pandoc: error parsing markdown"
        )
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                
                try:
                    result = self.processor.process_file(temp_path, output_path)
                    
                    assert result.status == ProcessingStatus.FAILED
                    assert "Pandoc conversion failed" in result.message
                    assert result.error_details == "pandoc: error parsing markdown"
                    assert result.processing_time > 0.0
                finally:
                    temp_path.unlink()
    
    @patch('subprocess.run')
    def test_process_file_timeout(self, mock_run):
        """Test handling of processing timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=['pandoc'], timeout=300
        )
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                
                try:
                    result = self.processor.process_file(temp_path, output_path)
                    
                    assert result.status == ProcessingStatus.ERROR
                    assert "timeout" in result.message.lower()
                    assert result.error_details == "Subprocess timeout"
                    assert result.processing_time > 0.0
                finally:
                    temp_path.unlink()
    
    @patch('subprocess.run')
    def test_process_file_unexpected_error(self, mock_run):
        """Test handling of unexpected errors."""
        mock_run.side_effect = Exception("Unexpected error occurred")
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                
                try:
                    result = self.processor.process_file(temp_path, output_path)
                    
                    assert result.status == ProcessingStatus.ERROR
                    assert "Unexpected error" in result.message
                    assert result.error_details == "Unexpected error occurred"
                    assert result.processing_time > 0.0
                finally:
                    temp_path.unlink()
    
    @patch('subprocess.run')
    def test_process_file_with_custom_config(self, mock_run):
        """Test processing with custom PandocConfig."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                config = PandocConfig(
                    template="academic",
                    extra_args=["--variable", "fontsize:12pt"]
                )
                
                try:
                    result = self.processor.process_file(temp_path, output_path, config)
                    
                    assert result.status == ProcessingStatus.SUCCESS
                    mock_run.assert_called_once()
                    
                    # Verify the command includes custom arguments
                    call_args = mock_run.call_args[0][0]
                    assert "--variable" in call_args
                    assert "fontsize:12pt" in call_args
                finally:
                    temp_path.unlink()
    
    @patch('subprocess.run')
    def test_process_file_creates_output_directory(self, mock_run):
        """Test processing creates output directory if it doesn't exist."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'nested' / 'dir' / 'output.pdf'
                
                assert not output_path.parent.exists()
                
                try:
                    result = self.processor.process_file(temp_path, output_path)
                    
                    assert result.status == ProcessingStatus.SUCCESS
                    assert output_path.parent.exists()
                finally:
                    temp_path.unlink()


class TestConfigurePandoc:
    """Test cases for the configure_pandoc method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    def test_configure_default_template(self):
        """Test configuration with default template."""
        config = self.processor.configure_pandoc("default")
        
        assert config.template == "default"
        assert config.bibliography is None
        assert config.output_format == "pdf"
        assert config.engine == "xelatex"
        assert config.extra_args == []
    
    def test_configure_academic_template(self):
        """Test configuration with academic template."""
        config = self.processor.configure_pandoc("academic")
        
        assert config.template == "academic"
        expected_args = [
            "--variable", "fontsize:11pt",
            "--variable", "geometry:margin=1in",
            "--variable", "documentclass:article"
        ]
        for arg in expected_args:
            assert arg in config.extra_args
    
    def test_configure_proposal_template(self):
        """Test configuration with proposal template."""
        config = self.processor.configure_pandoc("proposal")
        
        assert config.template == "proposal"
        expected_args = [
            "--variable", "fontsize:12pt",
            "--variable", "geometry:margin=1.25in",
            "--variable", "documentclass:report"
        ]
        for arg in expected_args:
            assert arg in config.extra_args
    
    def test_configure_minimal_template(self):
        """Test configuration with minimal template."""
        config = self.processor.configure_pandoc("minimal")
        
        assert config.template == "minimal"
        expected_args = [
            "--variable", "fontsize:10pt",
            "--variable", "geometry:margin=0.8in"
        ]
        for arg in expected_args:
            assert arg in config.extra_args
    
    def test_configure_with_bibliography(self):
        """Test configuration with bibliography file."""
        with tempfile.NamedTemporaryFile(suffix='.bib', delete=False) as bib_file:
            bib_path = Path(bib_file.name)
            
            try:
                config = self.processor.configure_pandoc("default", bib_path)
                
                assert config.bibliography == bib_path
                assert "--bibliography" in config.extra_args
                assert str(bib_path) in config.extra_args
                assert "--citeproc" in config.extra_args
            finally:
                bib_path.unlink()
    
    def test_configure_with_nonexistent_bibliography(self):
        """Test configuration with non-existent bibliography file."""
        bib_path = Path('/nonexistent/file.bib')
        config = self.processor.configure_pandoc("default", bib_path)
        
        assert config.bibliography == bib_path
        # Should not add bibliography args if file doesn't exist
        assert "--bibliography" not in config.extra_args
        assert "--citeproc" not in config.extra_args


class TestValidateDependencies:
    """Test cases for the validate_dependencies method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    @patch('subprocess.run')
    def test_validate_dependencies_both_available(self, mock_run):
        """Test validation when both Pandoc and XeLaTeX are available."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="pandoc 2.19.2"),  # pandoc --version
            Mock(returncode=0, stdout="XeTeX 3.141592653")  # xelatex --version
        ]
        
        result = self.processor.validate_dependencies()
        
        assert result.pandoc_status == DependencyStatus.AVAILABLE
        assert result.xelatex_status == DependencyStatus.AVAILABLE
        assert result.pandoc_version == "2.19.2"
        assert result.xelatex_version == "available"
        assert result.error_message is None
    
    @patch('subprocess.run')
    def test_validate_dependencies_pandoc_missing(self, mock_run):
        """Test validation when Pandoc is missing."""
        mock_run.side_effect = [
            FileNotFoundError(),  # pandoc not found
            Mock(returncode=0, stdout="XeTeX 3.141592653")  # xelatex available
        ]
        
        result = self.processor.validate_dependencies()
        
        assert result.pandoc_status == DependencyStatus.MISSING
        assert result.xelatex_status == DependencyStatus.AVAILABLE
        assert result.pandoc_version is None
        assert "Pandoc not available" in result.error_message
    
    @patch('subprocess.run')
    def test_validate_dependencies_xelatex_missing(self, mock_run):
        """Test validation when XeLaTeX is missing."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="pandoc 2.19.2"),  # pandoc available
            FileNotFoundError()  # xelatex not found
        ]
        
        result = self.processor.validate_dependencies()
        
        assert result.pandoc_status == DependencyStatus.AVAILABLE
        assert result.xelatex_status == DependencyStatus.MISSING
        assert result.xelatex_version is None
        assert "XeLaTeX not available" in result.error_message
    
    @patch('subprocess.run')
    def test_validate_dependencies_both_missing(self, mock_run):
        """Test validation when both dependencies are missing."""
        mock_run.side_effect = FileNotFoundError()
        
        result = self.processor.validate_dependencies()
        
        assert result.pandoc_status == DependencyStatus.MISSING
        assert result.xelatex_status == DependencyStatus.MISSING
        assert "Pandoc not available" in result.error_message
        assert "XeLaTeX not available" in result.error_message
    
    @patch('subprocess.run')
    def test_validate_dependencies_pandoc_old_version(self, mock_run):
        """Test validation with incompatible Pandoc version."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="pandoc 1.19.2"),  # old version
            Mock(returncode=0, stdout="XeTeX 3.141592653")
        ]
        
        result = self.processor.validate_dependencies()
        
        assert result.pandoc_status == DependencyStatus.VERSION_INCOMPATIBLE
        assert result.xelatex_status == DependencyStatus.AVAILABLE
        assert result.pandoc_version == "1.19.2"
    
    @patch('subprocess.run')
    def test_validate_dependencies_command_failure(self, mock_run):
        """Test validation when version commands fail."""
        mock_run.side_effect = [
            Mock(returncode=1, stdout=""),  # pandoc command fails
            Mock(returncode=1, stdout="")   # xelatex command fails
        ]
        
        result = self.processor.validate_dependencies()
        
        assert result.pandoc_status == DependencyStatus.MISSING
        assert result.xelatex_status == DependencyStatus.MISSING
    
    @patch('subprocess.run')
    def test_validate_dependencies_timeout(self, mock_run):
        """Test validation handles command timeouts."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=['pandoc'], timeout=10)
        
        result = self.processor.validate_dependencies()
        
        assert result.pandoc_status == DependencyStatus.MISSING
        assert result.xelatex_status == DependencyStatus.MISSING


class TestBuildPandocCommand:
    """Test cases for the _build_pandoc_command method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    def test_build_basic_command(self):
        """Test building basic Pandoc command."""
        md_path = Path('/input/test.md')
        output_path = Path('/output/test.pdf')
        config = PandocConfig(template="default")
        
        cmd = self.processor._build_pandoc_command(md_path, output_path, config)
        
        assert cmd[0] == "pandoc"
        assert "--standalone" in cmd
        assert "--number-sections" in cmd
        assert "--toc" in cmd
        assert "--highlight-style=pygments" in cmd
        assert "--pdf-engine" in cmd
        assert "xelatex" in cmd
        assert str(md_path) in cmd
        assert "-o" in cmd
        assert str(output_path) in cmd
    
    def test_build_command_with_extra_args(self):
        """Test building command with extra arguments."""
        md_path = Path('/input/test.md')
        output_path = Path('/output/test.pdf')
        config = PandocConfig(
            template="academic",
            extra_args=["--variable", "fontsize:12pt", "--bibliography", "refs.bib"]
        )
        
        cmd = self.processor._build_pandoc_command(md_path, output_path, config)
        
        assert "--variable" in cmd
        assert "fontsize:12pt" in cmd
        assert "--bibliography" in cmd
        assert "refs.bib" in cmd
    
    def test_build_command_with_different_engine(self):
        """Test building command with different PDF engine."""
        md_path = Path('/input/test.md')
        output_path = Path('/output/test.pdf')
        config = PandocConfig(template="default", engine="lualatex")
        
        cmd = self.processor._build_pandoc_command(md_path, output_path, config)
        
        engine_idx = cmd.index("--pdf-engine")
        assert cmd[engine_idx + 1] == "lualatex"


class TestPandocConfig:
    """Test cases for the PandocConfig dataclass."""
    
    def test_pandoc_config_creation(self):
        """Test creating PandocConfig with all parameters."""
        config = PandocConfig(
            template="academic",
            bibliography=Path("/refs.bib"),
            output_format="pdf",
            engine="lualatex",
            extra_args=["--variable", "fontsize:12pt"]
        )
        
        assert config.template == "academic"
        assert config.bibliography == Path("/refs.bib")
        assert config.output_format == "pdf"
        assert config.engine == "lualatex"
        assert config.extra_args == ["--variable", "fontsize:12pt"]
    
    def test_pandoc_config_defaults(self):
        """Test PandocConfig with default values."""
        config = PandocConfig(template="default")
        
        assert config.template == "default"
        assert config.bibliography is None
        assert config.output_format == "pdf"
        assert config.engine == "xelatex"
        assert config.extra_args == []
    
    def test_pandoc_config_post_init(self):
        """Test PandocConfig post-init processing."""
        config = PandocConfig(template="default", extra_args=None)
        
        assert config.extra_args == []


class TestProcessingResult:
    """Test cases for the ProcessingResult dataclass."""
    
    def test_processing_result_creation(self):
        """Test creating ProcessingResult."""
        result = ProcessingResult(
            input_path=Path('/input/test.md'),
            output_path=Path('/output/test.pdf'),
            status=ProcessingStatus.SUCCESS,
            message="Conversion completed",
            processing_time=2.5,
            error_details=None
        )
        
        assert result.input_path == Path('/input/test.md')
        assert result.output_path == Path('/output/test.pdf')
        assert result.status == ProcessingStatus.SUCCESS
        assert result.message == "Conversion completed"
        assert result.processing_time == 2.5
        assert result.error_details is None
    
    def test_processing_result_defaults(self):
        """Test ProcessingResult with default values."""
        result = ProcessingResult(
            input_path=Path('/input/test.md'),
            output_path=Path('/output/test.pdf'),
            status=ProcessingStatus.FAILED
        )
        
        assert result.message == ""
        assert result.processing_time == 0.0
        assert result.error_details is None


class TestDependencyCheck:
    """Test cases for the DependencyCheck dataclass."""
    
    def test_dependency_check_creation(self):
        """Test creating DependencyCheck."""
        check = DependencyCheck(
            pandoc_status=DependencyStatus.AVAILABLE,
            xelatex_status=DependencyStatus.MISSING,
            pandoc_version="2.19.2",
            xelatex_version=None,
            error_message="XeLaTeX not found"
        )
        
        assert check.pandoc_status == DependencyStatus.AVAILABLE
        assert check.xelatex_status == DependencyStatus.MISSING
        assert check.pandoc_version == "2.19.2"
        assert check.xelatex_version is None
        assert check.error_message == "XeLaTeX not found"
    
    def test_dependency_check_defaults(self):
        """Test DependencyCheck with default values."""
        check = DependencyCheck(
            pandoc_status=DependencyStatus.AVAILABLE,
            xelatex_status=DependencyStatus.AVAILABLE
        )
        
        assert check.pandoc_version is None
        assert check.xelatex_version is None
        assert check.error_message is None


class TestIntegration:
    """Integration tests for PandocProcessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = PandocProcessor()
    
    @patch('subprocess.run')
    def test_end_to_end_processing(self, mock_run):
        """Test complete processing workflow."""
        # Mock successful dependency check
        mock_run.side_effect = [
            Mock(returncode=0, stdout="pandoc 2.19.2"),
            Mock(returncode=0, stdout="XeTeX 3.141592653"),
            Mock(returncode=0, stderr="")  # successful conversion
        ]
        
        # Validate dependencies
        deps = self.processor.validate_dependencies()
        assert deps.pandoc_status == DependencyStatus.AVAILABLE
        assert deps.xelatex_status == DependencyStatus.AVAILABLE
        
        # Configure processor
        config = self.processor.configure_pandoc("academic")
        assert config.template == "academic"
        
        # Process file
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as temp_file:
            temp_file.write(b"# Test Document\n\nContent here.")
            temp_path = Path(temp_file.name)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / 'output.pdf'
                
                try:
                    result = self.processor.process_file(temp_path, output_path, config)
                    
                    assert result.status == ProcessingStatus.SUCCESS
                    assert result.processing_time > 0.0
                    assert result.error_details is None
                finally:
                    temp_path.unlink()