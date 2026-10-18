"""Flatten draft/main.tex for pandoc (Word copy). LaTeX-only constructs are mapped mechanically from the
same source, so the Word text cannot drift from the PDF:
  sections and generated tables inlined; numbers.tex inlined; figures -> PNG;
  every \\ref resolved to the number LaTeX printed (from main.aux), section headings numbered as in the PDF;
  align/gather split into one display per equation number (rows marked \\nonumber stay with the next row);
  the algorithm -> a numbered list with its caption.
Layout the Word writer cannot express is passed to src/paper/fix_word.py as @@...@@ markers:
  @@TAB:<num>:<W|N>:<S|M>@@ / @@FIG:<num>:<W|N>@@ at the start of captions (W: full width, S: small table font),
  @@NOIND@@ on text that continues a paragraph after a display equation, @@KW@@ (index terms),
  @@RQ:<label>@@ (labelled list items), @@ALG@@ (algorithm caption); display equation k gets number k."""
import json
import re
import sys

d, out = sys.argv[1], sys.argv[2]
s = open(f"{d}/main.tex", encoding="utf-8").read()
s = s.replace(r"\makeatletter\newcommand{\tabin}[1]{\@@input #1 }\makeatother", "")
s = s.replace(r"\input{numbers}", open(f"{d}/numbers.tex", encoding="utf-8").read())
s = re.sub(r"\\markboth\{[^}]*\}\{\}", "", s)


def inline(m):
    t = open(f"{d}/{m.group(1)}.tex", encoding="utf-8").read()
    return re.sub(r"\\tabin\{tables/([a-z_]+)\.tex\}", lambda k: open(f"{d}/tables/{k.group(1)}.tex", encoding="utf-8").read(), t)


s = re.sub(r"\\input\{(sec_[a-z]+)\}", inline, s)
s = re.sub(r"\\includegraphics(\[[^\]]*\])?\{(fig_[a-z_]+)\}", lambda m: r"\includegraphics" + (m.group(1) or "") + "{figs/" + m.group(2) + ".png}", s)

# numbers as LaTeX printed them
aux = {}
for auxf in ("supplement.aux", "main.aux"):         # the supplement's labels (S1, Table S1, ...) are cited by the paper
    aux.update({k: re.sub(r"\\mbox\s*\{([^}]*)\}", r"\1", v) for k, v in
                re.findall(r"\\newlabel\{([^}]+)\}\{\{((?:[^{}]|\{[^{}]*\})*)\}", open(f"{d}/{auxf}", encoding="utf-8").read())})
s = s.replace(r"\IEEEPARstart{R}{iver}", "River")
# pandoc does not know \newcolumntype: drop the definition and use plain p{} columns for the Word copy
s = re.sub(r"\\newcolumntype\{L\}\[1\]\{[^\n]*\n", "", s)
s = re.sub(r"L\{([0-9.]+cm)\}", r"p{\1}", s)
s = s.replace(r"\frac12", r"\tfrac12")          # Word sets a display \frac12 at full height; LaTeX keeps it small
assert r"\IEEEPARstart" not in s
s = re.sub(r"\\begin\{IEEEkeywords\}\s*(.*?)\s*\\end\{IEEEkeywords\}", r"@@KW@@\1", s, flags=re.S)
s = re.sub(r"\\item\[(RQ\d)\]\s*", r"\n\n@@RQ:\1@@", s)
s = re.sub(r"\\begin\{enumerate\}\s*(?=\n\n@@RQ)", "", s)
s = re.sub(r"(@@RQ:RQ4@@[^\n]*)\n\\end\{enumerate\}", r"\1\n", s)


def number_headings(s):
    sec, sub = 0, 0
    def h(m):
        nonlocal sec, sub
        kind, title = m.group(1), m.group(2)
        if kind == "section":
            sec, sub = sec + 1, 0
            num = aux[re.search(r"\\label\{([^}]+)\}", s[m.end():m.end() + 80]).group(1)]
            return rf"\section*{{{num}. {title}}}"
        sub += 1
        return rf"\subsection*{{{chr(64 + sub)}. {title}}}"
    return re.sub(r"\\(section|subsection)\{([^{}]*)\}", h, s)


s = number_headings(s)

# captions carry the float number and layout
def mark_float(m):
    env, body = m.group(1), m.group(2)
    label = re.search(r"\\label\{([^}]+)\}", body).group(1)
    wide = "W" if env.endswith("*") else "N"
    if env.startswith("table"):
        size = "S" if r"\scriptsize" in body else "M"
        tag = f"@@TAB:{aux[label]}:{wide}:{size}@@"
    else:
        tag = f"@@FIG:{aux[label]}:{wide}@@"
    body = body.replace(r"\caption{", r"\caption{" + tag, 1)
    body = re.sub(r"\\cmidrule(\([lr]+\))?\{[^}]*\}", "", body)
    body = re.sub(r"\\setlength\{\\tabcolsep\}\{[^}]*\}|\\scriptsize|\\small|\\addlinespace", "", body)
    return "\\begin{" + env.rstrip("*") + "}[t]" + body + "\\end{" + env.rstrip("*") + "}"


s = re.sub(r"\\begin\{(table\*?|figure\*?)\}\[t\](.*?)\\end\{\1\}", mark_float, s, flags=re.S)


def algo(m):
    body = m.group(0)
    cap = re.search(r"\\caption\{(.*?)\}\n", body).group(1)
    steps = re.search(r"\\begin\{algorithmic\}\[1\]\n(.*?)\\end\{algorithmic\}", body, re.S).group(1)
    items = []
    for line in steps.strip().split("\n"):
        x = line.strip()
        x = re.sub(r"\\If\{(.*)\}\s*\\State\s*(.*?)\s*\\EndIf", r"\\textbf{if} \1 \\textbf{then} \2; \\textbf{end if}", x)
        x = re.sub(r"\\If\{(.*)\}", r"\\textbf{if} \1 \\textbf{then}", x)
        x = x.replace(r"\EndIf", r"\textbf{end if}").replace(r"\State ", "").replace(r"\Return", r"\textbf{return}")
        items.append(r"\item " + x)
    return ("@@ALG@@\\textbf{Algorithm " + aux["alg:design"] + "} " + cap + "\n\\begin{enumerate}\n" + "\n".join(items) + "\n\\end{enumerate}\n")


s = re.sub(r"\\begin\{algorithm\}\[t\].*?\\end\{algorithm\}\n", algo, s, flags=re.S)

# display equations: one display per number, numbers checked against main.aux
numbers = []


def equations(m):
    env, body, after = m.group(1), m.group(2), m.group(3)
    rows = [body] if env == "equation" else re.split(r"\\\\\s*\n", body.strip())
    groups, cur = [], []
    for r in rows:
        cur.append(r)
        if r"\nonumber" not in r:
            groups.append(cur); cur = []
    assert not cur, "trailing \\nonumber row"
    disp = []
    for g in groups:
        lab = re.search(r"\\label\{([^}]+)\}", " ".join(g)).group(1)
        numbers.append(aux[lab])
        g = [re.sub(r"\\label\{[^}]+\}|\\nonumber", "", r).strip() for r in g]
        if len(g) == 1:
            body1 = g[0] if env == "equation" else g[0].replace("&", "")
        else:
            body1 = "\\begin{aligned}" + " \\\\\n".join(g) + "\\end{aligned}"
        disp.append("\\[\n" + body1 + "\n\\]")
    cont = "" if re.match(r"[ \t]*\n[ \t]*\n", after) else "@@NOIND@@"
    return "\n".join(disp) + "\n" + cont + after.lstrip(" \t\n") if cont else "\n".join(disp) + after


s = re.sub(r"\\begin\{(equation|align|gather)\}(.*?)\\end\{\1\}([ \t]*\n(?:[ \t]*\n)?)", equations, s, flags=re.S)
assert numbers == [str(i) for i in range(1, len(numbers) + 1)], numbers
s = re.sub(r"\\ref\{([^}]+)\}", lambda m: aux[m.group(1)], s)

for bad in (r"\tabin", r"\input{", r"\begin{algorithm", r"\ref{", r"\cmidrule", r"\begin{align}", r"\begin{gather}", r"\begin{equation}"):
    assert bad not in s, bad
open(out, "w", encoding="utf-8").write(s)
json.dump({"equations": len(numbers)}, open(out + ".json", "w"))
print("flattened", len(s), "equations", len(numbers))
