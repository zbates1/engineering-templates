"""
Unit tests for file_validator.py module.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch, mock_open

from src.validators.file_validator import (
    FileValidator, ValidationResult, ValidationIssue, 
    ValidationSeverity, ReferenceCheck
)


class TestFileValidator:
    """Test cases for FileValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileValidator()
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_test_file(self, filename: str, content: str) -> Path:
        """Helper to create test files."""
        file_path = self.temp_dir / filename
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file."""
        non_existent = self.temp_dir / "nonexistent.md"
        result = self.validator.validate_markdown(non_existent)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].severity == ValidationSeverity.ERROR
        assert "does not exist" in result.issues[0].message
    
    def test_validate_non_markdown_file(self):
        """Test validation of non-markdown file."""
        txt_file = self.create_test_file("test.txt", "This is not markdown")
        result = self.validator.validate_markdown(txt_file)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].severity == ValidationSeverity.ERROR
        assert "not a markdown file" in result.issues[0].message
    
    def test_validate_directory_instead_of_file(self):
        """Test validation when path is a directory."""
        test_dir = self.temp_dir / "test_dir"
        test_dir.mkdir()
        
        result = self.validator.validate_markdown(test_dir)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].severity == ValidationSeverity.ERROR
        assert "not a file" in result.issues[0].message
    
    def test_validate_valid_simple_markdown(self):
        """Test validation of valid simple markdown."""
        content = """---
title: "Test Document"
author: "Test Author"
---

# Introduction

This is a test document with proper structure.

## Section 1

Some content here.
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert result.is_valid
        assert result.metadata is not None
        assert result.metadata['title'] == "Test Document"
        assert result.metadata['author'] == "Test Author"
    
    def test_validate_markdown_without_frontmatter(self):
        """Test validation of markdown without frontmatter."""
        content = """# Test Document

This is a test document without frontmatter.
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert result.is_valid
        # Should have warnings for missing title/author
        warnings = [issue for issue in result.issues if issue.severity == ValidationSeverity.WARNING]
        assert len(warnings) >= 2  # Missing title and author warnings
    
    def test_validate_invalid_yaml_frontmatter(self):
        """Test validation with invalid YAML frontmatter."""
        content = """---
title: "Test Document
author: [invalid yaml
---

# Content
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert not result.is_valid
        errors = [issue for issue in result.issues if issue.severity == ValidationSeverity.ERROR]
        assert len(errors) >= 1
        assert any("Invalid YAML" in error.message for error in errors)
    
    def test_validate_unclosed_yaml_frontmatter(self):
        """Test validation with unclosed YAML frontmatter."""
        content = """---
title: "Test Document"
author: "Test Author"

# Content without closing frontmatter
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert not result.is_valid
        errors = [issue for issue in result.issues if issue.severity == ValidationSeverity.ERROR]
        assert any("not properly closed" in error.message for error in errors)
    
    def test_validate_short_document_warning(self):
        """Test warning for very short documents."""
        content = "# Title\n\nShort content."
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert result.is_valid
        warnings = [issue for issue in result.issues if issue.severity == ValidationSeverity.WARNING]
        assert any("very short" in warning.message for warning in warnings)
    
    def test_validate_no_headers_warning(self):
        """Test warning for documents without headers."""
        content = "This is just plain text without any headers."
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert result.is_valid
        warnings = [issue for issue in result.issues if issue.severity == ValidationSeverity.WARNING]
        assert any("no headers" in warning.message for warning in warnings)
    
    def test_validate_unbalanced_brackets(self):
        """Test detection of unbalanced brackets."""
        content = """# Test
        
This has [unbalanced brackets and should warn.

Also this: [another unbalanced
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        warnings = [issue for issue in result.issues if issue.severity == ValidationSeverity.WARNING]
        bracket_warnings = [w for w in warnings if "brackets" in w.message]
        assert len(bracket_warnings) >= 1
    
    def test_validate_unclosed_link_parenthesis(self):
        """Test detection of unclosed parentheses in links."""
        content = """# Test

This has an [unclosed link](http://example.com and should warn.
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        warnings = [issue for issue in result.issues if issue.severity == ValidationSeverity.WARNING]
        paren_warnings = [w for w in warnings if "parenthesis" in w.message]
        assert len(paren_warnings) >= 1
    
    def test_check_references_missing_images(self):
        """Test detection of missing image references."""
        content = """# Test

![Missing Image](missing.png)
![Another Missing](images/nonexistent.jpg)
![Valid External](https://example.com/image.png)
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.check_references(md_file)
        
        assert not result.all_references_valid
        assert len(result.missing_images) == 2
        assert Path("missing.png") in result.missing_images
        assert Path("images/nonexistent.jpg") in result.missing_images
    
    def test_check_references_missing_bibliography(self):
        """Test detection of missing bibliography files."""
        content = """---
title: "Test"
bibliography: missing.bib
---

# Test Content
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.check_references(md_file)
        
        assert not result.all_references_valid
        assert len(result.missing_bibliography) == 1
        assert Path("missing.bib") in result.missing_bibliography
    
    def test_check_references_multiple_bibliography_files(self):
        """Test handling of multiple bibliography files."""
        content = """---
title: "Test"
bibliography: 
  - refs1.bib
  - refs2.bib
---

# Test Content
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.check_references(md_file)
        
        assert not result.all_references_valid
        assert len(result.missing_bibliography) == 2
    
    def test_check_references_broken_internal_links(self):
        """Test detection of broken internal links."""
        content = """# Test

[Broken Link](missing.md)
[External Link](https://example.com)
[Another Broken](docs/nonexistent.md)
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.check_references(md_file)
        
        assert not result.all_references_valid
        assert len(result.broken_links) == 2
        assert "missing.md" in result.broken_links
        assert "docs/nonexistent.md" in result.broken_links
    
    def test_check_references_with_existing_files(self):
        """Test reference checking with existing files."""
        # Create required files
        image_file = self.create_test_file("test.png", "fake image")
        bib_file = self.create_test_file("refs.bib", "@article{test}")
        
        content = """---
title: "Test"
bibliography: refs.bib
---

# Test

![Valid Image](test.png)
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.check_references(md_file)
        
        assert result.all_references_valid
        assert len(result.missing_images) == 0
        assert len(result.missing_bibliography) == 0
        assert len(result.broken_links) == 0
    
    def test_ensure_output_directory_creates_directory(self):
        """Test output directory creation."""
        output_dir = self.temp_dir / "output" / "nested"
        
        result = self.validator.ensure_output_directory(output_dir)
        
        assert result
        assert output_dir.exists()
        assert output_dir.is_dir()
    
    def test_ensure_output_directory_existing_directory(self):
        """Test with existing output directory."""
        output_dir = self.temp_dir / "existing"
        output_dir.mkdir()
        
        result = self.validator.ensure_output_directory(output_dir)
        
        assert result
        assert output_dir.exists()
    
    @patch('pathlib.Path.mkdir')
    def test_ensure_output_directory_permission_error(self, mock_mkdir):
        """Test handling of permission errors when creating directory."""
        mock_mkdir.side_effect = PermissionError("Permission denied")
        
        output_dir = self.temp_dir / "no_permission"
        result = self.validator.ensure_output_directory(output_dir)
        
        assert not result
    
    def test_unicode_decode_error_handling(self):
        """Test handling of files with encoding issues."""
        # Create a file with invalid UTF-8
        binary_file = self.temp_dir / "binary.md"
        binary_file.write_bytes(b'\xff\xfe\x00\x00invalid utf-8')
        
        result = self.validator.validate_markdown(binary_file)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].severity == ValidationSeverity.ERROR
        assert "decode" in result.issues[0].message.lower()
    
    def test_empty_yaml_frontmatter(self):
        """Test handling of empty YAML frontmatter."""
        content = """---
---

# Content
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert result.is_valid
        assert result.metadata == {}
    
    def test_non_dict_yaml_frontmatter(self):
        """Test handling of non-dictionary YAML frontmatter."""
        content = """---
- item1
- item2
---

# Content
"""
        md_file = self.create_test_file("test.md", content)
        result = self.validator.validate_markdown(md_file)
        
        assert not result.is_valid
        errors = [issue for issue in result.issues if issue.severity == ValidationSeverity.ERROR]
        assert any("must be a dictionary" in error.message for error in errors)