import sys, json, urllib.request, urllib.parse
for q in sys.argv[1:]:
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"filter": "title.search:" + q, "per-page": 6, "mailto": "research@example.org"})
    r = json.load(urllib.request.urlopen(url, timeout=60))
    print(f"\n### TITLE: {q}  (hits={r['meta']['count']})")
    for w in r["results"]:
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        oa = (w.get("best_oa_location") or {}).get("pdf_url")
        print(f"- [{w['publication_year']}] {w['display_name'][:130]} | {src} | cites={w['cited_by_count']} | doi={w.get('doi')} | pdf={oa}")
