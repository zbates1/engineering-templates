@echo off
echo Building PDF from Markdown...
echo.

REM Check if required files exist
if not exist "index.md" (
    echo ERROR: index.md not found!
    exit /b 1
)

if not exist "meta.yaml" (
    echo ERROR: meta.yaml not found!
    exit /b 1
)

if not exist "ieee.csl" (
    echo ERROR: ieee.csl not found!
    exit /b 1
)

if not exist "template-basic.tex" (
    echo ERROR: template-basic.tex not found!
    exit /b 1
)

if not exist "refs.bib" (
    echo ERROR: refs.bib not found!
    exit /b 1
)

REM Run pandoc with working configuration
echo Running pandoc...
pandoc index.md --from markdown+tex_math_dollars --pdf-engine=pdflatex --citeproc --bibliography=refs.bib --csl=ieee.csl --metadata-file=meta.yaml --template=template-basic.tex -o proposal.pdf

if %ERRORLEVEL% equ 0 (
    echo.
    echo SUCCESS: PDF generated successfully!
    echo Output: proposal.pdf
    if exist proposal.pdf (
        for %%A in (proposal.pdf) do echo File size: %%~zA bytes
    )
) else (
    echo.
    echo ERROR: PDF generation failed!
    exit /b 1
)