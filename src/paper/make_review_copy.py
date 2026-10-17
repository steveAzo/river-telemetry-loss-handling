"""TGCN review copy (single column, double spaced, 12 pt, no draft banner) derived from draft/main.tex, so the two
versions cannot drift apart. Usage (from Paper2/draft): python -I ../src/paper/make_review_copy.py main.tex main_review.tex
"""
import sys

src, dst = sys.argv[1:3]
s = open(src, encoding="utf-8").read()
old = r"\documentclass[journal]{IEEEtran}"
assert old in s
s = s.replace(old, r"\documentclass[journal,12pt,onecolumn,draftclsnofoot]{IEEEtran}" + "\n" + r"\usepackage{setspace}")
s = s.replace(r"\begin{document}", r"\begin{document}" + "\n" + r"\doublespacing", 1)
lines = [l for l in s.split("\n") if not l.startswith(r"\markboth")]
open(dst, "w", encoding="utf-8").write("\n".join(lines))
print("wrote", dst)
