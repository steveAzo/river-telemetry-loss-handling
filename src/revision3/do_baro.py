"""Revision 3, audit issue 18: barometric correction of DO percent saturation (post hoc sensitivity data).

The frozen cleaning (src/data/clean_usgs.py) derives DO %sat from approved DO mg/L and water temperature with the
Benson and Krause (1984) solubility at 1 atm. At elevation h the saturation concentration is lower by the ratio of
mean barometric pressure to 1 atm; to first order (water-vapour term neglected)
    p/p0 = (1 - 2.25577e-5 h)^5.25588                 (standard atmosphere, h in m)
    DO_corrected [%sat] = DO_frozen [%sat] / (p/p0).
Site altitudes: USGS site service, alt_va in feet (data/raw/usgs_sites/site_metadata.rdb); the five sites without
one take the USGS National Map elevation at their coordinates (data/raw/usgs_sites/epqs_missing_alt_m.tsv; negative
values set to 0).
Writes data/clean/usgs_baro and data/clean/usgs_2024_baro (same files and columns as the frozen folders, DO
replaced, plus a column p_ratio). The frozen folders are not touched.
Usage (from Paper2/): python -I src/revision3/do_baro.py
"""
import glob
import os

import numpy as np
import pandas as pd

META = "data/raw/usgs_sites/site_metadata.rdb"
EPQS = "data/raw/usgs_sites/epqs_missing_alt_m.tsv"
PAIRS = (("data/clean/usgs", "data/clean/usgs_baro"), ("data/clean/usgs_2024", "data/clean/usgs_2024_baro"))


def altitudes_m():
    rows = [l.rstrip("\n").split("\t") for l in open(META, encoding="utf-8") if not l.startswith("#")]
    head = rows[0]
    i_site, i_alt = head.index("site_no"), head.index("alt_va")
    alt = {}
    for r in rows[2:]:
        if len(r) > i_alt and r[i_alt].strip():
            alt[r[i_site]] = float(r[i_alt]) * 0.3048
    for l in open(EPQS, encoding="utf-8"):
        s, v = l.split()
        alt.setdefault(s, max(0.0, float(v)))
    return alt


def pressure_ratio(h_m):
    return (1.0 - 2.25577e-5 * h_m) ** 5.25588


def main():
    alt = altitudes_m()
    for src, dst in PAIRS:
        os.makedirs(dst, exist_ok=True)
        for f in sorted(glob.glob(f"{src}/*.csv")):
            site = os.path.basename(f)[:-4]
            if site not in alt:
                raise SystemExit(f"no altitude for {site}")
            d = pd.read_csv(f)
            pr = pressure_ratio(alt[site])
            if "DO" in d.columns:
                d["DO"] = d["DO"] / pr
            d["p_ratio"] = pr
            d.to_csv(f"{dst}/{site}.csv", index=False)
            print(f"{site}: altitude {alt[site]:7.1f} m, p/p0 {pr:.4f}", flush=True)


if __name__ == "__main__":
    main()
