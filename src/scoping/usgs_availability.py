"""Per-site, per-year availability of approved T/EC/DO/pH at USGS same-river chain sites, from DAILY
values (daily mean, statistic 00003; one small request per site). A site-year counts as usable when
every parameter has >= 250 approved ("A") daily means. Daily coverage is a proxy for 15-min coverage.
Usage: python -I src/scoping/usgs_availability.py results/scoping/chain_sites.csv 2021 2024 out.csv
"""
import json, sys, time, urllib.request
import pandas as pd

PARAMS = {"00010": "T", "00095": "EC", "00300": "DO", "00400": "pH"}
URL = ("https://waterservices.usgs.gov/nwis/dv/?format=json&sites={s}&parameterCd={p}"
       "&statCd=00003,00008&startDT={a}-01-01&endDT={b}-12-31&siteStatus=all")


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print("   retry", k + 1, e, flush=True); time.sleep(5 * (k + 1))
    return None


def main(sites_csv, y0, y1, out):
    sites = pd.read_csv(sites_csv, dtype=str)
    rows = []
    for _, s in sites.iterrows():
        d = get(URL.format(s=s.site_no, p=",".join(PARAMS), a=y0, b=y1))
        cnt = {}  # (param, year) -> approved days (best method/statistic)
        for ts in (d or {"value": {"timeSeries": []}})["value"]["timeSeries"]:
            name = PARAMS.get(ts["variable"]["variableCode"][0]["value"])
            for b in ts["values"]:
                per = {}
                for v in b["value"]:
                    if "A" in v["qualifiers"]:
                        y = int(v["dateTime"][:4]); per[y] = per.get(y, 0) + 1
                for y, n in per.items():
                    cnt[(name, y)] = max(cnt.get((name, y), 0), n)
        for y in range(int(y0), int(y1) + 1):
            r = {"site_no": s.site_no, "station_nm": s.station_nm, "river": s.river, "year": y,
                 "lat": s.dec_lat_va, "lon": s.dec_long_va}
            r.update({f"days_{p}": cnt.get((p, y), 0) for p in PARAMS.values()})
            r["min_days"] = min(r[f"days_{p}"] for p in PARAMS.values())
            rows.append(r)
        print(s.site_no, s.station_nm[:45], [rows[-k]["min_days"] for k in range(int(y1) - int(y0) + 1, 0, -1)], flush=True)
    pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main(*sys.argv[1:5])
