<p align="center">
  <img src="images/cmu_logo.png" alt="CMU Logo" width="200"/>
</p>


# Proposals Starter (Markdown → Pandoc → PDF)

This repo is a ready-to-go template for writing in **Markdown** (exported from Notion) and compiling gorgeous PDFs via **Pandoc** + **XeLaTeX**.

## Folder Layout
```
/closed-loop-bioink-proposal/
  index.md         # Paste your Notion-exported Markdown here (or edit directly)
  meta.yaml        # Title, author, TOC, margins, etc.
  refs.bib         # Your BibTeX references (use Zotero + Better BibTeX)
  template.tex     # Pandoc LaTeX template
  images/          # Drop images referenced from Markdown
  .github/workflows/build.yml  # Optional CI to build on every push
  Makefile         # 'make pdf' builds proposal.pdf
```

## Setup
wget https://github.com/jgm/pandoc/releases/download/3.1.12.2/pandoc-3.1.12.2-1-amd64.deb
sudo dpkg -i pandoc-3.1.12.2-1-amd64.deb || sudo apt -f install -y
sudo snap install tectonic
sudo apt install -y texlive-xetex texlive-latex-recommended texlive-fonts-recommended texlive-fonts-extra

## Using with Notion
1. Write in Notion using headings, lists, and inline math (`$...$`) or display math (`$$...$$`).
2. **Export** → *Markdown & CSV*.
3. Drop the exported `index.md` + `images/` into this folder (replace the starter files).
4. Run `make pdf` (or the pandoc command above).

## Citations
- Manage references in **Zotero** with **Better BibTeX**.
- Set your library/collection to auto‑export to `refs.bib` in this folder.
- Cite inline like `[@key]` or "Smith (2024) [@key]". Choose a CSL (e.g., `ieee.csl`, `nature.csl`).

## Customization
- Adjust fonts/margins/colors in `template.tex`.
- Add front‑matter in `meta.yaml` (title, authors, keywords, TOC).
- Add Make targets (e.g., `make docx`) if you want other outputs.

---

*Generated 2025-08-29. Replace placeholders as needed.*
