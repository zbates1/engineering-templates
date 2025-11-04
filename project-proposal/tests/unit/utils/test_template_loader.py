"""
Unit tests for template_loader.py module.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch, mock_open

from src.utils.template_loader import (
    TemplateLoader, Template, Metadata, ProcessingConfig,
    TemplateType
)


class TestTemplateLoader:
    """Test cases for TemplateLoader class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_dir = self.temp_dir / "templates"
        self.template_dir.mkdir()
        self.loader = TemplateLoader(template_dirs=[self.template_dir])
    
    def teardown_method(self):
        """Clean up test fixtures."""
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
    
    def test_load_built_in_template_default(self):
        """Test loading built-in default template."""
        template = self.loader.load_template('default')
        
        assert template.name == 'default'
        assert template.template_type == TemplateType.LATEX
        assert template.content is not None
        assert len(template.content) > 0
        assert 'documentclass' in template.content
        assert 'begin{document}' in template.content
        assert 'end{document}' in template.content
    
    def test_load_built_in_template_academic(self):
        """Test loading built-in academic template."""
        template = self.loader.load_template('academic')
        
        assert template.name == 'academic'
        assert template.template_type == TemplateType.LATEX
        assert template.variables.get('documentclass') == 'article'
        assert template.variables.get('fontsize') == '12pt'
    
    def test_load_custom_template(self):
        """Test loading custom template from file."""
        custom_content = """\\documentclass{article}
% GEOMETRY: margin=2in
% FONTSIZE: 14pt

\\begin{document}
$body$
\\end{document}
"""
        self.create_test_file("custom.tex", custom_content, "templates")
        
        template = self.loader.load_template('custom')
        
        assert template.name == 'custom'
        assert template.template_type == TemplateType.CUSTOM
        assert template.content == custom_content
        assert template.variables.get('geometry') == 'margin=2in'
        assert template.variables.get('fontsize') == '14pt'
    
    def test_load_template_not_found(self):
        """Test loading non-existent template raises error."""
        with pytest.raises(FileNotFoundError):
            self.loader.load_template('nonexistent')
    
    def test_template_caching(self):
        """Test that templates are cached after first load."""
        # Load template twice
        template1 = self.loader.load_template('default')
        template2 = self.loader.load_template('default')
        
        # Should be the same object (cached)
        assert template1 is template2
        assert 'default' in self.loader.template_cache
    
    def test_load_metadata_with_frontmatter(self):
        """Test loading metadata from YAML frontmatter."""
        content = """---
title: "Test Document"
author: "John Doe"
date: "2025-09-05"
bibliography: refs.bib
csl: ieee.csl
lang: en-GB
geometry: margin=1.5in
fontsize: 12pt
documentclass: report
toc: true
---

# Content here
"""
        md_file = self.create_test_file("test.md", content)
        
        metadata = self.loader.load_metadata(md_file)
        
        assert metadata.title == "Test Document"
        assert metadata.author == "John Doe"
        assert metadata.date == "2025-09-05"
        assert metadata.bibliography == "refs.bib"
        assert metadata.csl == "ieee.csl"
        assert metadata.lang == "en-GB"
        assert metadata.geometry == "margin=1.5in"
        assert metadata.fontsize == "12pt"
        assert metadata.documentclass == "report"
        assert metadata.raw_metadata['toc'] is True
    
    def test_load_metadata_list_authors(self):
        """Test loading metadata with list of authors."""
        content = """---
title: "Multi-Author Document"
author: 
  - "John Doe"
  - "Jane Smith"
bibliography:
  - "refs1.bib"
  - "refs2.bib"
---

# Content
"""
        md_file = self.create_test_file("test.md", content)
        
        metadata = self.loader.load_metadata(md_file)
        
        assert metadata.title == "Multi-Author Document"
        assert metadata.author == ["John Doe", "Jane Smith"]
        assert metadata.bibliography == ["refs1.bib", "refs2.bib"]
    
    def test_load_metadata_no_frontmatter(self):
        """Test loading metadata from file without frontmatter."""
        content = "# Simple Document\n\nNo frontmatter here."
        md_file = self.create_test_file("test.md", content)
        
        metadata = self.loader.load_metadata(md_file)
        
        assert metadata.title is None
        assert metadata.author is None
        assert len(metadata.raw_metadata) == 0
    
    def test_load_metadata_invalid_yaml(self):
        """Test handling of invalid YAML frontmatter."""
        content = """---
title: "Test Document
author: [invalid yaml
---

# Content
"""
        md_file = self.create_test_file("test.md", content)
        
        metadata = self.loader.load_metadata(md_file)
        
        # Should return empty metadata on YAML parse error
        assert metadata.title is None
        assert len(metadata.raw_metadata) == 0
    
    def test_load_metadata_nonexistent_file(self):
        """Test loading metadata from non-existent file."""
        non_existent = self.temp_dir / "nonexistent.md"
        
        metadata = self.loader.load_metadata(non_existent)
        
        assert metadata.title is None
        assert len(metadata.raw_metadata) == 0
    
    def test_merge_config_basic(self):
        """Test basic configuration merging."""
        template = self.loader.load_template('default')
        metadata = Metadata(
            title="Test Document",
            author="Test Author",
            bibliography="refs.bib"
        )
        
        config = self.loader.merge_config(template, metadata)
        
        assert config.template == template
        assert config.metadata.title == "Test Document"
        assert config.metadata.author == "Test Author"
        assert config.metadata.bibliography == "refs.bib"
        assert config.output_format == 'pdf'
        assert len(config.pandoc_options) > 0
        assert '--from' in config.pandoc_options
        assert '--to' in config.pandoc_options
    
    def test_merge_config_template_overrides(self):
        """Test that metadata overrides template defaults."""
        template = self.loader.load_template('default')
        metadata = Metadata(
            fontsize="14pt",
            geometry="margin=2in",
            documentclass="report"
        )
        
        config = self.loader.merge_config(template, metadata)
        
        assert config.metadata.fontsize == "14pt"
        assert config.metadata.geometry == "margin=2in"
        assert config.metadata.documentclass == "report"
    
    def test_merge_config_with_bibliography(self):
        """Test config merging with bibliography settings."""
        template = self.loader.load_template('academic')
        metadata = Metadata(
            bibliography=["refs1.bib", "refs2.bib"],
            csl="apa.csl"
        )
        
        config = self.loader.merge_config(template, metadata)
        
        assert '--bibliography' in config.pandoc_options
        assert '--csl' in config.pandoc_options
        assert '--citeproc' in config.pandoc_options
    
    def test_get_available_templates(self):
        """Test getting list of available templates."""
        # Create a custom template
        self.create_test_file("mycustom.tex", "\\documentclass{article}", "templates")
        
        available = self.loader.get_available_templates()
        
        # Should include built-in templates
        assert 'default' in available
        assert 'academic' in available
        assert 'proposal' in available
        assert 'minimal' in available
        
        # Should include custom template
        assert 'mycustom' in available
        
        # Check descriptions
        assert 'Clean, professional layout' in available['default']
        assert 'Custom template' in available['mycustom']
    
    def test_validate_template_valid(self):
        """Test validation of valid template."""
        template = Template(
            name="test",
            template_type=TemplateType.LATEX,
            content="""\\documentclass{article}
\\begin{document}
$title$
$body$
\\end{document}""",
            variables={'title': 'Test'}
        )
        
        errors = self.loader.validate_template(template)
        
        assert len(errors) == 0
    
    def test_validate_template_missing_commands(self):
        """Test validation of template missing required commands."""
        template = Template(
            name="invalid",
            template_type=TemplateType.LATEX,
            content="Just some text, no LaTeX commands"
        )
        
        errors = self.loader.validate_template(template)
        
        assert len(errors) > 0
        assert any("documentclass" in error for error in errors)
        assert any("begin{document}" in error for error in errors)
        assert any("end{document}" in error for error in errors)
    
    def test_validate_template_undefined_variables(self):
        """Test validation catches undefined variables."""
        template = Template(
            name="undefined_vars",
            template_type=TemplateType.LATEX,
            content="""\\documentclass{article}
\\begin{document}
$title$
$undefined_variable$
\\end{document}"""
        )
        
        errors = self.loader.validate_template(template)
        
        assert len(errors) > 0
        assert any("undefined_variable" in error for error in errors)
    
    def test_validate_template_mismatched_braces(self):
        """Test validation catches mismatched braces."""
        template = Template(
            name="mismatched",
            template_type=TemplateType.LATEX,
            content="""\\documentclass{article}
\\begin{document}
{Missing closing brace
\\end{document}"""
        )
        
        errors = self.loader.validate_template(template)
        
        assert len(errors) > 0
        assert any("Mismatched braces" in error for error in errors)
    
    def test_validate_template_empty_content(self):
        """Test validation of empty template."""
        template = Template(
            name="empty",
            template_type=TemplateType.LATEX,
            content=""
        )
        
        errors = self.loader.validate_template(template)
        
        assert len(errors) > 0
        assert "Template content is empty" in errors[0]
    
    def test_extract_template_variables(self):
        """Test extraction of variables from template comments."""
        template_content = """% GEOMETRY: margin=1in
% FONTSIZE: 12pt
% AUTHOR: Default Author
\\documentclass{article}
% This is a regular comment
\\begin{document}
% DESCRIPTION: Test template
$body$
\\end{document}
"""
        variables = self.loader._extract_template_variables(template_content)
        
        assert variables['geometry'] == 'margin=1in'
        assert variables['fontsize'] == '12pt'
        assert variables['author'] == 'Default Author'
        assert variables['description'] == 'Test template'
    
    def test_build_pandoc_options_basic(self):
        """Test building basic pandoc options."""
        template = Template("test", TemplateType.LATEX, "content")
        metadata = Metadata(
            bibliography="refs.bib",
            csl="ieee.csl"
        )
        
        options = self.loader._build_pandoc_options(template, metadata)
        
        assert '--from' in options
        assert 'markdown' in options
        assert '--to' in options
        assert 'latex' in options
        assert '--bibliography' in options
        assert 'refs.bib' in options
        assert '--csl' in options
        assert 'ieee.csl' in options
        assert '--citeproc' in options
        assert '--pdf-engine' in options
        assert 'xelatex' in options
    
    def test_build_pandoc_options_with_toc(self):
        """Test pandoc options with table of contents."""
        template = Template("test", TemplateType.LATEX, "content")
        metadata = Metadata(
            raw_metadata={'toc': True, 'number-sections': True}
        )
        
        options = self.loader._build_pandoc_options(template, metadata)
        
        assert '--toc' in options
        assert '--number-sections' in options
    
    def test_build_latex_options(self):
        """Test building LaTeX options."""
        template = Template("test", TemplateType.LATEX, "content")
        metadata = Metadata()
        
        options = self.loader._build_latex_options(template, metadata)
        
        assert '-interaction=nonstopmode' in options
        assert '-output-directory' in options
    
    def test_generate_default_template_content(self):
        """Test generation of default template content."""
        config = {
            'documentclass': 'report',
            'fontsize': '12pt',
            'geometry': 'margin=1.5in'
        }
        
        content = self.loader._generate_default_template_content(config)
        
        assert '\\documentclass[12pt]{report}' in content
        assert 'margin=1.5in' in content
        assert '\\begin{document}' in content
        assert '\\end{document}' in content
        assert '$body$' in content
    
    def test_custom_template_error_handling(self):
        """Test error handling when loading custom template fails."""
        # Create a template file with permission issues or invalid content
        template_file = self.template_dir / "problematic.tex"
        template_file.write_text("Valid content initially")
        
        # Mock read_text to raise an exception
        with patch.object(Path, 'read_text', side_effect=IOError("Read error")):
            template = self.loader._load_custom_template("problematic")
            assert template is None
    
    def test_metadata_extraction_non_dict_yaml(self):
        """Test handling of non-dictionary YAML frontmatter."""
        content = """---
- item1
- item2
---

# Content
"""
        metadata = self.loader._extract_metadata_from_content(content)
        
        # Should return empty metadata for non-dict YAML
        assert metadata.title is None
        assert len(metadata.raw_metadata) == 0
    
    def test_metadata_extraction_malformed_frontmatter(self):
        """Test handling of malformed frontmatter boundaries."""
        content = """---
title: "Test"
No closing boundary

# Content
"""
        metadata = self.loader._extract_metadata_from_content(content)
        
        # Should return empty metadata for malformed frontmatter
        assert metadata.title is None
        assert len(metadata.raw_metadata) == 0