"""
File management utilities for markdown-to-PDF pipeline.

This module provides file discovery, asset management, and cleanup operations
for the processing pipeline.
"""

from pathlib import Path
from typing import List, Dict, Set, NamedTuple, Optional, Any
import shutil
import tempfile
import logging
from dataclasses import dataclass
from enum import Enum
import hashlib
import re


class CopyResult(NamedTuple):
    """Result of asset copy operation."""
    success: bool
    copied_files: List[Path]
    failed_files: List[Path]
    error_messages: List[str]


class FileType(Enum):
    """Supported file types for processing."""
    MARKDOWN = "markdown"
    IMAGE = "image"
    BIBLIOGRAPHY = "bibliography"
    TEMPLATE = "template"
    UNKNOWN = "unknown"


@dataclass
class FileInfo:
    """Information about a discovered file."""
    path: Path
    file_type: FileType
    size_bytes: int
    modified_time: float
    checksum: Optional[str] = None


class FileManager:
    """
    Manages file operations for the markdown-to-PDF pipeline.
    
    Handles:
    - Discovery of markdown files and their dependencies
    - Asset copying and management
    - Temporary file cleanup
    - File type identification
    """
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.supported_md_extensions = {'.md', '.markdown'}
        self.supported_image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf', '.bmp', '.tiff', '.webp'}
        self.supported_bib_extensions = {'.bib', '.json', '.yaml', '.yml', '.csl'}
        self.temp_files: Set[Path] = set()
        self.temp_directories: Set[Path] = set()
        
        if temp_dir:
            self.temp_base_dir = temp_dir
        else:
            self.temp_base_dir = Path(tempfile.gettempdir()) / "md2pdf"
        
        # Ensure temp directory exists
        self.temp_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
    
    def discover_md_files(self, directory: Path, recursive: bool = True) -> List[Path]:
        """
        Find all markdown files in a directory.
        
        Args:
            directory: Directory to search in
            recursive: Whether to search recursively in subdirectories
            
        Returns:
            List of paths to markdown files, sorted by modification time (newest first)
        """
        if not directory.exists():
            self.logger.warning(f"Directory does not exist: {directory}")
            return []
        
        if not directory.is_dir():
            self.logger.warning(f"Path is not a directory: {directory}")
            return []
        
        markdown_files = []
        
        try:
            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"
            
            for file_path in directory.glob(pattern):
                if file_path.is_file() and file_path.suffix.lower() in self.supported_md_extensions:
                    markdown_files.append(file_path)
        
        except Exception as e:
            self.logger.error(f"Error discovering markdown files in {directory}: {e}")
            return []
        
        # Sort by modification time (newest first)
        try:
            markdown_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        except Exception as e:
            self.logger.warning(f"Error sorting files by modification time: {e}")
        
        self.logger.info(f"Discovered {len(markdown_files)} markdown files in {directory}")
        return markdown_files
    
    def discover_assets(self, md_file: Path) -> Dict[str, List[Path]]:
        """
        Discover assets referenced by a markdown file.
        
        Args:
            md_file: Path to the markdown file
            
        Returns:
            Dictionary with asset types as keys and lists of asset paths as values
        """
        assets = {
            'images': [],
            'bibliography': [],
            'other': []
        }
        
        if not md_file.exists():
            return assets
        
        try:
            content = md_file.read_text(encoding='utf-8')
        except Exception as e:
            self.logger.error(f"Error reading markdown file {md_file}: {e}")
            return assets
        
        base_dir = md_file.parent
        
        # Find image references
        image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        for match in image_pattern.finditer(content):
            image_path_str = match.group(2)
            
            # Skip URLs
            if image_path_str.startswith(('http://', 'https://', 'ftp://')):
                continue
            
            image_path = base_dir / image_path_str
            if image_path.exists():
                assets['images'].append(image_path.resolve())
        
        # Find bibliography from frontmatter
        yaml_pattern = re.compile(r'^---\s*\n(.*?)\n---', re.MULTILINE | re.DOTALL)
        yaml_match = yaml_pattern.match(content)
        if yaml_match:
            try:
                import yaml
                metadata = yaml.safe_load(yaml_match.group(1))
                if isinstance(metadata, dict) and 'bibliography' in metadata:
                    bib_refs = metadata['bibliography']
                    if isinstance(bib_refs, str):
                        bib_refs = [bib_refs]
                    elif not isinstance(bib_refs, list):
                        bib_refs = []
                    
                    for bib_ref in bib_refs:
                        bib_path = base_dir / bib_ref
                        if bib_path.exists():
                            assets['bibliography'].append(bib_path.resolve())
            except Exception as e:
                self.logger.debug(f"Error parsing YAML frontmatter in {md_file}: {e}")
        
        return assets
    
    def copy_assets(self, source_dir: Path, target_dir: Path, 
                   preserve_structure: bool = True) -> CopyResult:
        """
        Copy assets from source to target directory.
        
        Args:
            source_dir: Source directory containing assets
            target_dir: Target directory for copied assets
            preserve_structure: Whether to preserve directory structure
            
        Returns:
            CopyResult with operation details
        """
        copied_files = []
        failed_files = []
        error_messages = []
        
        if not source_dir.exists():
            error_messages.append(f"Source directory does not exist: {source_dir}")
            return CopyResult(False, copied_files, failed_files, error_messages)
        
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            error_messages.append(f"Error creating target directory {target_dir}: {e}")
            return CopyResult(False, copied_files, failed_files, error_messages)
        
        # Find all asset files
        asset_files = []
        for file_type in [self.supported_image_extensions, self.supported_bib_extensions]:
            for ext in file_type:
                asset_files.extend(source_dir.glob(f"**/*{ext}"))
        
        for asset_file in asset_files:
            try:
                if preserve_structure:
                    # Maintain relative path structure
                    rel_path = asset_file.relative_to(source_dir)
                    target_path = target_dir / rel_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    # Flat structure - all files in target_dir root
                    target_path = target_dir / asset_file.name
                
                shutil.copy2(asset_file, target_path)
                copied_files.append(target_path)
                self.logger.debug(f"Copied asset: {asset_file} -> {target_path}")
                
            except Exception as e:
                failed_files.append(asset_file)
                error_messages.append(f"Failed to copy {asset_file}: {e}")
                self.logger.error(f"Error copying {asset_file}: {e}")
        
        success = len(failed_files) == 0
        self.logger.info(f"Asset copy completed: {len(copied_files)} copied, {len(failed_files)} failed")
        
        return CopyResult(success, copied_files, failed_files, error_messages)
    
    def create_temp_file(self, suffix: str = "", prefix: str = "md2pdf_") -> Path:
        """
        Create a temporary file for processing.
        
        Args:
            suffix: File suffix (e.g., '.tex', '.pdf')
            prefix: File prefix
            
        Returns:
            Path to created temporary file
        """
        temp_file = self.temp_base_dir / f"{prefix}{hashlib.md5(str(Path.cwd()).encode()).hexdigest()[:8]}{suffix}"
        
        # Ensure file is unique
        counter = 0
        original_temp_file = temp_file
        while temp_file.exists():
            counter += 1
            temp_file = original_temp_file.with_stem(f"{original_temp_file.stem}_{counter}")
        
        # Create the file
        temp_file.touch()
        self.temp_files.add(temp_file)
        
        self.logger.debug(f"Created temporary file: {temp_file}")
        return temp_file
    
    def create_temp_directory(self, prefix: str = "md2pdf_") -> Path:
        """
        Create a temporary directory for processing.
        
        Args:
            prefix: Directory prefix
            
        Returns:
            Path to created temporary directory
        """
        temp_dir = self.temp_base_dir / f"{prefix}{hashlib.md5(str(Path.cwd()).encode()).hexdigest()[:8]}"
        
        # Ensure directory is unique
        counter = 0
        original_temp_dir = temp_dir
        while temp_dir.exists():
            counter += 1
            temp_dir = original_temp_dir.with_name(f"{original_temp_dir.name}_{counter}")
        
        temp_dir.mkdir(parents=True)
        self.temp_directories.add(temp_dir)
        
        self.logger.debug(f"Created temporary directory: {temp_dir}")
        return temp_dir
    
    def cleanup_temp_files(self) -> None:
        """Remove all tracked temporary files and directories."""
        # Clean up files
        for temp_file in list(self.temp_files):
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    self.logger.debug(f"Deleted temporary file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Error deleting temporary file {temp_file}: {e}")
        
        self.temp_files.clear()
        
        # Clean up directories
        for temp_dir in list(self.temp_directories):
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    self.logger.debug(f"Deleted temporary directory: {temp_dir}")
            except Exception as e:
                self.logger.warning(f"Error deleting temporary directory {temp_dir}: {e}")
        
        self.temp_directories.clear()
        
        self.logger.info("Temporary file cleanup completed")
    
    def get_file_info(self, file_path: Path) -> FileInfo:
        """
        Get detailed information about a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            FileInfo object with file details
        """
        if not file_path.exists():
            return FileInfo(
                path=file_path,
                file_type=FileType.UNKNOWN,
                size_bytes=0,
                modified_time=0
            )
        
        stat_result = file_path.stat()
        file_type = self._identify_file_type(file_path)
        
        # Calculate checksum for small files only
        checksum = None
        if stat_result.st_size < 1024 * 1024:  # 1MB limit
            try:
                checksum = self._calculate_checksum(file_path)
            except Exception as e:
                self.logger.debug(f"Error calculating checksum for {file_path}: {e}")
        
        return FileInfo(
            path=file_path,
            file_type=file_type,
            size_bytes=stat_result.st_size,
            modified_time=stat_result.st_mtime,
            checksum=checksum
        )
    
    def ensure_directory_writable(self, directory: Path) -> bool:
        """
        Ensure a directory exists and is writable.
        
        Args:
            directory: Directory to check/create
            
        Returns:
            True if directory exists and is writable, False otherwise
        """
        try:
            directory.mkdir(parents=True, exist_ok=True)
            
            # Test write permissions
            test_file = directory / '.write_test'
            test_file.write_text('test')
            test_file.unlink()
            
            return True
        except Exception as e:
            self.logger.error(f"Directory not writable {directory}: {e}")
            return False
    
    def calculate_total_size(self, files: List[Path]) -> int:
        """
        Calculate total size of a list of files.
        
        Args:
            files: List of file paths
            
        Returns:
            Total size in bytes
        """
        total_size = 0
        for file_path in files:
            try:
                if file_path.exists() and file_path.is_file():
                    total_size += file_path.stat().st_size
            except Exception as e:
                self.logger.debug(f"Error getting size of {file_path}: {e}")
        
        return total_size
    
    def _identify_file_type(self, file_path: Path) -> FileType:
        """Identify the type of a file based on its extension."""
        suffix = file_path.suffix.lower()
        
        if suffix in self.supported_md_extensions:
            return FileType.MARKDOWN
        elif suffix in self.supported_image_extensions:
            return FileType.IMAGE
        elif suffix in self.supported_bib_extensions:
            return FileType.BIBLIOGRAPHY
        elif suffix in {'.tex', '.cls', '.sty'}:
            return FileType.TEMPLATE
        else:
            return FileType.UNKNOWN
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            self.cleanup_temp_files()
        except Exception:
            pass  # Ignore errors during cleanup