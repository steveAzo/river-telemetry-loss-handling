"""Hourly shortwave radiation and precipitation (Open-Meteo historical archive, ERA5-based reanalysis) at the
USGS development sites, for the rescoping value-of-information screen (src/rescoping/voi_sensing.py).

Source: https://archive-api.open-meteo.com/v1/archive (free, no key; data CC BY 4.0). One request per site.
Output: data/raw/openmeteo/<site>_<year>.csv with columns t (UTC), sw_rad (W/m2), precip (mm).
Usage (from Paper2/): python -I src/data/fetch_openmeteo.py 2023
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

OUT = "data/raw/openmeteo"
META = ["results/scoping/usgs_scout_sites.csv", "results/scoping/chain_sites.csv"]


def main(year):
    os.makedirs(OUT, exist_ok=True)
    meta = pd.concat([pd.read_csv(f, dtype={"site_no": str}) for f in META]).drop_duplicates("site_no")
    meta = meta.set_index("site_no")
    sites = sorted(f[:-4] for f in os.listdir("data/clean/usgs") if f.endswith(".csv"))
    for s in sites:
        path = f"{OUT}/{s}_{year}.csv"
        if os.path.exists(path):
            continue
        lat, lon = meta.loc[s, "dec_lat_va"], meta.loc[s, "dec_long_va"]
        q = urllib.parse.urlencode({"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}",
                                    "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
                                    "hourly": "shortwave_radiation,precipitation", "timezone": "UTC"})
        req = urllib.request.Request("https://archive-api.open-meteo.com/v1/archive?" + q,
                                     headers={"User-Agent": "Mozilla/5.0 (research script)"})
        for attempt in range(4):                         # the service answers empty bodies when busy
            try:
                d = json.load(urllib.request.urlopen(req, timeout=120))
                break
            except (json.JSONDecodeError, OSError):
                if attempt == 3:
                    raise
                time.sleep(10 * (attempt + 1))
        h = d["hourly"]
        pd.DataFrame({"t": pd.to_datetime(h["time"], utc=True), "sw_rad": h["shortwave_radiation"],
                      "precip": h["precipitation"]}).to_csv(path, index=False)
        print(s, len(h["time"]), flush=True)
        time.sleep(1.0)                                  # be polite to the free service


if __name__ == "__main__":
    main(int(sys.argv[1]))
