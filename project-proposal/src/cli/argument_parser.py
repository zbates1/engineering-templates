"""
Command-line argument parser for the markdown-to-PDF processing pipeline.
Provides PipelineConfig dataclass and argument parsing with path validation.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
from enum import Enum


class ValidationResult(Enum):
    """Result of path validation operations."""
    VALID = "valid"
    INVALID_PATH = "invalid_path"
    PERMISSION_DENIED = "permission_denied"
    NOT_DIRECTORY = "not_directory"
    DOES_NOT_EXIST = "does_not_exist"


@dataclass
class PipelineConfig:
    """Configuration object for the markdown processing pipeline."""
    input_dir: Path
    output_dir: Path
    template: str = "default"
    bib_dir: Optional[Path] = None
    clean: bool = False
    verbose: bool = False
    max_retries: int = 3
    checkpoint_enabled: bool = True
    log_level: str = "INFO"


class ArgumentParser:
    """Command-line argument parser for the pipeline."""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create and configure the argument parser."""
        parser = argparse.ArgumentParser(
            prog='md2pdf',
            description='Convert Markdown files to PDF using Pandoc and XeLaTeX',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  md2pdf                                    # Process current directory
  md2pdf -i ./docs -o ./pdfs               # Custom input/output directories
  md2pdf --template academic --verbose     # Use academic template with verbose output
  md2pdf --clean --max-retries 5           # Clean temp files, max 5 retries
            """
        )
        
        parser.add_argument(
            '-i', '--input-dir',
            type=Path,
            default=Path.cwd(),
            help='Input directory containing .md files (default: current directory)'
        )
        
        parser.add_argument(
            '-o', '--output-dir',
            type=Path,
            default=Path.cwd() / 'output',
            help='Output directory for PDFs (default: ./output)'
        )
        
        parser.add_argument(
            '-t', '--template',
            type=str,
            default='default',
            choices=['default', 'academic', 'proposal', 'minimal'],
            help='LaTeX template to use (default: default)'
        )
        
        parser.add_argument(
            '--bib-dir',
            type=Path,
            help='Directory containing bibliography files'
        )
        
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Remove temporary files after processing'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed processing information'
        )
        
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='Maximum number of retry attempts for failed operations (default: 3)'
        )
        
        parser.add_argument(
            '--no-checkpoint',
            action='store_true',
            help='Disable checkpoint saving for batch processing'
        )
        
        parser.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARN', 'ERROR'],
            default='INFO',
            help='Set logging level (default: INFO)'
        )
        
        return parser
    
    def parse_args(self, args: Optional[List[str]] = None) -> PipelineConfig:
        """
        Parse command-line arguments and return PipelineConfig.
        
        Args:
            args: List of arguments to parse (default: sys.argv)
            
        Returns:
            PipelineConfig object with parsed arguments
            
        Raises:
            SystemExit: If argument parsing fails
        """
        parsed_args = self.parser.parse_args(args)
        
        config = PipelineConfig(
            input_dir=parsed_args.input_dir,
            output_dir=parsed_args.output_dir,
            template=parsed_args.template,
            bib_dir=parsed_args.bib_dir,
            clean=parsed_args.clean,
            verbose=parsed_args.verbose,
            max_retries=parsed_args.max_retries,
            checkpoint_enabled=not parsed_args.no_checkpoint,
            log_level=parsed_args.log_level
        )
        
        return config
    
    def validate_paths(self, config: PipelineConfig) -> ValidationResult:
        """
        Validate input and output directory paths.
        
        Args:
            config: PipelineConfig object to validate
            
        Returns:
            ValidationResult indicating validation status
        """
        # Validate input directory
        input_result = self._validate_input_path(config.input_dir)
        if input_result != ValidationResult.VALID:
            return input_result
        
        # Validate bibliography directory if specified
        if config.bib_dir:
            bib_result = self._validate_input_path(config.bib_dir)
            if bib_result != ValidationResult.VALID:
                return bib_result
        
        # Validate/create output directory
        output_result = self._validate_output_path(config.output_dir)
        if output_result != ValidationResult.VALID:
            return output_result
        
        return ValidationResult.VALID
    
    def _validate_input_path(self, path: Path) -> ValidationResult:
        """Validate that input path exists and is readable."""
        try:
            if not path.exists():
                return ValidationResult.DOES_NOT_EXIST
            
            if not path.is_dir():
                return ValidationResult.NOT_DIRECTORY
            
            # Test read permissions
            list(path.iterdir())
            
        except PermissionError:
            return ValidationResult.PERMISSION_DENIED
        except OSError:
            return ValidationResult.INVALID_PATH
        
        return ValidationResult.VALID
    
    def _validate_output_path(self, path: Path) -> ValidationResult:
        """Validate that output path can be created and is writable."""
        try:
            # Create directory if it doesn't exist
            path.mkdir(parents=True, exist_ok=True)
            
            # Test write permissions by creating a temporary file
            test_file = path / '.write_test'
            test_file.touch()
            test_file.unlink()
            
        except PermissionError:
            return ValidationResult.PERMISSION_DENIED
        except OSError:
            return ValidationResult.INVALID_PATH
        
        return ValidationResult.VALID
    
    def display_help(self) -> None:
        """Display help information."""
        self.parser.print_help()