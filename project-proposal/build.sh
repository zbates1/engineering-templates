#!/bin/bash

echo "Building PDF from Markdown..."
echo ""

# Check if required files exist
if [ ! -f "index.md" ]; then
    echo "ERROR: index.md not found!"
    exit 1
fi

if [ ! -f "meta.yaml" ]; then
    echo "ERROR: meta.yaml not found!"
    exit 1
fi

if [ ! -f "ieee.csl" ]; then
    echo "ERROR: ieee.csl not found!"
    exit 1
fi

if [ ! -f "template-basic.tex" ]; then
    echo "ERROR: template-basic.tex not found!"
    exit 1
fi

if [ ! -f "refs.bib" ]; then
    echo "ERROR: refs.bib not found!"
    exit 1
fi

# Run pandoc with working configuration
echo "Running pandoc..."
pandoc index.md \
    --from markdown+tex_math_dollars \
    --pdf-engine=pdflatex \
    --citeproc \
    --bibliography=refs.bib \
    --csl=ieee.csl \
    --metadata-file=meta.yaml \
    --template=template-basic.tex \
    -o proposal.pdf

if [ $? -eq 0 ]; then
    echo ""
    echo "SUCCESS: PDF generated successfully!"
    echo "Output: proposal.pdf"
    if [ -f "proposal.pdf" ]; then
        echo "File size: $(stat -f%z proposal.pdf 2>/dev/null || stat -c%s proposal.pdf 2>/dev/null) bytes"
    fi
else
    echo ""
    echo "ERROR: PDF generation failed!"
    exit 1
fi