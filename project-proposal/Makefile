pdf:
	pandoc index.md --from markdown+tex_math_dollars \
	--pdf-engine=pdflatex --citeproc --bibliography=refs.bib \
	--csl=ieee.csl --metadata-file=meta.yaml --template=template-basic.tex \
	-o proposal.pdf
