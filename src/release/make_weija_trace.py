"""Derived Weija delivery trace for the code release (review M15): timestamps only, no water-quality values.
For every stream and probe: the time of each record, whether the received file flagged it as imputed, and whether it
counts as a genuine delivery in this paper (src/revision/gap_cause.py rules). This is all the delivery analysis uses.
Usage (from Paper2/): python -I src/release/make_weija_trace.py release/weija_delivery_trace.csv
"""
import glob
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src/data")
from clean_weija import MAX_DECIMALS, ramp_mask  # noqa: E402

DECIMAL_PARAMS = {"conductivity", "ph", "temperature"}


def main(out):
    parts = []
    for f in sorted(glob.glob("data/weija_raw/*_cleaned_records.csv")):
        d = pd.read_csv(f, parse_dates=["Datetime"], dtype={"Value": str})
        p = d.Parameter.iloc[0]
        d["imputed_flag"] = d.Was_Imputed.astype(str) == "True"
        dec = d.Value.str.split(".").str[1].fillna("").str.len()
        d["genuine"] = ~d.imputed_flag & ((dec <= MAX_DECIMALS) | (p not in DECIMAL_PARAMS))
        for probe, g in d.groupby("Probe Name"):
            g = g.sort_values("Datetime").drop_duplicates("Datetime").copy()
            cand = g[g.genuine]
            if len(cand) > 2:
                ramp = ramp_mask(cand.Datetime, cand.Value.astype(float))
                g.loc[cand.index[ramp], "genuine"] = False
            parts.append(pd.DataFrame({"stream": p, "probe": probe, "time": g.Datetime,
                                       "imputed_flag": g.imputed_flag, "genuine_delivery": g.genuine}))
    t = pd.concat(parts).sort_values(["stream", "probe", "time"])
    t.to_csv(out, index=False)
    print(t.groupby("stream")[["genuine_delivery"]].agg(["size", "sum"]))


if __name__ == "__main__":
    main(sys.argv[1])
