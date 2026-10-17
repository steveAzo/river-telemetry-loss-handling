"""Append to fetched.bib the registry BibTeX (doi.org content negotiation) of every key in dois.tsv not yet in it.
One entry per line, citation key replaced by ours (the format build_bib.py parses). Added 2026-10-17 for the
references of the revision. Usage (from Paper2/draft/bib): python -I fetch_bib.py
"""
import re
import urllib.request

have = set(re.findall(r"@\w+\{([^,]+),", open("fetched.bib", encoding="utf-8").read()))
rows = [l.rstrip("\n").split("\t") for l in open("dois.tsv", encoding="utf-8") if l.strip()]
with open("fetched.bib", "a", encoding="utf-8") as out:
    for key, doi in rows:
        if key in have:
            continue
        req = urllib.request.Request(f"https://doi.org/{doi}", headers={"Accept": "application/x-bibtex"})
        bib = urllib.request.urlopen(req, timeout=60).read().decode("utf-8").strip()
        bib = re.sub(r"^(@\w+\{)[^,]+,", lambda m: m.group(1) + key + ",", bib.replace("\n", " "))
        out.write("\n " + bib + "\n")
        print("fetched", key, doi)
