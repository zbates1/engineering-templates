"""
Pandoc processor for converting Markdown files to PDF using Pandoc and XeLaTeX.
Provides the core processing functionality with dependency validation and error handling.
"""

import subprocess
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any
import sys
import shutil


class ProcessingStatus(Enum):
    """Status of file processing operation."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class DependencyStatus(Enum):
    """Status of dependency check."""
    AVAILABLE = "available"
    MISSING = "missing"
    VERSION_INCOMPATIBLE = "version_incompatible"


@dataclass
class ProcessingResult:
    """Result of processing a single markdown file."""
    input_path: Path
    output_path: Path
    status: ProcessingStatus
    message: str = ""
    processing_time: float = 0.0
    error_details: Optional[str] = None


@dataclass
class DependencyCheck:
    """Result of dependency validation."""
    pandoc_status: DependencyStatus
    xelatex_status: DependencyStatus
    pandoc_version: Optional[str] = None
    xelatex_version: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class PandocConfig:
    """Configuration for Pandoc processing."""
    template: str
    bibliography: Optional[Path] = None
    output_format: str = "pdf"
    engine: str = "xelatex"
    extra_args: List[str] = None
    
    def __post_init__(self):
        if self.extra_args is None:
            self.extra_args = []


class PandocProcessor:
    """
    Handles conversion of Markdown files to PDF using Pandoc and XeLaTeX.
    
    This class provides the core processing functionality including:
    - Single file conversion with configurable templates
    - Dependency validation for Pandoc and XeLaTeX
    - Error handling and detailed result reporting
    - Support for bibliography and citation processing
    """
    
    def __init__(self):
        self.default_pandoc_args = [
            "--standalone",
            "--number-sections",
            "--toc",
            "--highlight-style=pygments"
        ]
    
    def process_file(self, md_path: Path, output_path: Path, config: Optional[PandocConfig] = None) -> ProcessingResult:
        """
        Convert a single Markdown file to PDF.
        
        Args:
            md_path: Path to the input Markdown file
            output_path: Path where the PDF should be saved
            config: Optional PandocConfig for processing options
            
        Returns:
            ProcessingResult with conversion status and details
        """
        import time
        start_time = time.perf_counter()
        
        # Validate inputs
        if not md_path.exists():
            return ProcessingResult(
                input_path=md_path,
                output_path=output_path,
                status=ProcessingStatus.ERROR,
                message=f"Input file does not exist: {md_path}",
                processing_time=0.0
            )
        
        if not md_path.suffix.lower() == '.md':
            return ProcessingResult(
                input_path=md_path,
                output_path=output_path,
                status=ProcessingStatus.SKIPPED,
                message=f"Not a Markdown file: {md_path}",
                processing_time=0.0
            )
        
        # Use default config if none provided
        if config is None:
            config = PandocConfig(template="default")
        
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build Pandoc command
            cmd = self._build_pandoc_command(md_path, output_path, config)
            
            # Execute Pandoc
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            processing_time = time.perf_counter() - start_time
            
            if result.returncode == 0:
                return ProcessingResult(
                    input_path=md_path,
                    output_path=output_path,
                    status=ProcessingStatus.SUCCESS,
                    message=f"Successfully converted {md_path.name}",
                    processing_time=processing_time
                )
            else:
                return ProcessingResult(
                    input_path=md_path,
                    output_path=output_path,
                    status=ProcessingStatus.FAILED,
                    message=f"Pandoc conversion failed: {result.stderr}",
                    processing_time=processing_time,
                    error_details=result.stderr
                )
                
        except subprocess.TimeoutExpired:
            return ProcessingResult(
                input_path=md_path,
                output_path=output_path,
                status=ProcessingStatus.ERROR,
                message=f"Processing timeout after 5 minutes",
                processing_time=time.perf_counter() - start_time,
                error_details="Subprocess timeout"
            )
        except Exception as e:
            return ProcessingResult(
                input_path=md_path,
                output_path=output_path,
                status=ProcessingStatus.ERROR,
                message=f"Unexpected error: {str(e)}",
                processing_time=time.perf_counter() - start_time,
                error_details=str(e)
            )
    
    def configure_pandoc(self, template: str, bibliography: Optional[Path] = None) -> PandocConfig:
        """
        Create a PandocConfig with specified template and bibliography.
        
        Args:
            template: Name of the LaTeX template to use
            bibliography: Optional path to bibliography file
            
        Returns:
            Configured PandocConfig object
        """
        config = PandocConfig(
            template=template,
            bibliography=bibliography,
            output_format="pdf",
            engine="xelatex"
        )
        
        # Add template-specific arguments
        if template == "academic":
            config.extra_args.extend([
                "--variable", "fontsize:11pt",
                "--variable", "geometry:margin=1in",
                "--variable", "documentclass:article"
            ])
        elif template == "proposal":
            config.extra_args.extend([
                "--variable", "fontsize:12pt",
                "--variable", "geometry:margin=1.25in",
                "--variable", "documentclass:report"
            ])
        elif template == "minimal":
            config.extra_args.extend([
                "--variable", "fontsize:10pt",
                "--variable", "geometry:margin=0.8in"
            ])
        
        # Add bibliography if specified
        if bibliography and bibliography.exists():
            config.extra_args.extend(["--bibliography", str(bibliography)])
            config.extra_args.extend(["--citeproc"])
        
        return config
    
    def validate_dependencies(self) -> DependencyCheck:
        """
        Check availability and versions of Pandoc and XeLaTeX dependencies.
        
        Returns:
            DependencyCheck with status of required dependencies
        """
        pandoc_status, pandoc_version = self._check_pandoc()
        xelatex_status, xelatex_version = self._check_xelatex()
        
        error_messages = []
        if pandoc_status != DependencyStatus.AVAILABLE:
            error_messages.append("Pandoc not available or incompatible version")
        if xelatex_status != DependencyStatus.AVAILABLE:
            error_messages.append("XeLaTeX not available or incompatible version")
        
        return DependencyCheck(
            pandoc_status=pandoc_status,
            xelatex_status=xelatex_status,
            pandoc_version=pandoc_version,
            xelatex_version=xelatex_version,
            error_message="; ".join(error_messages) if error_messages else None
        )
    
    def _check_pandoc(self) -> tuple[DependencyStatus, Optional[str]]:
        """Check Pandoc availability and version."""
        try:
            result = subprocess.run(
                ["pandoc", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Extract version from first line of output
                version_line = result.stdout.split('\n')[0]
                version = version_line.split()[1] if len(version_line.split()) > 1 else "unknown"
                
                # Check minimum version (2.0+)
                try:
                    major_version = int(version.split('.')[0])
                    if major_version >= 2:
                        return DependencyStatus.AVAILABLE, version
                    else:
                        return DependencyStatus.VERSION_INCOMPATIBLE, version
                except (ValueError, IndexError):
                    return DependencyStatus.VERSION_INCOMPATIBLE, version
            else:
                return DependencyStatus.MISSING, None
                
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return DependencyStatus.MISSING, None
    
    def _check_xelatex(self) -> tuple[DependencyStatus, Optional[str]]:
        """Check XeLaTeX availability and version."""
        try:
            result = subprocess.run(
                ["xelatex", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Extract version from output (typically in first few lines)
                version_info = result.stdout.split('\n')[0]
                # Simple version extraction - XeTeX usually shows version info clearly
                version = "available"  # Simplified - XeTeX version parsing can be complex
                return DependencyStatus.AVAILABLE, version
            else:
                return DependencyStatus.MISSING, None
                
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return DependencyStatus.MISSING, None
    
    def _build_pandoc_command(self, md_path: Path, output_path: Path, config: PandocConfig) -> List[str]:
        """Build the Pandoc command line arguments."""
        cmd = ["pandoc"]
        
        # Add default arguments
        cmd.extend(self.default_pandoc_args)
        
        # Add PDF engine
        cmd.extend(["--pdf-engine", config.engine])
        
        # Add extra arguments from config
        if config.extra_args:
            cmd.extend(config.extra_args)
        
        # Add input and output files
        cmd.append(str(md_path))
        cmd.extend(["-o", str(output_path)])
        
        return cmd