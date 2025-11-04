"""
Template loading and metadata management for markdown-to-PDF pipeline.

This module handles LaTeX template loading, YAML metadata extraction,
and configuration merging for the processing pipeline.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, NamedTuple, Union
import yaml
import re
import logging
from dataclasses import dataclass, field
from enum import Enum


class TemplateType(Enum):
    """Supported template types."""
    LATEX = "latex"
    PANDOC = "pandoc"
    CUSTOM = "custom"


@dataclass
class Template:
    """Represents a loaded template."""
    name: str
    template_type: TemplateType
    content: str
    variables: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class Metadata:
    """Represents extracted document metadata."""
    title: Optional[str] = None
    author: Optional[Union[str, List[str]]] = None
    date: Optional[str] = None
    bibliography: Optional[Union[str, List[str]]] = None
    csl: Optional[str] = None
    lang: Optional[str] = None
    geometry: Optional[str] = None
    fontsize: Optional[str] = None
    documentclass: Optional[str] = None
    template: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


class ProcessingConfig(NamedTuple):
    """Combined processing configuration."""
    template: Template
    metadata: Metadata
    pandoc_options: List[str]
    latex_options: List[str]
    output_format: str


class TemplateLoader:
    """
    Loads and manages templates and metadata for the processing pipeline.
    
    Handles:
    - LaTeX template discovery and loading
    - YAML frontmatter extraction and parsing
    - Configuration merging between templates and metadata
    - Template variable substitution
    """
    
    def __init__(self, template_dirs: Optional[List[Path]] = None):
        self.template_dirs = template_dirs or []
        self.built_in_templates_dir = Path(__file__).parent.parent.parent / "templates"
        self.template_cache: Dict[str, Template] = {}
        self.logger = logging.getLogger(__name__)
        
        # Built-in template names and their configurations
        self.built_in_templates = {
            'default': {
                'description': 'Clean, professional layout',
                'documentclass': 'article',
                'geometry': 'margin=1in',
                'fontsize': '11pt'
            },
            'academic': {
                'description': 'Suitable for research papers',
                'documentclass': 'article',
                'geometry': 'margin=1in',
                'fontsize': '12pt',
                'bibliography_style': 'ieee'
            },
            'proposal': {
                'description': 'Formatted for project proposals',
                'documentclass': 'report',
                'geometry': 'margin=1.25in',
                'fontsize': '11pt'
            },
            'minimal': {
                'description': 'Lightweight design',
                'documentclass': 'article',
                'geometry': 'margin=0.75in',
                'fontsize': '10pt'
            }
        }
    
    def load_template(self, name: str) -> Template:
        """
        Load a template by name.
        
        Args:
            name: Template name (built-in or custom)
            
        Returns:
            Template object
            
        Raises:
            FileNotFoundError: If template is not found
            ValueError: If template is invalid
        """
        # Check cache first
        if name in self.template_cache:
            self.logger.debug(f"Loading template '{name}' from cache")
            return self.template_cache[name]
        
        template = None
        
        # Try to load built-in template
        if name in self.built_in_templates:
            template = self._load_built_in_template(name)
        else:
            # Try to load custom template
            template = self._load_custom_template(name)
        
        if template is None:
            raise FileNotFoundError(f"Template '{name}' not found")
        
        # Cache the template
        self.template_cache[name] = template
        self.logger.info(f"Loaded template '{name}' successfully")
        
        return template
    
    def load_metadata(self, md_path: Path) -> Metadata:
        """
        Extract metadata from a markdown file's YAML frontmatter.
        
        Args:
            md_path: Path to the markdown file
            
        Returns:
            Metadata object with extracted information
        """
        if not md_path.exists():
            self.logger.warning(f"Markdown file does not exist: {md_path}")
            return Metadata()
        
        try:
            content = md_path.read_text(encoding='utf-8')
        except Exception as e:
            self.logger.error(f"Error reading markdown file {md_path}: {e}")
            return Metadata()
        
        return self._extract_metadata_from_content(content)
    
    def merge_config(self, template: Template, metadata: Metadata) -> ProcessingConfig:
        """
        Merge template and metadata into a processing configuration.
        
        Args:
            template: Template object
            metadata: Metadata object
            
        Returns:
            ProcessingConfig with merged settings
        """
        # Start with template defaults
        merged_metadata = Metadata(
            title=metadata.title,
            author=metadata.author,
            date=metadata.date,
            bibliography=metadata.bibliography,
            csl=metadata.csl,
            lang=metadata.lang or 'en-US',
            geometry=metadata.geometry or template.variables.get('geometry'),
            fontsize=metadata.fontsize or template.variables.get('fontsize'),
            documentclass=metadata.documentclass or template.variables.get('documentclass'),
            template=template.name,
            raw_metadata=metadata.raw_metadata.copy()
        )
        
        # Build pandoc options
        pandoc_options = self._build_pandoc_options(template, merged_metadata)
        
        # Build latex options
        latex_options = self._build_latex_options(template, merged_metadata)
        
        return ProcessingConfig(
            template=template,
            metadata=merged_metadata,
            pandoc_options=pandoc_options,
            latex_options=latex_options,
            output_format='pdf'
        )
    
    def get_available_templates(self) -> Dict[str, str]:
        """
        Get list of available templates with descriptions.
        
        Returns:
            Dictionary mapping template names to descriptions
        """
        available = {}
        
        # Add built-in templates
        for name, config in self.built_in_templates.items():
            available[name] = config.get('description', f'Built-in template: {name}')
        
        # Add custom templates from template directories
        for template_dir in self.template_dirs:
            if template_dir.exists():
                for template_file in template_dir.glob('*.tex'):
                    template_name = template_file.stem
                    available[template_name] = f'Custom template: {template_name}'
        
        return available
    
    def validate_template(self, template: Template) -> List[str]:
        """
        Validate a template for common issues.
        
        Args:
            template: Template to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not template.content:
            errors.append("Template content is empty")
            return errors
        
        # Check for required LaTeX commands
        required_commands = [r'\\documentclass', r'\\begin{document}', r'\\end{document}']
        for cmd in required_commands:
            if not re.search(cmd, template.content):
                errors.append(f"Missing required LaTeX command: {cmd}")
        
        # Check for potential variable substitution issues
        var_pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)\$'
        variables_in_template = set(re.findall(var_pattern, template.content))
        
        for var in variables_in_template:
            if var not in template.variables and var not in [
                'title', 'author', 'date', 'body', 'toc', 'bibliography'
            ]:
                errors.append(f"Undefined template variable: {var}")
        
        # Check for unclosed braces
        open_braces = template.content.count('{')
        close_braces = template.content.count('}')
        if open_braces != close_braces:
            errors.append(f"Mismatched braces: {open_braces} open, {close_braces} close")
        
        return errors
    
    def _load_built_in_template(self, name: str) -> Template:
        """Load a built-in template."""
        config = self.built_in_templates[name]
        
        # Try to load template file from built-in templates directory
        template_file = self.built_in_templates_dir / f"{name}.tex"
        
        if template_file.exists():
            try:
                content = template_file.read_text(encoding='utf-8')
            except Exception as e:
                self.logger.error(f"Error reading built-in template {name}: {e}")
                content = self._generate_default_template_content(config)
        else:
            # Generate template content from configuration
            content = self._generate_default_template_content(config)
        
        return Template(
            name=name,
            template_type=TemplateType.LATEX,
            content=content,
            variables=config.copy(),
            description=config.get('description')
        )
    
    def _load_custom_template(self, name: str) -> Optional[Template]:
        """Load a custom template from template directories."""
        for template_dir in self.template_dirs:
            template_file = template_dir / f"{name}.tex"
            if template_file.exists():
                try:
                    content = template_file.read_text(encoding='utf-8')
                    
                    # Extract variables from template comments
                    variables = self._extract_template_variables(content)
                    
                    return Template(
                        name=name,
                        template_type=TemplateType.CUSTOM,
                        content=content,
                        variables=variables,
                        description=f"Custom template: {name}"
                    )
                except Exception as e:
                    self.logger.error(f"Error loading custom template {name}: {e}")
                    continue
        
        return None
    
    def _extract_metadata_from_content(self, content: str) -> Metadata:
        """Extract YAML frontmatter from markdown content."""
        if not content.startswith('---'):
            return Metadata()
        
        # Find YAML frontmatter boundaries
        yaml_pattern = re.compile(r'^---\s*\n(.*?)\n---', re.MULTILINE | re.DOTALL)
        match = yaml_pattern.match(content)
        
        if not match:
            return Metadata()
        
        yaml_content = match.group(1)
        
        try:
            raw_data = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML frontmatter: {e}")
            return Metadata()
        
        if not isinstance(raw_data, dict):
            self.logger.warning("YAML frontmatter is not a dictionary")
            return Metadata()
        
        # Extract known fields
        return Metadata(
            title=raw_data.get('title'),
            author=raw_data.get('author'),
            date=raw_data.get('date'),
            bibliography=raw_data.get('bibliography'),
            csl=raw_data.get('csl'),
            lang=raw_data.get('lang'),
            geometry=raw_data.get('geometry'),
            fontsize=raw_data.get('fontsize'),
            documentclass=raw_data.get('documentclass'),
            template=raw_data.get('template'),
            raw_metadata=raw_data.copy()
        )
    
    def _extract_template_variables(self, template_content: str) -> Dict[str, Any]:
        """Extract variables from template comments."""
        variables = {}
        
        # Look for variable definitions in comments
        # Format: % VARIABLE: value
        var_pattern = re.compile(r'%\s*([A-Z_]+):\s*(.+)', re.IGNORECASE)
        
        for match in var_pattern.finditer(template_content):
            var_name = match.group(1).lower()
            var_value = match.group(2).strip()
            variables[var_name] = var_value
        
        return variables
    
    def _generate_default_template_content(self, config: Dict[str, Any]) -> str:
        """Generate default LaTeX template content from configuration."""
        documentclass = config.get('documentclass', 'article')
        fontsize = config.get('fontsize', '11pt')
        geometry = config.get('geometry', 'margin=1in')
        
        template = f"""\\documentclass[{fontsize}]{{{documentclass}}}

% Package imports
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\usepackage[{geometry}]{{geometry}}
\\usepackage{{graphicx}}
\\usepackage{{hyperref}}

% Bibliography support
\\usepackage{{natbib}}
\\usepackage{{url}}

% Title, author, date
$if(title)$
\\title{{$title$}}
$endif$
$if(author)$
\\author{{$author$}}
$endif$
$if(date)$
\\date{{$date$}}
$endif$

\\begin{{document}}

$if(title)$
\\maketitle
$endif$

$if(toc)$
\\tableofcontents
\\newpage
$endif$

$body$

$if(bibliography)$
\\bibliographystyle{{plain}}
\\bibliography{{$bibliography$}}
$endif$

\\end{{document}}
"""
        return template
    
    def _build_pandoc_options(self, template: Template, metadata: Metadata) -> List[str]:
        """Build pandoc command-line options."""
        options = []
        
        # Basic options
        options.extend(['--from', 'markdown'])
        options.extend(['--to', 'latex'])
        
        # Template-specific options
        if template.template_type == TemplateType.LATEX:
            options.extend(['--template', template.name])
        
        # Metadata options
        if metadata.bibliography:
            if isinstance(metadata.bibliography, list):
                for bib in metadata.bibliography:
                    options.extend(['--bibliography', str(bib)])
            else:
                options.extend(['--bibliography', str(metadata.bibliography)])
        
        if metadata.csl:
            options.extend(['--csl', str(metadata.csl)])
        
        # Citation processing
        options.append('--citeproc')
        
        # PDF engine
        options.extend(['--pdf-engine', 'xelatex'])
        
        # Include table of contents if specified in metadata
        if metadata.raw_metadata.get('toc', False):
            options.append('--toc')
        
        # Number sections if specified
        if metadata.raw_metadata.get('number-sections', False):
            options.append('--number-sections')
        
        return options
    
    def _build_latex_options(self, template: Template, metadata: Metadata) -> List[str]:
        """Build LaTeX-specific options."""
        options = []
        
        # XeLaTeX options
        options.extend(['-interaction=nonstopmode'])
        
        # Output directory handling
        options.extend(['-output-directory', '.'])
        
        return options