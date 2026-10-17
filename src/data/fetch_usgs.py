"""Download USGS continuous water-quality data (instantaneous values) for Paper 2 (copied unchanged from the sealed Paper 1 repo, 2026-10-11).

Parameters (USGS codes): 00010 water temperature (degC), 00095 specific conductance
(uS/cm @25C), 00300 dissolved oxygen (mg/L), 00301 dissolved oxygen (% saturation),
00400 pH. Each value carries USGS qualifiers: "A" = approved, "P" = provisional.
We keep the qualifiers so only approved data can be used in the evaluation.

Usage:  python src/data/fetch_usgs.py 01463500 2023-01-01 2023-12-31
Output: data/raw/usgs/<site>_<start>_<end>.csv  (long format: time, param, value, qualifiers)
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

PARAMS = "00010,00095,00300,00301,00400"
NAMES = {"00010": "temp_c", "00095": "spcond_uScm", "00300": "do_mgL",
         "00301": "do_pctsat", "00400": "ph"}
URL = ("https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}"
       "&parameterCd={params}&startDT={start}&endDT={end}&siteStatus=all")


def fetch_month(site, start, end, retries=3):
    url = URL.format(site=site, params=PARAMS, start=start, end=end)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except Exception as e:  # network hiccups are common; back off and retry
            print(f"  retry {attempt + 1} for {start}: {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"failed {site} {start}-{end}")


def main(site, start, end):
    out = Path("data/raw/usgs")
    out.mkdir(parents=True, exist_ok=True)
    rows, meta = [], {}
    # month-sized requests keep responses small and avoid server timeouts
    for m0 in pd.date_range(start, end, freq="MS"):
        m1 = min(m0 + pd.offsets.MonthEnd(0), pd.Timestamp(end))
        d = fetch_month(site, m0.date(), m1.date())
        for ts in d["value"]["timeSeries"]:
            code = ts["variable"]["variableCode"][0]["value"]
            meta.setdefault("site_name", ts["sourceInfo"]["siteName"])
            for block in ts["values"]:
                method = block["method"][0].get("methodDescription", "")
                for v in block["value"]:
                    rows.append((v["dateTime"], NAMES.get(code, code), float(v["value"]),
                                 ",".join(v["qualifiers"]), method))
        print(f"{site} {m0:%Y-%m}: {len(rows)} values so far")
    df = pd.DataFrame(rows, columns=["time", "param", "value", "qualifiers", "method"])
    f = out / f"{site}_{start}_{end}.csv"
    df.to_csv(f, index=False)
    print(f"saved {f} ({len(df)} rows) — {meta.get('site_name')}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
