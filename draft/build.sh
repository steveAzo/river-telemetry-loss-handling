#!/bin/sh
# Rebuild the Paper 2 draft from the results (run from Paper2/):  sh draft/build.sh
# 1. numbers and tables  2. figures  3. bibliography  4. PDFs  5. Word submission copy (pandoc, Springer numeric CSL)
# Deliverables (draft/deliverables/): the Wireless Networks Word submission copy, the two-column PDF, the double-spaced PDF.
# Older versions live in draft/archive/versions/.
set -e
V=v0.5
# revision 3: numbers, tables, and figures from the corrected post hoc runs (src/revision3/)
python -I src/revision3/corrected_numbers.py --adopt
python -I src/revision3/run_figures.py
(cd draft/bib && python -I build_bib.py)
python -I src/paper/check_draft.py draft
cd draft
mkdir -p deliverables build
pdflatex -interaction=nonstopmode main.tex > build1.log
bibtex main > bib.log
pdflatex -interaction=nonstopmode main.tex > build2.log
pdflatex -interaction=nonstopmode main.tex > build3.log
if grep -q "^!" main.log; then echo "LaTeX errors: see draft/main.log"; exit 1; fi
if grep -qi "undefined" main.log; then echo "undefined references or citations: see draft/main.log"; exit 1; fi
cp main.pdf deliverables/Paper2_${V}_two-column.pdf
# double-spaced copy: single column, 10 pt (derived from main.tex)
python -I ../src/paper/make_review_copy.py main.tex main_review.tex
pdflatex -interaction=nonstopmode main_review.tex > build_r1.log
bibtex main_review > bib_r.log
pdflatex -interaction=nonstopmode main_review.tex > build_r2.log
pdflatex -interaction=nonstopmode main_review.tex > build_r3.log
if grep -q "^!" main_review.log; then echo "LaTeX errors in the review copy: see draft/main_review.log"; exit 1; fi
cp main_review.pdf deliverables/Paper2_${V}_double-spaced.pdf
# Word submission copy for Wireless Networks: decimal headings, Arabic table numbers, Springer numeric references
python -I ../src/paper/make_word.py . word_main.tex springer
pandoc word_main.tex -f latex -t docx --citeproc --bibliography=refs.bib --csl=springer-basic-brackets.csl --resource-path=. \
  -M reference-section-title=References -o word_raw.docx
python -I ../src/paper/fix_word.py word_raw.docx deliverables/Paper2_${V}_WirelessNetworks.docx \
  "$(python -I -c 'import json; print(json.load(open("word_main.tex.json"))["equations"])')" springer
rm -f word_main.tex word_main.tex.json word_raw.docx
mv -f *.aux *.bbl *.blg *.log *.out texput.log main_review.tex build/ 2>/dev/null || true
echo "built draft/deliverables/, with LaTeX intermediates in draft/build/"
