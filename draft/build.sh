#!/bin/sh
# Rebuild the Paper 2 draft from the results (run from Paper2/):  sh draft/build.sh
# 1. numbers and tables  2. figures  3. bibliography  4. PDF  5. Word copy (pandoc, IEEE CSL)
set -e
python -I src/paper/paper_numbers.py
python -I src/paper/make_figures.py
(cd draft/bib && python -I build_bib.py)
python -I src/paper/check_draft.py draft
cd draft
mkdir -p deliverables build
# supplement first (its labels are referenced by the paper through xr), then the paper, then both again
pdflatex -interaction=nonstopmode supplement.tex > build_s1.log
bibtex supplement > bib_s.log
pdflatex -interaction=nonstopmode main.tex > build1.log
bibtex main > bib.log
pdflatex -interaction=nonstopmode supplement.tex > build_s2.log
pdflatex -interaction=nonstopmode main.tex > build2.log
pdflatex -interaction=nonstopmode supplement.tex > build_s3.log
pdflatex -interaction=nonstopmode main.tex > build3.log
if grep -q "^!" supplement.log; then echo "LaTeX errors in the supplement: see draft/supplement.log"; exit 1; fi
if grep -qi "undefined" supplement.log; then echo "undefined references in the supplement: see draft/supplement.log"; exit 1; fi
cp supplement.pdf deliverables/Paper2_supplement_v0.3.pdf
if grep -q "^!" main.log; then echo "LaTeX errors: see draft/main.log"; exit 1; fi
if grep -qi "undefined" main.log; then echo "undefined references or citations: see draft/main.log"; exit 1; fi
cp main.pdf deliverables/Paper2_draft_v0.3.pdf
# TGCN review copy: single column, double spaced, 12 pt (derived from main.tex)
python -I ../src/paper/make_review_copy.py main.tex main_review.tex
pdflatex -interaction=nonstopmode main_review.tex > build_r1.log
bibtex main_review > bib_r.log
pdflatex -interaction=nonstopmode main_review.tex > build_r2.log
pdflatex -interaction=nonstopmode main_review.tex > build_r3.log
if grep -q "^!" main_review.log; then echo "LaTeX errors in the review copy: see draft/main_review.log"; exit 1; fi
cp main_review.pdf deliverables/Paper2_TGCN_review_copy_v0.3.pdf
python -I ../src/paper/make_word.py . word_main.tex
pandoc word_main.tex -f latex -t docx --citeproc --bibliography=refs.bib --csl=ieee.csl --resource-path=. \
  -M reference-section-title=References -o word_raw.docx
# IEEE layout for the Word copy: fonts, two columns, numbered equations, captions, table rules, header
python -I ../src/paper/fix_word.py word_raw.docx deliverables/Paper2_draft_v0.3.docx \
  "$(python -I -c 'import json; print(json.load(open("word_main.tex.json"))["equations"])')"
python -I ../src/paper/fix_word.py word_raw.docx deliverables/Paper2_TGCN_review_copy_v0.3.docx \
  "$(python -I -c 'import json; print(json.load(open("word_main.tex.json"))["equations"])')" review
rm -f word_main.tex word_main.tex.json word_raw.docx
mv -f *.aux *.bbl *.blg *.log *.out texput.log main_review.tex build/ 2>/dev/null || true
echo "built draft/deliverables/, with LaTeX intermediates in draft/build/"
