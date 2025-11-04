# Markdown-to-PDF Pipeline

A command-line tool for batch processing Markdown files into professionally formatted PDFs using Pandoc and XeLaTeX.

## Features

- **Batch Processing**: Process multiple .md files from a specified input directory
- **Configurable Directories**: Set custom input and output directories via command-line arguments
- **Bibliography Support**: Full BibTeX and CSL citation processing
- **Template System**: Professional LaTeX templates for consistent formatting
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Quick Start

```bash
# Process all .md files in current directory, output to ./output/
md2pdf

# Process files from custom input directory
md2pdf --input-dir ./docs --output-dir ./pdfs

# Process with specific template
md2pdf -i ./content -o ./results --template academic
```

## Installation

### Prerequisites
```bash
# Install Pandoc (version 3.1.12.2+)
wget https://github.com/jgm/pandoc/releases/download/3.1.12.2/pandoc-3.1.12.2-1-amd64.deb
sudo dpkg -i pandoc-3.1.12.2-1-amd64.deb || sudo apt -f install -y

# Install XeLaTeX and fonts
sudo apt install -y texlive-xetex texlive-latex-recommended texlive-fonts-recommended texlive-fonts-extra

# Alternative: Use Tectonic for faster builds
sudo snap install tectonic
```

### Install Pipeline
```bash
pip install markdown-pdf-pipeline
# or
git clone <repository> && cd markdown-pdf-pipeline && pip install -e .
```

## File Structure

Your project directory can be organized like this:
```
project/
├── content/              # Input .md files
│   ├── chapter1.md
│   ├── chapter2.md
│   └── images/           # Referenced images
├── bibliography/
│   └── refs.bib          # BibTeX references
├── output/               # Generated PDFs
└── templates/            # Custom LaTeX templates (optional)
```

## Markdown Format

### Frontmatter (YAML)
```yaml
---
title: "Document Title"
author: "Your Name"
date: "2025-09-05"
bibliography: refs.bib
csl: ieee.csl
---
```

### Citations
- Inline: `Smith et al. [@smith2024] showed that...`
- Multiple: `[@smith2024; @jones2023]`
- Parenthetical: `This is well established [@smith2024].`

### Math Support
- Inline: `The equation $E = mc^2$ shows...`
- Display: `$$\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}$$`

## Command-Line Options

```bash
md2pdf [OPTIONS]

Options:
  -i, --input-dir PATH     Input directory containing .md files [default: current directory]
  -o, --output-dir PATH    Output directory for PDFs [default: ./output]
  -t, --template NAME      LaTeX template to use [default: default]
  --bib-dir PATH           Directory containing bibliography files
  --clean                  Remove temporary files after processing
  --verbose                Show detailed processing information
  --help                   Show this message and exit
```

## Bibliography Management

### Zotero + Better BibTeX (Recommended)
1. Install **Better BibTeX** plugin in Zotero
2. Configure auto-export to `refs.bib` in your project
3. Use citation keys like `@smith2024` in your Markdown

### Manual BibTeX
Create a `refs.bib` file:
```bibtex
@article{smith2024,
  title={Advanced Markdown Processing},
  author={Smith, John and Doe, Jane},
  journal={Journal of Document Processing},
  year={2024},
  volume={15},
  pages={123--145}
}
```

## Templates

Built-in templates:
- `default`: Clean, professional layout
- `academic`: Suitable for research papers
- `proposal`: Formatted for project proposals
- `minimal`: Lightweight design

### Custom Templates
Place `.tex` files in the `templates/` directory and reference them with `--template custom_name`.

## Error Handling

The pipeline provides detailed feedback:
- File validation errors
- Missing dependencies
- Citation resolution issues
- LaTeX compilation problems

## Integration

### GitHub Actions
```yaml
name: Build PDFs
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Dependencies
        run: |
          sudo apt-get install -y pandoc texlive-xetex
      - name: Build PDFs
        run: md2pdf --input-dir content --output-dir dist
```

### Make Integration
```makefile
.PHONY: pdf clean
pdf:
	md2pdf --input-dir content --output-dir output --clean

clean:
	rm -rf output/ temp/
```

---

*Transform your Markdown documents into beautiful PDFs with a single command.*
