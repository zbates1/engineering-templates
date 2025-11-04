"""
File validation module for markdown-to-PDF pipeline.

This module provides comprehensive validation of markdown files and their dependencies,
ensuring they meet processing requirements before entering the conversion pipeline.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any, NamedTuple
import re
import yaml
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in a file."""
    severity: ValidationSeverity
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None


class ValidationResult(NamedTuple):
    """Result of file validation."""
    is_valid: bool
    issues: List[ValidationIssue]
    metadata: Optional[Dict[str, Any]] = None


class ReferenceCheck(NamedTuple):
    """Result of reference validation."""
    missing_images: List[Path]
    missing_bibliography: List[Path]
    broken_links: List[str]
    all_references_valid: bool


class FileValidator:
    """
    Validates markdown files and their dependencies for processing pipeline.
    
    Performs comprehensive validation including:
    - Markdown syntax validation
    - YAML frontmatter validation
    - Image reference checking
    - Bibliography file verification
    - Link validation
    """
    
    def __init__(self):
        self.supported_image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.pdf'}
        self.supported_bib_extensions = {'.bib', '.json', '.yaml', '.yml'}
        
        # Common markdown patterns
        self.image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        self.link_pattern = re.compile(r'(?<!!)\[([^\]]*)\]\(([^)]+)\)')
        self.citation_pattern = re.compile(r'@[\w-]+')
        self.yaml_delimiter_pattern = re.compile(r'^---\s*$', re.MULTILINE)
    
    def validate_markdown(self, path: Path) -> ValidationResult:
        """
        Validate a markdown file for syntax and structure.
        
        Args:
            path: Path to the markdown file
            
        Returns:
            ValidationResult containing validation status and any issues
        """
        if not path.exists():
            return ValidationResult(
                is_valid=False,
                issues=[ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"File does not exist: {path}"
                )]
            )
        
        if not path.is_file():
            return ValidationResult(
                is_valid=False,
                issues=[ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Path is not a file: {path}"
                )]
            )
        
        if path.suffix.lower() not in {'.md', '.markdown'}:
            return ValidationResult(
                is_valid=False,
                issues=[ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"File is not a markdown file: {path.suffix}"
                )]
            )
        
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as e:
            return ValidationResult(
                is_valid=False,
                issues=[ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Unable to decode file as UTF-8: {e}"
                )]
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                issues=[ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Error reading file: {e}"
                )]
            )
        
        issues = []
        metadata = None
        
        # Validate YAML frontmatter if present
        yaml_result = self._validate_yaml_frontmatter(content)
        if yaml_result.issues:
            issues.extend(yaml_result.issues)
        metadata = yaml_result.metadata
        
        # Validate markdown structure
        structure_issues = self._validate_markdown_structure(content)
        issues.extend(structure_issues)
        
        # Check for common markdown issues
        syntax_issues = self._validate_markdown_syntax(content)
        issues.extend(syntax_issues)
        
        # Determine overall validity
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        
        return ValidationResult(
            is_valid=not has_errors,
            issues=issues,
            metadata=metadata
        )
    
    def check_references(self, md_path: Path) -> ReferenceCheck:
        """
        Check all references (images, bibliography) in a markdown file.
        
        Args:
            md_path: Path to the markdown file
            
        Returns:
            ReferenceCheck containing information about missing references
        """
        if not md_path.exists():
            return ReferenceCheck([], [], [], False)
        
        try:
            content = md_path.read_text(encoding='utf-8')
        except Exception:
            return ReferenceCheck([], [], [], False)
        
        base_dir = md_path.parent
        
        # Find image references
        missing_images = []
        for match in self.image_pattern.finditer(content):
            image_path_str = match.group(2)
            
            # Skip URLs
            if image_path_str.startswith(('http://', 'https://', 'ftp://')):
                continue
            
            image_path = base_dir / image_path_str
            if not image_path.exists():
                missing_images.append(Path(image_path_str))
        
        # Find bibliography references from frontmatter
        missing_bibliography = []
        metadata = self._extract_yaml_frontmatter(content)
        if metadata and 'bibliography' in metadata:
            bib_refs = metadata['bibliography']
            if isinstance(bib_refs, str):
                bib_refs = [bib_refs]
            elif not isinstance(bib_refs, list):
                bib_refs = []
            
            for bib_ref in bib_refs:
                bib_path = base_dir / bib_ref
                if not bib_path.exists():
                    missing_bibliography.append(Path(bib_ref))
        
        # Check for broken internal links
        broken_links = []
        for match in self.link_pattern.finditer(content):
            link_url = match.group(2)
            
            # Skip external URLs
            if link_url.startswith(('http://', 'https://', 'ftp://', 'mailto:')):
                continue
            
            # Check internal file references
            if '#' in link_url:
                link_url = link_url.split('#')[0]
            
            if link_url and not link_url.startswith('#'):
                link_path = base_dir / link_url
                if not link_path.exists():
                    broken_links.append(link_url)
        
        all_valid = (
            len(missing_images) == 0 and
            len(missing_bibliography) == 0 and
            len(broken_links) == 0
        )
        
        return ReferenceCheck(
            missing_images=missing_images,
            missing_bibliography=missing_bibliography,
            broken_links=broken_links,
            all_references_valid=all_valid
        )
    
    def ensure_output_directory(self, path: Path) -> bool:
        """
        Ensure output directory exists and is writable.
        
        Args:
            path: Path to the output directory
            
        Returns:
            True if directory exists and is writable, False otherwise
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            # Test write permissions
            test_file = path / '.write_test'
            test_file.write_text('test')
            test_file.unlink()
            
            return True
        except Exception:
            return False
    
    def _validate_yaml_frontmatter(self, content: str) -> ValidationResult:
        """Validate YAML frontmatter in markdown content."""
        issues = []
        metadata = None
        
        # Check if frontmatter exists
        if not content.startswith('---'):
            # Add warnings for missing title/author since there's no frontmatter
            issues.append(ValidationIssue(
                ValidationSeverity.WARNING,
                "Missing 'title' in frontmatter",
                suggestion="Add a title field for proper document formatting"
            ))
            issues.append(ValidationIssue(
                ValidationSeverity.WARNING,
                "Missing 'author' in frontmatter", 
                suggestion="Add an author field for proper document attribution"
            ))
            return ValidationResult(True, issues, metadata)
        
        # Extract frontmatter
        yaml_matches = list(self.yaml_delimiter_pattern.finditer(content))
        if len(yaml_matches) < 2:
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "YAML frontmatter not properly closed with '---'"
            ))
            return ValidationResult(False, issues, metadata)
        
        yaml_content = content[yaml_matches[0].end():yaml_matches[1].start()].strip()
        
        try:
            metadata = yaml.safe_load(yaml_content)
            if metadata is None:
                metadata = {}
        except yaml.YAMLError as e:
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                f"Invalid YAML frontmatter: {e}"
            ))
            return ValidationResult(False, issues, metadata)
        
        # Validate common metadata fields
        if isinstance(metadata, dict):
            if 'title' not in metadata:
                issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    "Missing 'title' in frontmatter",
                    suggestion="Add a title field for proper document formatting"
                ))
            
            if 'author' not in metadata:
                issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    "Missing 'author' in frontmatter",
                    suggestion="Add an author field for proper document attribution"
                ))
        else:
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "YAML frontmatter must be a dictionary"
            ))
        
        has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        return ValidationResult(not has_errors, issues, metadata)
    
    def _validate_markdown_structure(self, content: str) -> List[ValidationIssue]:
        """Validate markdown document structure."""
        issues = []
        lines = content.split('\n')
        
        # Check for basic structure elements
        has_headers = any(line.strip().startswith('#') for line in lines)
        if not has_headers:
            issues.append(ValidationIssue(
                ValidationSeverity.WARNING,
                "Document has no headers",
                suggestion="Add section headers for better document structure"
            ))
        
        # Check for very short documents
        non_empty_lines = [line for line in lines if line.strip()]
        if len(non_empty_lines) < 5:
            issues.append(ValidationIssue(
                ValidationSeverity.WARNING,
                "Document appears to be very short",
                suggestion="Consider adding more content or verify this is intentional"
            ))
        
        return issues
    
    def _validate_markdown_syntax(self, content: str) -> List[ValidationIssue]:
        """Validate markdown syntax for common issues."""
        issues = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for unbalanced brackets in links/images
            if '[' in line or ']' in line:
                open_brackets = line.count('[')
                close_brackets = line.count(']')
                if open_brackets != close_brackets:
                    issues.append(ValidationIssue(
                        ValidationSeverity.WARNING,
                        "Unbalanced brackets in markdown syntax",
                        line_number=line_num,
                        suggestion="Check link or image syntax"
                    ))
            
            # Check for unbalanced parentheses in links/images
            # Only check lines with markdown link syntax
            if '](' in line:
                # Find all ]( patterns and check their parentheses
                link_start = 0
                while True:
                    link_pos = line.find('](', link_start)
                    if link_pos == -1:
                        break
                    
                    # Count parentheses from this position to end of line
                    remaining = line[link_pos + 2:]
                    open_parens = remaining.count('(')
                    close_parens = remaining.count(')')
                    
                    # Find the first closing parenthesis for this link
                    close_pos = remaining.find(')')
                    if close_pos == -1:
                        issues.append(ValidationIssue(
                            ValidationSeverity.WARNING,
                            "Unclosed parenthesis in link/image syntax",
                            line_number=line_num,
                            suggestion="Add closing parenthesis ')'"
                        ))
                    
                    link_start = link_pos + 2
        
        return issues
    
    def _extract_yaml_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter from markdown content."""
        if not content.startswith('---'):
            return None
        
        yaml_matches = list(self.yaml_delimiter_pattern.finditer(content))
        if len(yaml_matches) < 2:
            return None
        
        yaml_content = content[yaml_matches[0].end():yaml_matches[1].start()].strip()
        
        try:
            return yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError:
            return None