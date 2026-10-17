"""Site eligibility for the design evaluation (DESIGN_EVAL_PLAN.md §1, with deviation D2), as a script.

The 2023 file results/scoping/design_site_eligibility.csv was computed inline; this script states the rule
and must reproduce that file exactly on the 2023 data (tests/test_confirm.py).
Rule: all four parameters (T, EC, pH, DO) present; native step = median time step; a site is 'ok' if its
complete cycles (all four present) cover >= 50% of the slots of its own record span AND >= 50% of the slots
of the calendar year at the native step.
Usage (from Paper2/): python -I src/confirm/eligibility.py <clean dir> <year> <out csv>
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PARAMS = ["T", "EC", "pH", "DO"]


def site_row(f, year):
    site = Path(f).stem
    d = pd.read_csv(f, parse_dates=["t"])
    miss = [p for p in PARAMS if p not in d.columns or d[p].notna().sum() == 0]
    if miss:
        return {"site": site, "status": f"missing {miss[0]}", "step_min": np.nan,
                "complete_frac": np.nan, "complete_frac_of_year": np.nan}
    d = d.sort_values("t").drop_duplicates("t")
    step = float(d.t.diff().dt.total_seconds().median())
    complete = int(d[PARAMS].notna().all(axis=1).sum())
    span_slots = (d.t.iloc[-1] - d.t.iloc[0]).total_seconds() / step + 1
    frac = complete / span_slots
    days = 366 if pd.Timestamp(year=year, month=12, day=31).dayofyear == 366 else 365
    year_slots = days * 86400 / step
    row = {"site": site, "step_min": step / 60, "complete_frac": round(frac, 3), "complete_frac_of_year": np.nan}
    if frac < 0.5:
        row["status"] = "complete<50%"
        return row
    row["complete_frac_of_year"] = complete / year_slots
    row["status"] = "ok" if complete / year_slots >= 0.5 else "complete<50% of year"
    return row


def main(clean_dir, year, out):
    rows = [site_row(f, int(year)) for f in sorted(glob.glob(f"{clean_dir}/*.csv"))]
    df = pd.DataFrame(rows)[["site", "status", "step_min", "complete_frac", "complete_frac_of_year"]]
    df.to_csv(out, index=False)
    print(df.status.value_counts().to_string())


if __name__ == "__main__":
    main(*sys.argv[1:4])
