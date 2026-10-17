"""Phase 1 — clean USGS instantaneous-value downloads into the same schema as InWaterSense.

Rules (conservative, documented so reviewers can reproduce):
  * keep only values whose qualifier is exactly "A" (approved); drop provisional "P",
    estimated "e", equipment malfunction "Eqp", ice, etc.
  * if a parameter has several sensors/methods at one site, keep the method with most data
  * columns renamed to the InWaterSense schema: T (degC), EC (specific conductance,
    uS/cm @25C), pH, DO (% saturation), DO_mgL
  * DO (% saturation): for most sites USGS has *approved* only DO in mg/L for 2023 (the
    %sat series are provisional fragments). For consistency across all sites DO %sat is
    therefore DERIVED from approved DO mg/L and water temperature with the Benson & Krause
    (1984) freshwater solubility equation at 1 atm (the same physics behind USGS DOTABLES
    and our InWaterSense conversion). No barometric correction -> a constant elevation-
    dependent scale error of a few %, irrelevant for predictability analyses.
  * new segment after a gap > 60 min (never interpolate across gaps)
Usage: python src/data/clean_usgs.py            (cleans every downloaded site-year into data/clean/usgs)
       python src/data/clean_usgs.py 2024 data/clean/usgs_2024   (one year, own output directory; added
       2026-10-17 for the held-out confirmatory data, so that 2024 files never overwrite the 2023 ones)
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

RENAME = {"temp_c": "T", "spcond_uScm": "EC", "ph": "pH", "do_pctsat": "DO", "do_mgL": "DO_mgL"}
SEGMENT_GAP_MIN = 60


def do_sat_mgL(T):
    """Benson & Krause (1984) DO solubility in fresh water at 1 atm, mg/L."""
    Tk = T + 273.15
    return np.exp(-139.34411 + 1.575701e5 / Tk - 6.642308e7 / Tk ** 2
                  + 1.243800e10 / Tk ** 3 - 8.621949e11 / Tk ** 4)


def clean_file(f):
    d = pd.read_csv(f, dtype={"qualifiers": str, "method": str})
    n0 = len(d)
    d = d[d.qualifiers == "A"].copy()
    d["method"] = d["method"].fillna("")
    best = d.groupby(["param", "method"]).size().reset_index(name="n") \
            .sort_values("n").groupby("param").tail(1)[["param", "method"]]
    d = d.merge(best, on=["param", "method"])
    d["t"] = pd.to_datetime(d["time"], utc=True)
    w = d.pivot_table(index="t", columns="param", values="value", aggfunc="mean").rename(columns=RENAME)
    w = w.reset_index().sort_values("t")
    if "DO" in w:                     # keep USGS' own %sat only as a reference column
        w = w.rename(columns={"DO": "DO_pct_usgs"})
    if {"DO_mgL", "T"} <= set(w.columns):
        w["DO"] = 100 * w["DO_mgL"] / do_sat_mgL(w["T"])
    gap = w.t.diff().dt.total_seconds() / 60
    w["segment"] = (gap.isna() | (gap > SEGMENT_GAP_MIN)).cumsum()
    info = {"file": Path(f).name, "raw_values": n0, "approved_values": int(len(d)),
            "timestamps": int(len(w)), "median_step_min": float(gap.median()),
            "segments": int(w.segment.nunique()),
            "complete_T_EC_DO_pH": int(w[["T", "EC", "DO", "pH"]].notna().all(axis=1).sum())
            if set(["T", "EC", "DO", "pH"]) <= set(w.columns) else 0}
    return w, info


def main(year="????", out="data/clean/usgs"):
    Path(out).mkdir(parents=True, exist_ok=True)
    infos = []
    for f in sorted(glob.glob(f"data/raw/usgs/*_{year}-01-01_{year}-12-31.csv")):
        if pd.read_csv(f, nrows=1).empty:
            print({"file": Path(f).name, "excluded": "no data for this year"}); continue
        w, info = clean_file(f)
        site = Path(f).name.split("_")[0]
        w.to_csv(f"{out}/{site}.csv", index=False)
        infos.append(info); print(info)
    qdir = "results/phase1" if year == "????" else f"results/phase1/{year}"
    Path(qdir).mkdir(parents=True, exist_ok=True)
    Path(f"{qdir}/usgs_quality.json").write_text(json.dumps(infos, indent=2))


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:3])
