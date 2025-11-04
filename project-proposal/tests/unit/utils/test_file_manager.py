"""
Unit tests for file_manager.py module.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import hashlib
import time

from src.utils.file_manager import (
    FileManager, CopyResult, FileInfo, FileType
)


class TestFileManager:
    """Test cases for FileManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.file_manager = FileManager(temp_dir=self.temp_dir / "test_temp")
    
    def teardown_method(self):
        """Clean up test fixtures."""
        self.file_manager.cleanup_temp_files()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_test_file(self, filename: str, content: str, subdir: str = "") -> Path:
        """Helper to create test files."""
        if subdir:
            dir_path = self.temp_dir / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            file_path = dir_path / filename
        else:
            file_path = self.temp_dir / filename
        
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    def test_discover_md_files_recursive(self):
        """Test recursive discovery of markdown files."""
        # Create test files
        self.create_test_file("doc1.md", "# Document 1")
        self.create_test_file("doc2.markdown", "# Document 2")
        self.create_test_file("readme.txt", "Not markdown")
        self.create_test_file("doc3.md", "# Document 3", "subdir")
        self.create_test_file("doc4.md", "# Document 4", "subdir/nested")
        
        files = self.file_manager.discover_md_files(self.temp_dir, recursive=True)
        
        assert len(files) == 4
        md_files = [f.name for f in files]
        assert "doc1.md" in md_files
        assert "doc2.markdown" in md_files
        assert "doc3.md" in md_files
        assert "doc4.md" in md_files
        assert "readme.txt" not in md_files
    
    def test_discover_md_files_non_recursive(self):
        """Test non-recursive discovery of markdown files."""
        # Create test files
        self.create_test_file("doc1.md", "# Document 1")
        self.create_test_file("doc2.md", "# Document 2", "subdir")
        
        files = self.file_manager.discover_md_files(self.temp_dir, recursive=False)
        
        assert len(files) == 1
        assert files[0].name == "doc1.md"
    
    def test_discover_md_files_nonexistent_directory(self):
        """Test discovery in non-existent directory."""
        non_existent = self.temp_dir / "nonexistent"
        files = self.file_manager.discover_md_files(non_existent)
        
        assert len(files) == 0
    
    def test_discover_md_files_not_directory(self):
        """Test discovery when path is not a directory."""
        file_path = self.create_test_file("test.md", "# Test")
        files = self.file_manager.discover_md_files(file_path)
        
        assert len(files) == 0
    
    def test_discover_md_files_sorted_by_mtime(self):
        """Test that files are sorted by modification time (newest first)."""
        # Create files with different modification times
        file1 = self.create_test_file("old.md", "# Old")
        time.sleep(0.1)  # Ensure different timestamps
        file2 = self.create_test_file("new.md", "# New")
        
        files = self.file_manager.discover_md_files(self.temp_dir)
        
        assert len(files) == 2
        # Newer file should be first
        assert files[0].name == "new.md"
        assert files[1].name == "old.md"
    
    def test_discover_assets_with_images(self):
        """Test discovery of image assets."""
        # Create test image files
        img1 = self.create_test_file("image1.png", "fake png")
        img2 = self.create_test_file("image2.jpg", "fake jpg", "images")
        
        # Create markdown file with image references
        md_content = """# Test Document
        
![Image 1](image1.png)
![Image 2](images/image2.jpg)
![External](https://example.com/external.png)
![Missing](missing.png)
"""
        md_file = self.create_test_file("test.md", md_content)
        
        assets = self.file_manager.discover_assets(md_file)
        
        assert len(assets['images']) == 2
        image_paths = [img.name for img in assets['images']]
        assert "image1.png" in image_paths
        assert "image2.jpg" in image_paths
    
    def test_discover_assets_with_bibliography(self):
        """Test discovery of bibliography assets."""
        # Create test bibliography file
        bib_file = self.create_test_file("refs.bib", "@article{test}")
        
        # Create markdown file with bibliography reference
        md_content = """---
title: "Test Document"
bibliography: refs.bib
---

# Test Content
"""
        md_file = self.create_test_file("test.md", md_content)
        
        assets = self.file_manager.discover_assets(md_file)
        
        assert len(assets['bibliography']) == 1
        assert assets['bibliography'][0].name == "refs.bib"
    
    def test_discover_assets_multiple_bibliography(self):
        """Test discovery with multiple bibliography files."""
        # Create test bibliography files
        bib1 = self.create_test_file("refs1.bib", "@article{test1}")
        bib2 = self.create_test_file("refs2.bib", "@article{test2}")
        
        # Create markdown file with multiple bibliography references
        md_content = """---
title: "Test Document"
bibliography: 
  - refs1.bib
  - refs2.bib
---

# Test Content
"""
        md_file = self.create_test_file("test.md", md_content)
        
        assets = self.file_manager.discover_assets(md_file)
        
        assert len(assets['bibliography']) == 2
        bib_names = [bib.name for bib in assets['bibliography']]
        assert "refs1.bib" in bib_names
        assert "refs2.bib" in bib_names
    
    def test_discover_assets_nonexistent_file(self):
        """Test asset discovery for non-existent markdown file."""
        non_existent = self.temp_dir / "nonexistent.md"
        assets = self.file_manager.discover_assets(non_existent)
        
        assert len(assets['images']) == 0
        assert len(assets['bibliography']) == 0
    
    def test_copy_assets_preserve_structure(self):
        """Test copying assets with preserved directory structure."""
        # Create source assets
        source_dir = self.temp_dir / "source"
        target_dir = self.temp_dir / "target"
        
        img1 = self.create_test_file("image1.png", "fake png", "source")
        img2 = self.create_test_file("image2.jpg", "fake jpg", "source/images")
        bib1 = self.create_test_file("refs.bib", "@article{test}", "source")
        
        result = self.file_manager.copy_assets(source_dir, target_dir, preserve_structure=True)
        
        assert result.success
        assert len(result.copied_files) == 3
        assert len(result.failed_files) == 0
        
        # Check that structure is preserved
        assert (target_dir / "image1.png").exists()
        assert (target_dir / "images" / "image2.jpg").exists()
        assert (target_dir / "refs.bib").exists()
    
    def test_copy_assets_flat_structure(self):
        """Test copying assets with flat directory structure."""
        # Create source assets
        source_dir = self.temp_dir / "source"
        target_dir = self.temp_dir / "target"
        
        img1 = self.create_test_file("image1.png", "fake png", "source")
        img2 = self.create_test_file("image2.jpg", "fake jpg", "source/images")
        
        result = self.file_manager.copy_assets(source_dir, target_dir, preserve_structure=False)
        
        assert result.success
        assert len(result.copied_files) == 2
        
        # Check that files are in target root
        assert (target_dir / "image1.png").exists()
        assert (target_dir / "image2.jpg").exists()
        assert not (target_dir / "images").exists()
    
    def test_copy_assets_nonexistent_source(self):
        """Test copying assets from non-existent source."""
        source_dir = self.temp_dir / "nonexistent"
        target_dir = self.temp_dir / "target"
        
        result = self.file_manager.copy_assets(source_dir, target_dir)
        
        assert not result.success
        assert len(result.copied_files) == 0
        assert len(result.error_messages) > 0
    
    @patch('shutil.copy2')
    def test_copy_assets_copy_failure(self, mock_copy):
        """Test handling of copy failures."""
        mock_copy.side_effect = PermissionError("Permission denied")
        
        source_dir = self.temp_dir / "source"
        target_dir = self.temp_dir / "target"
        
        img1 = self.create_test_file("image1.png", "fake png", "source")
        
        result = self.file_manager.copy_assets(source_dir, target_dir)
        
        assert not result.success
        assert len(result.failed_files) == 1
        assert len(result.error_messages) > 0
    
    def test_create_temp_file(self):
        """Test temporary file creation."""
        temp_file = self.file_manager.create_temp_file(suffix=".tex", prefix="test_")
        
        assert temp_file.exists()
        assert temp_file.suffix == ".tex"
        assert temp_file.name.startswith("test_")
        assert temp_file in self.file_manager.temp_files
    
    def test_create_temp_file_unique(self):
        """Test that temporary files have unique names."""
        temp_file1 = self.file_manager.create_temp_file()
        temp_file2 = self.file_manager.create_temp_file()
        
        assert temp_file1 != temp_file2
        assert temp_file1.exists()
        assert temp_file2.exists()
    
    def test_create_temp_directory(self):
        """Test temporary directory creation."""
        temp_dir = self.file_manager.create_temp_directory(prefix="test_")
        
        assert temp_dir.exists()
        assert temp_dir.is_dir()
        assert temp_dir.name.startswith("test_")
        assert temp_dir in self.file_manager.temp_directories
    
    def test_cleanup_temp_files(self):
        """Test cleanup of temporary files and directories."""
        # Create temp files and directories
        temp_file = self.file_manager.create_temp_file()
        temp_dir = self.file_manager.create_temp_directory()
        
        # Create a file in the temp directory
        (temp_dir / "test.txt").write_text("test content")
        
        assert temp_file.exists()
        assert temp_dir.exists()
        
        # Cleanup
        self.file_manager.cleanup_temp_files()
        
        assert not temp_file.exists()
        assert not temp_dir.exists()
        assert len(self.file_manager.temp_files) == 0
        assert len(self.file_manager.temp_directories) == 0
    
    def test_get_file_info_existing_file(self):
        """Test getting information for existing file."""
        test_content = "# Test Document\n\nSome content here."
        test_file = self.create_test_file("test.md", test_content)
        
        file_info = self.file_manager.get_file_info(test_file)
        
        assert file_info.path == test_file
        assert file_info.file_type == FileType.MARKDOWN
        # File size should be greater than 0 (account for potential line ending differences)
        assert file_info.size_bytes > 0
        assert file_info.modified_time > 0
        assert file_info.checksum is not None
    
    def test_get_file_info_nonexistent_file(self):
        """Test getting information for non-existent file."""
        non_existent = self.temp_dir / "nonexistent.md"
        
        file_info = self.file_manager.get_file_info(non_existent)
        
        assert file_info.path == non_existent
        assert file_info.file_type == FileType.UNKNOWN
        assert file_info.size_bytes == 0
        assert file_info.modified_time == 0
        assert file_info.checksum is None
    
    def test_file_type_identification(self):
        """Test file type identification."""
        # Test various file types
        md_file = self.create_test_file("test.md", "# Test")
        img_file = self.create_test_file("test.png", "fake png")
        bib_file = self.create_test_file("test.bib", "@article{test}")
        tex_file = self.create_test_file("test.tex", "\\documentclass{article}")
        unknown_file = self.create_test_file("test.unknown", "unknown content")
        
        assert self.file_manager.get_file_info(md_file).file_type == FileType.MARKDOWN
        assert self.file_manager.get_file_info(img_file).file_type == FileType.IMAGE
        assert self.file_manager.get_file_info(bib_file).file_type == FileType.BIBLIOGRAPHY
        assert self.file_manager.get_file_info(tex_file).file_type == FileType.TEMPLATE
        assert self.file_manager.get_file_info(unknown_file).file_type == FileType.UNKNOWN
    
    def test_ensure_directory_writable_new_directory(self):
        """Test ensuring writable directory creation."""
        new_dir = self.temp_dir / "new_directory"
        
        result = self.file_manager.ensure_directory_writable(new_dir)
        
        assert result
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    def test_ensure_directory_writable_existing_directory(self):
        """Test ensuring writable existing directory."""
        existing_dir = self.temp_dir / "existing"
        existing_dir.mkdir()
        
        result = self.file_manager.ensure_directory_writable(existing_dir)
        
        assert result
    
    @patch('pathlib.Path.mkdir')
    def test_ensure_directory_writable_permission_error(self, mock_mkdir):
        """Test handling of permission errors."""
        mock_mkdir.side_effect = PermissionError("Permission denied")
        
        new_dir = self.temp_dir / "no_permission"
        result = self.file_manager.ensure_directory_writable(new_dir)
        
        assert not result
    
    def test_calculate_total_size(self):
        """Test calculation of total file size."""
        file1 = self.create_test_file("file1.md", "Content 1")
        file2 = self.create_test_file("file2.md", "Content 2 is longer")
        non_existent = self.temp_dir / "nonexistent.md"
        
        files = [file1, file2, non_existent]
        total_size = self.file_manager.calculate_total_size(files)
        
        expected_size = len("Content 1".encode('utf-8')) + len("Content 2 is longer".encode('utf-8'))
        assert total_size == expected_size
    
    def test_checksum_calculation(self):
        """Test checksum calculation."""
        content = "Test content for checksum"
        test_file = self.create_test_file("test.md", content)
        
        file_info = self.file_manager.get_file_info(test_file)
        
        # Calculate expected checksum
        expected_checksum = hashlib.md5(content.encode('utf-8')).hexdigest()
        assert file_info.checksum == expected_checksum
    
    def test_large_file_no_checksum(self):
        """Test that large files don't get checksums calculated."""
        # Mock file size to be large
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value = MagicMock()
            mock_stat.return_value.st_size = 2 * 1024 * 1024  # 2MB
            mock_stat.return_value.st_mtime = time.time()
            
            test_file = self.create_test_file("large.md", "content")
            file_info = self.file_manager.get_file_info(test_file)
            
            assert file_info.checksum is None
    
    def test_discover_assets_malformed_yaml(self):
        """Test asset discovery with malformed YAML frontmatter."""
        md_content = """---
title: Test
invalid yaml: [unclosed
---

# Content
"""
        md_file = self.create_test_file("test.md", md_content)
        
        # Should not raise exception, should return empty assets
        assets = self.file_manager.discover_assets(md_file)
        
        assert len(assets['bibliography']) == 0
    
    def test_discover_assets_read_error(self):
        """Test asset discovery with file read error."""
        test_file = self.create_test_file("test.md", "# Test")
        
        # Mock read_text to raise an exception
        with patch.object(Path, 'read_text', side_effect=IOError("Read error")):
            assets = self.file_manager.discover_assets(test_file)
            
            # Should return empty assets on read error
            assert len(assets['images']) == 0
            assert len(assets['bibliography']) == 0