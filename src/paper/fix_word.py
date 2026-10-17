"""Give the pandoc Word copy of the draft the layout of the IEEEtran PDF (run by draft/build.sh after pandoc).

  - US Letter; one column with 1-in margins (default, for journal submission), or with columns=2 the IEEE
    journal page: title block in one column, body in two 21-pc columns, table*/figure* in one-column sections;
  - Times New Roman 10 pt body, 24 pt title, 9 pt bold abstract and index terms, small-caps section headings,
    italic subsection headings, 8 pt captions, tables and references;
  - display equations centred with their number at the right margin, as LaTeX numbers them;
  - "TABLE I" above table captions, "Fig. 1." in figure captions, booktabs-style rules on tables;
  - the draft running header with page numbers.
Layout markers (@@...@@) come from src/paper/make_word.py; every marker must be consumed.
Usage: python -I src/paper/fix_word.py in.docx out.docx n_equations [columns: 1 (default) or 2]
"""
import copy
import re
import sys

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

src, dst, n_eq = sys.argv[1], sys.argv[2], int(sys.argv[3])
COLUMNS = int(sys.argv[4]) if len(sys.argv) > 4 else 1
assert COLUMNS in (1, 2)
doc = docx.Document(src)
body = doc.element.body
FONT = "Times New Roman"
if COLUMNS == 2:
    MARGIN_LR, MARGIN_TB = 960, 1080
    TEXT_W, COL_GAP = 10320, 240                # 43 pc text width, 1 pc column gap (twips)
    COL_W = (TEXT_W - COL_GAP) // 2             # 21 pc column: equations and narrow figures
else:
    MARGIN_LR, MARGIN_TB = 1440, 1440           # 1-in margins
    TEXT_W, COL_GAP = 12240 - 2 * 1440, 0
    COL_W = 5040                                # narrow (one-column) figures keep their IEEE width
EMU_PER_TWIP = 635
MATH = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn("w:" + k), str(v))
    return e


# child order required by the WordprocessingML schema (Word rejects out-of-order properties)
ORDER = {
    "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs "
           "suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd "
           "snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment "
           "textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange",
    "rPr": "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid "
           "vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs "
           "em lang eastAsianLayout specVanish oMath",
    "tblPr": "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing "
             "tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription",
    "tcPr": "cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark",
}
ORDER = {k: v.split() for k, v in ORDER.items()}


def child(parent, tag, **attrs):
    """Replace parent's <tag> with a new one carrying attrs, inserted at its schema position."""
    old = parent.find(qn(tag))
    if old is not None:
        parent.remove(old)
    new = el(tag, **attrs)
    seq = ORDER.get(parent.tag.split("}")[1])
    if seq is None:
        parent.append(new); return new
    pos = seq.index(tag.split(":")[1])
    for i, c in enumerate(parent):
        name = c.tag.split("}")[1] if "}" in c.tag else c.tag
        if name in seq and seq.index(name) > pos:
            parent.insert(i, new); return new
    parent.append(new)
    return new


def get_rpr(r):
    rp = r.find(qn("w:rPr"))
    if rp is None:
        rp = el("w:rPr"); r.insert(0, rp)
    return rp


def get_tcpr(tc):
    tp = tc.find(qn("w:tcPr"))
    if tp is None:
        tp = el("w:tcPr"); tc.insert(0, tp)
    return tp


def ppr(p):
    return p.get_or_add_pPr()


def texts(p):
    return [t for t in p.iter(qn("w:t"))]


def ptext(p):
    return "".join(t.text or "" for t in texts(p))


def take_marker(p, pattern):
    """Remove a leading @@...@@ marker from paragraph p and return its regex match."""
    ts = texts(p)
    m = re.match(pattern, ts[0].text or "")
    assert m, (pattern, ptext(p)[:60])
    ts[0].text = ts[0].text[m.end():]
    return m


def run(text, bold=False, italic=False, size=None):
    r = el("w:r"); rp = el("w:rPr")
    if bold: rp.append(el("w:b"))
    if italic: rp.append(el("w:i"))
    if size: rp.append(el("w:sz", val=size)); rp.append(el("w:szCs", val=size))
    r.append(rp)
    for i, part in enumerate(text.split("\t")):
        if i: r.append(el("w:tab"))
        if part:
            t = el("w:t"); t.text = part; t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve"); r.append(t)
    return r


def insert_first_run(p, r):
    pp = p.find(qn("w:pPr"))
    (pp.addnext(r) if pp is not None else p.insert(0, r))


# ---------------------------------------------------------------- styles
def fonts(rpr):
    f = rpr.find(qn("w:rFonts"))
    if f is not None: rpr.remove(f)
    rpr.insert(0, el("w:rFonts", ascii=FONT, hAnsi=FONT, cs=FONT, eastAsia=FONT))


def style(name, size=20, bold=False, italic=False, caps=False, jc=None, before=0, after=0, first=None,
          left=None, hanging=None, keep=False, line=None):
    try:
        st = doc.styles[name]
    except KeyError:
        return
    rpr = st.element.get_or_add_rPr(); fonts(rpr)
    child(rpr, "w:b", val=int(bold)); child(rpr, "w:bCs", val=int(bold))
    child(rpr, "w:i", val=int(italic)); child(rpr, "w:iCs", val=int(italic))
    child(rpr, "w:smallCaps", val=int(caps))
    child(rpr, "w:color", val="000000")
    child(rpr, "w:u", val="none")
    if name == "Hyperlink":                     # links (DOIs) keep the size of the text around them
        for tag in ("w:sz", "w:szCs"):
            e = rpr.find(qn(tag))
            if e is not None: rpr.remove(e)
        return
    child(rpr, "w:sz", val=size); child(rpr, "w:szCs", val=size)
    pf = st.element.get_or_add_pPr()
    if keep: child(pf, "w:keepNext")
    sp = dict(before=before, after=after)
    if line: sp.update(line=line, lineRule="auto")
    child(pf, "w:spacing", **sp)
    ind = {}
    if first is not None: ind["firstLine"] = first
    if left is not None: ind["left"] = left
    if hanging is not None: ind["hanging"] = hanging
    child(pf, "w:ind", **(ind or {"firstLine": 0}))
    if jc: child(pf, "w:jc", val=jc)


dd = doc.styles.element.find(qn("w:docDefaults"))
drpr = dd.find(qn("w:rPrDefault")).find(qn("w:rPr")); fonts(drpr)
for tag in ("w:sz", "w:szCs"):
    child(drpr, tag, val=20)
dppr = dd.find(qn("w:pPrDefault"))
if dppr is not None and dppr.find(qn("w:pPr")) is not None:
    child(dppr.find(qn("w:pPr")), "w:spacing", before=0, after=0, line=240, lineRule="auto")

EM = 200                                        # 1 em at 10 pt (twips)
style("Normal", jc="both")
style("Body Text", jc="both", first=EM)
style("First Paragraph", jc="both", first=EM)
style("Compact", jc="both")
style("Title", size=48, jc="center", after=120, line=240)
style("Author", size=22, jc="center", after=240)
style("Abstract", size=18, bold=True, jc="both")
style("Heading 1", caps=True, jc="center", before=240, after=120, keep=True)
style("Heading 2", italic=True, jc="left", before=120, after=60, keep=True)
style("Heading 3", italic=True, jc="left", before=60, keep=True)
style("Table Caption", size=16, caps=True, jc="center", after=60, keep=True)
style("Image Caption", size=16, jc="both", before=60, after=200)
style("Captioned Figure", jc="center", before=120, keep=True)
style("Figure", jc="center", before=120, keep=True)
style("Bibliography", size=16, jc="both", left=360, hanging=360)
style("Footnote Text", size=16, jc="both")
style("Hyperlink")

# ---------------------------------------------------------------- front matter
paras = list(body.iter(qn("w:p")))
for p in paras:
    sty = p.find(qn("w:pPr") + "/" + qn("w:pStyle"))
    if sty is not None and sty.get(qn("w:val")) == "AbstractTitle":
        p.getparent().remove(p)
abstract = [p for p in body.iter(qn("w:p")) if (p.find(qn("w:pPr") + "/" + qn("w:pStyle")) is not None
            and p.find(qn("w:pPr") + "/" + qn("w:pStyle")).get(qn("w:val")) == "Abstract")]
assert len(abstract) == 1
insert_first_run(abstract[0], run("Abstract—", bold=True, italic=True))

for p in list(body.iter(qn("w:p"))):
    t = ptext(p)
    if t.startswith("@@KW@@"):
        take_marker(p, r"@@KW@@")
        child(ppr(p), "w:pStyle", val="Abstract")
        child(ppr(p), "w:spacing", before=120, after=120)
        insert_first_run(p, run("Index Terms—", bold=True, italic=True))
    elif t.startswith("@@RQ:"):
        m = take_marker(p, r"@@RQ:(RQ\d)@@")
        child(ppr(p), "w:ind", left=560, hanging=560)
        insert_first_run(p, run(m.group(1) + "\t"))
    elif t.startswith("@@NOIND@@"):
        take_marker(p, r"@@NOIND@@")
        child(ppr(p), "w:ind", firstLine=0)
    elif t.startswith("@@ALG@@"):
        take_marker(p, r"@@ALG@@")
        pp = ppr(p)
        child(pp, "w:keepNext")
        bd = child(pp, "w:pBdr")
        bd.append(el("w:top", val="single", sz=6, space=1, color="000000"))
        bd.append(el("w:bottom", val="single", sz=4, space=1, color="000000"))
        child(pp, "w:spacing", before=120, after=40)
        child(pp, "w:ind", firstLine=0)
        steps, q = [], p.getnext()
        while q is not None and q.tag == qn("w:p") and q.find(".//" + qn("w:numPr")) is not None:
            steps.append(q); q = q.getnext()
        assert len(steps) >= 5, "algorithm steps not found"
        for i, s_ in enumerate(steps):
            sp = ppr(s_)
            if i < len(steps) - 1:
                child(sp, "w:keepNext")
            for r in s_.iter(qn("w:r")):
                rp = get_rpr(r)
                child(rp, "w:sz", val=18); child(rp, "w:szCs", val=18)
        bd = child(ppr(steps[-1]), "w:pBdr")
        bd.append(el("w:bottom", val="single", sz=6, space=4, color="000000"))
        child(ppr(steps[-1]), "w:spacing", after=200)

# ---------------------------------------------------------------- tables (data tables, before equations become tables)
wide_blocks = []                                # (first element, last element) of each full-width float
for tbl in list(body.iter(qn("w:tbl"))):
    cap = tbl.getprevious()
    m = re.match(r"@@TAB:([IVXL]+):([WN]):([SM])@@", ptext(cap) if cap is not None else "")
    assert m, "table without a numbered caption"
    take_marker(cap, r"@@TAB:[IVXL]+:[WN]:[SM]@@")
    num, wide, small = m.group(1), m.group(2) == "W", m.group(3) == "S"
    label = copy.deepcopy(cap)
    for r in list(label):
        if r.tag != qn("w:pPr"): label.remove(r)
    label.append(run(f"TABLE {num}"))
    child(ppr(label), "w:spacing", before=200, after=0)
    cap.addprevious(label)
    size = 14 if small else 16
    tp = tbl.find(qn("w:tblPr"))
    child(tp, "w:jc", val="center")
    b = child(tp, "w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b.append(el("w:" + side, val="single", sz=8, space=0, color="000000") if side in ("top", "bottom") else el("w:" + side, val="nil"))
    mar = child(tp, "w:tblCellMar")
    mar.append(el("w:left", w=57, type="dxa")); mar.append(el("w:right", w=57, type="dxa"))
    if tp.find(qn("w:tblLayout")) is None or tp.find(qn("w:tblLayout")).get(qn("w:type")) != "fixed":
        child(tp, "w:tblW", w=0, type="auto")
    rows = tbl.findall(qn("w:tr"))
    head = [r for r in rows if r.find(qn("w:trPr") + "/" + qn("w:tblHeader")) is not None] or rows[:1]
    for i, r in enumerate(head):
        for tc in r.findall(qn("w:tc")):
            span = tc.find(qn("w:tcPr") + "/" + qn("w:gridSpan"))
            last = i == len(head) - 1
            if last or (span is not None and int(span.get(qn("w:val"))) > 1 and ptext(tc).strip()):
                tcp = get_tcpr(tc)
                bd = child(tcp, "w:tcBorders")
                bd.append(el("w:bottom", val="single", sz=4, space=0, color="000000"))
    for r in rows:                              # keep each table in one piece, as LaTeX floats are
        trp = r.find(qn("w:trPr"))
        if trp is None:
            trp = el("w:trPr"); r.insert(0, trp)
        if trp.find(qn("w:cantSplit")) is None:
            trp.insert(0, el("w:cantSplit"))
        if r is not rows[-1]:
            for p in r.iter(qn("w:p")):
                child(ppr(p), "w:keepNext")
    for p in tbl.iter(qn("w:p")):
        pp = ppr(p)
        child(pp, "w:spacing", before=10, after=10)
        child(pp, "w:ind", firstLine=0)
        mark = child(pp, "w:rPr")                   # paragraph mark: empty cells must not set a taller row
        mark.append(el("w:sz", val=size)); mark.append(el("w:szCs", val=size))
        for r in p.iter(qn("w:r")):
            rp = get_rpr(r)
            child(rp, "w:sz", val=size); child(rp, "w:szCs", val=size)
        for r in p.iter(MATH + "r"):                # inline math in cells (e.g. 1.48x) at the table size
            rp = el("w:rPr"); rp.append(el("w:sz", val=size)); rp.append(el("w:szCs", val=size))
            mrp = r.find(MATH + "rPr")
            (mrp.addnext(rp) if mrp is not None else r.insert(0, rp))
    if wide:
        wide_blocks.append((label, tbl))

# ---------------------------------------------------------------- figures
for p in list(body.iter(qn("w:p"))):
    m = re.match(r"@@FIG:(\d+):([WN])@@", ptext(p))
    if not m:
        continue
    take_marker(p, r"@@FIG:\d+:[WN]@@")
    insert_first_run(p, run(f"Fig. {m.group(1)}. "))
    fig = p.getprevious()
    assert fig is not None and fig.find(".//" + qn("w:drawing")) is not None, "caption without a figure"
    width = (TEXT_W if m.group(2) == "W" else COL_W) * EMU_PER_TWIP
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
    ext = fig.find(".//" + WP + "extent")
    cx, cy = int(ext.get("cx")), int(ext.get("cy"))
    h = round(cy * width / cx)
    ext.set("cx", str(width)); ext.set("cy", str(h))
    for e in fig.iter(A + "ext"):
        if e.get("cx"):
            e.set("cx", str(width)); e.set("cy", str(h))
    if m.group(2) == "W":
        wide_blocks.append((fig, p))

# ---------------------------------------------------------------- display equations: centred, number at the right
eqs = [p for p in body.iter(qn("w:p")) if p.find(MATH + "oMathPara") is not None]
assert len(eqs) == n_eq, (len(eqs), n_eq)
NUM_W, PAD_W = 360, 0                           # number cell; no left pad, so the widest equation (4) stays on one line
EQ_W = COL_W if COLUMNS == 2 else TEXT_W
if COLUMNS == 1:
    NUM_W, PAD_W = 600, 600                     # room to spare: centre the equation on the page
widths = (PAD_W, EQ_W - PAD_W - NUM_W, NUM_W)
for k, p in enumerate(eqs, 1):
    tbl = el("w:tbl")
    tp = el("w:tblPr")
    tp.append(el("w:tblW", w=EQ_W, type="dxa")); tp.append(el("w:jc", val="center"))
    nob = el("w:tblBorders")
    for side_ in ("top", "left", "bottom", "right", "insideH", "insideV"):
        nob.append(el("w:" + side_, val="nil"))
    tp.append(nob)
    tp.append(el("w:tblLayout", type="fixed"))
    mar = el("w:tblCellMar"); mar.append(el("w:left", w=0, type="dxa")); mar.append(el("w:right", w=0, type="dxa")); tp.append(mar)
    tp.append(el("w:tblLook", val="0000", firstRow=0, lastRow=0, firstColumn=0, lastColumn=0, noHBand=1, noVBand=1))
    tbl.append(tp)
    grid = el("w:tblGrid")
    for w in widths:
        grid.append(el("w:gridCol", w=w))
    tbl.append(grid)
    tr = el("w:tr"); tr.append(el("w:trPr")); tr[0].append(el("w:cantSplit"))
    tbl.append(tr)
    for i, w in enumerate(widths):
        tc = el("w:tc"); tcp = el("w:tcPr"); tcp.append(el("w:tcW", w=w, type="dxa"))
        cb = el("w:tcBorders")                  # override any rule the default table style draws
        for side_ in ("top", "left", "bottom", "right"):
            cb.append(el("w:" + side_, val="nil"))
        tcp.append(cb); tcp.append(el("w:vAlign", val="center")); tc.append(tcp)
        q = el("w:p"); qp = el("w:pPr")
        qp.append(el("w:pStyle", val="Normal")); qp.append(el("w:spacing", before=60, after=60))
        qp.append(el("w:jc", val=("center", "center", "right")[i])); q.append(qp)
        if i == 1:
            q.append(p.find(MATH + "oMathPara"))
        elif i == 2:
            q.append(run(f"({k})"))
        tc.append(q); tr.append(tc)
    p.addprevious(tbl)
    p.getparent().remove(p)

# ---------------------------------------------------------------- page, columns, sections
def sect(cols, continuous=True):
    s = el("w:sectPr")
    if continuous: s.append(el("w:type", val="continuous"))
    s.append(el("w:pgSz", w=12240, h=15840))
    s.append(el("w:pgMar", top=MARGIN_TB, right=MARGIN_LR, bottom=MARGIN_TB, left=MARGIN_LR, header=720, footer=720, gutter=0))
    s.append(el("w:cols", num=cols, space=COL_GAP if cols > 1 else 0))
    return s


def section_break(after_el, cols, continuous=True):
    """Insert after `after_el` an empty paragraph that ends the current section with `cols` columns."""
    p = el("w:p"); pp = el("w:pPr")
    pp.append(el("w:spacing", before=0, after=0, line=20, lineRule="exact"))
    rp = el("w:rPr"); rp.append(el("w:sz", val=2)); pp.append(rp)
    pp.append(sect(cols, continuous)); p.append(pp)
    after_el.addnext(p)
    return p


author = [p for p in body.iter(qn("w:p")) if (p.find(qn("w:pPr") + "/" + qn("w:pStyle")) is not None
          and p.find(qn("w:pPr") + "/" + qn("w:pStyle")).get(qn("w:val")) == "Author")]
assert len(author) == 1
# the affiliation note (\thanks): unmarked, at the foot of the first column as in IEEE journals. Anchored in the
# two-column abstract; a footnote in the one-column title section makes Word push the body to page 2.
refs = list(author[0].iter(qn("w:footnoteReference")))
assert len(refs) == 1, "expected one \\thanks footnote on the author line"
fid = refs[0].get(qn("w:id"))
refs[0].set(qn("w:customMarkFollows"), "1")
fn_run = refs[0].getparent()
fn_run.getparent().remove(fn_run)
insert_first_run(abstract[0], fn_run)
from lxml import etree
fpart = next(r.target_part for r in doc.part.rels.values() if r.reltype.endswith("/footnotes"))
froot = fpart.element if hasattr(fpart, "element") else etree.fromstring(fpart.blob)
for fn in froot.findall(qn("w:footnote")):
    if fn.get(qn("w:id")) == fid:
        for mark in list(fn.iter(qn("w:footnoteRef"))):
            r = mark.getparent(); r.getparent().remove(r)
        for t in fn.iter(qn("w:t")):            # pandoc puts a space after the mark
            t.text = (t.text or "").lstrip(); break
if not hasattr(fpart, "element"):
    fpart._blob = etree.tostring(froot, xml_declaration=True, encoding="UTF-8", standalone=True)
final = body.find(qn("w:sectPr"))
body.remove(final)
if COLUMNS == 2:
    section_break(author[0], 1, continuous=False)
    for first, last in wide_blocks:
        prev = first.getprevious()
        section_break(prev, 2)
        section_break(last, 1)
    section_break(body[-1], 2)                  # a closing continuous break balances the last page's columns
body.append(sect(COLUMNS, continuous=False))

# running header as in the PDF
hdr = doc.sections[0].header
hdr.is_linked_to_previous = False
hp = hdr.paragraphs[0]
hp._p.append(run("DRAFT V0.1 — NOT FOR DISTRIBUTION\t", size=16))
fld = el("w:fldSimple", instr="PAGE"); fld.append(run("1", size=16)); hp._p.append(fld)
pp = hp._p.get_or_add_pPr()
child(pp, "w:tabs").append(el("w:tab", val="right", pos=TEXT_W))
child(pp, "w:ind", firstLine=0)

left = [ptext(p)[:50] for p in body.iter(qn("w:p")) if "@@" in ptext(p)]
assert not left, f"unconsumed layout markers: {left}"
doc.save(dst)
print(f"Word layout: {COLUMNS} column(s), {n_eq} equations numbered, {len(wide_blocks)} full-width floats, saved {dst}")
