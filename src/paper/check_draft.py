"""Consistency checks on the Paper 2 manuscript sources (run by draft/build.sh; exits non-zero on failure).

  - every table, figure, algorithm and equation label is referenced in the text, and every \\ref has a label;
  - every \\cite key is in refs.bib, and every refs.bib entry is cited;
  - every macro used is defined in numbers.tex;
  - the paper is standalone: no citation of, or wording about, the companion study (Paper 1);
  - no bold in running text (bold is allowed only in tables, for the best value, and in algorithm keywords);
  - no italics in running text, no period-ended paragraph labels, "Section" not "Sec." (supervisor, 2026-10-23);
  - no first-person wording ("we", "our", "us", or "the authors" as a stand-in) and no "thesis";
    the abstract is about 200 words (180-220).
Usage (from Paper2/): python -I src/paper/check_draft.py draft
"""
import glob
import re
import sys

d = sys.argv[1] if len(sys.argv) > 1 else "draft"
tex = {f: open(f, encoding="utf-8").read() for f in sorted(glob.glob(f"{d}/*.tex")) if not f.endswith(("numbers.tex", "word_main.tex"))}
alltex = "\n".join(tex.values())
tables = "\n".join(open(f, encoding="utf-8").read() for f in glob.glob(f"{d}/tables/*.tex"))
fail = []

labels = re.findall(r"\\label\{([^}]+)\}", alltex)
refs = set(re.findall(r"\\ref\{([^}]+)\}", alltex))
dup = sorted({l for l in labels if labels.count(l) > 1})
if dup:
    fail.append(f"duplicate labels: {dup}")
if refs - set(labels):
    fail.append(f"references without a label: {sorted(refs - set(labels))}")
unref = sorted(l for l in set(labels) - refs if l.split(":")[0] in ("tab", "fig", "alg", "eq"))
if unref:
    fail.append(f"tables/figures/algorithms/equations never referenced: {unref}")

cites = {k.strip() for g in re.findall(r"\\cite\{([^}]+)\}", alltex) for k in g.split(",")}
bib = set(re.findall(r"^@\w+\{([^,]+),", open(f"{d}/refs.bib", encoding="utf-8").read(), re.M))
if cites - bib:
    fail.append(f"citations missing from refs.bib: {sorted(cites - bib)}")
if bib - cites:
    fail.append(f"refs.bib entries never cited: {sorted(bib - cites)}")

defined = set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", open(f"{d}/numbers.tex", encoding="utf-8").read()))
latex_ok = set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", alltex))
used = set(re.findall(r"\\([A-Za-z]+)", alltex + tables))
# macros named like ours (camelCase with a capital) that are not defined anywhere
ours = {m for m in used if re.match(r"^[a-z]+[A-Z]", m)}
if ours - defined - latex_ok - {"addlinespace", "makeatletter", "makeatother", "columnwidth", "textwidth", "graphicspath",
                               "bibliographystyle", "maketitle", "markboth", "noalign", "cmidrule", "setlength",
                               "tabcolsep", "operatorname", "mathrm", "includegraphics", "bottomrule", "toprule", "midrule"}:
    fail.append(f"undefined number macros: {sorted(ours - defined - latex_ok)}")

for f, s in tex.items():
    if re.search(r"adumanu2026|companion (study|manuscript|paper)|Paper~?1", s, re.I):
        fail.append(f"{f}: mentions or cites Paper 1 (this paper is standalone)")
    body = re.sub(r"\\begin\{algorithmic\}.*?\\end\{algorithmic\}", "", s, flags=re.S)
    body = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", "", body, flags=re.S)
    broken = re.findall(r"(?<![\\A-Za-z])(ef|egin|abel|ite|extbf)\{", s)   # e.g. "\ref" turned into a CR + "ef{"
    if broken:
        fail.append(f"{f}: a LaTeX command lost its backslash: {sorted(set(broken))}")
    if "\\textbf" in body:
        fail.append(f"{f}: bold in running text")
    # the supervisor's writing rules (2026-10-23): no italics in prose; lists as itemize/enumerate;
    # a paragraph label ends with a colon; "Section", not "Sec."
    for cmd in ("\\emph{", "\\textit{", "\\itshape", "{\\it "):
        if cmd in body:
            fail.append(f"{f}: italics in running text ({cmd.strip('{ ')})")
    labels_period = re.findall(r"(?m)^(?:\\item\s+)?([A-Z][A-Za-z ,()0-9-]{1,40})\.\s+[A-Z]", body)
    labels_period = [l for l in labels_period if len(l.split()) <= 4 and not re.search(r"\b(is|are|was|were|has|had)\b", l)]
    if labels_period:
        fail.append(f"{f}: paragraph labels ending in a period instead of a colon: {labels_period}")
    if re.search(r"Secs?\.~", s):
        fail.append(f"{f}: write 'Section'/'Sections', not 'Sec.'/'Secs.'")
    body_text = re.sub(r"\\thanks\{.*?\}\}", "", s, flags=re.S)  # the affiliation note may name the authors
    words = sorted({w.lower() for w in re.findall(r"\b(we|our|ours|us|ourselves|thesis|the authors'?)(?=\W)", body_text, re.I)})
    if words:
        fail.append(f"{f}: first-person or 'thesis' wording: {words}")

abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", alltex, re.S).group(1)
n_abstract = len(re.sub(r"\\[A-Za-z]+(\{\})?", "X", abstract).split())  # a number macro counts as one word
if not 180 <= n_abstract <= 220:
    fail.append(f"abstract has {n_abstract} words (target about 200)")

print(f"labels {len(set(labels))}, references {len(refs)}, citations {len(cites)} of {len(bib)} bib entries, "
      f"equations {len([l for l in labels if l.startswith('eq:')])}, figures {len([l for l in labels if l.startswith('fig:')])}, "
      f"tables {len([l for l in labels if l.startswith('tab:')])}, algorithms {len([l for l in labels if l.startswith('alg:')])}")
if fail:
    print("FAILED:\n  " + "\n  ".join(fail))
    sys.exit(1)
print("draft checks passed")
