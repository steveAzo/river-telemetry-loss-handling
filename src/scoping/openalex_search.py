import sys, json, urllib.request, urllib.parse, time
out = []
for q in sys.argv[2:]:
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": q, "per-page": 12, "sort": "relevance_score:desc", "mailto": "research@example.org"})
    try:
        r = json.load(urllib.request.urlopen(url, timeout=60))
    except Exception as e:
        print("ERR", q, e); continue
    print(f"\n### {q}")
    for w in r["results"]:
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        oa = (w.get("best_oa_location") or {}).get("pdf_url")
        print(f"- [{w['publication_year']}] {w['display_name'][:120]} | {src} | cites={w['cited_by_count']} | doi={w.get('doi')} | pdf={oa}")
        out.append({"q": q, "id": w["id"], "title": w["display_name"], "year": w["publication_year"], "venue": src, "cites": w["cited_by_count"], "doi": w.get("doi"), "pdf": oa})
    time.sleep(0.3)
json.dump(out, open(sys.argv[1], "a"), indent=0)
