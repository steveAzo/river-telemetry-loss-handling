"""Phase 1 (late addition) -- clean the Weija deployment (Prof Adu-Manu, 2018-19) into cycles.

Source: cleaned/cleaned/<param>_cleaned_records.csv as received 2026-10-04. These files were
already "cleaned" by someone else; the profile below (checked 2026-10-04) shows that their
cleaning left artefacts that would bias a predictability study, so we re-clean conservatively.

Profile of the received files (all numbers reproducible with this script):
  * one sonde cycle every ~32.5 min: EC, pH and temperature Sensor Two are within ~1 min of
    each other; temperature Sensor One runs ~15 min offset on the same 32.5-min cadence;
    Sensor Five, DO and ORP every ~5 h (too coarse for 30-min suppression); Sensor Four has
    17 rows on day 1 only.
  * Was_Imputed rows: temperature Sensor Two is 87 % imputed in Jan 2019 and 100 % in Feb-Mar
    2019, so real co-sampled T/EC/pH exist only from 30 Oct 2018 to early Jan 2019.
  * UNFLAGGED computed values: genuine T/EC/pH readings have <= 3 decimals, imputed rows
    12-15; yet 513 EC, 874 pH and 22 T rows with Was_Imputed = False have 4-16 decimals.
    They are linear interpolation, e.g. EC 11-12 Nov 2018 falls by exactly 0.133219 per ROW
    across irregular timestamps (found 2026-10-04 from a figure, after the first run, which
    used only the time-slope ramp rule and missed it).
  * calcium (from ~25 Nov) and fluoride (from ~20 Dec) are statistically white noise: lag-1
    autocorrelation ~0 and a flat histogram between fixed bounds (Ca 2.03-30.76 mg/L, F
    0.114-0.472 mg/L), whereas the same probes have autocorrelation 0.87-0.95 in November.
    Either a floating electrode or a processing artefact; unusable either way.
  * pH: < 3 from ~10 Jan 2019 onward (probe failure; 59-85 % of Jan-Mar readings), and
    9-12.5 for much of Nov-Dec. Values > 9 are not plausible for this reservoir without
    independent confirmation, so pH is kept but flagged and NOT simulated by default
    (same treatment as InWaterSense pH).

Quality tiers (same philosophy as clean_inws.py: every decision is a flag):
  IMPUTED  Was_Imputed == True                          -> dropped before cycling
  COMPUTED more than MAX_DECIMALS decimals (T, EC, pH)  -> dropped before cycling
  RAMP     member of an unflagged run with a constant step per row OR per minute -> dropped
  RANGE    T [15, 45] degC, EC [20, 2000] uS/cm, pH [3, 14]   -> value set to NaN
  SPIKE    Hampel (window 7 cycles ~3.5 h, 4 scaled MAD) -> value KEPT, flagged
Cycles are anchored on EC rows; pH and T (Sensor Two) are attached if within CYCLE_TOL.
T1 (Sensor One, offset probe) is attached as a separate column for sensitivity checks.
Segments: a new segment starts after a gap > 60 min (never interpolate across it).

Outputs: data/clean/weija_cycles.csv, results/phase1/weija_quality.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path("cleaned/cleaned")
OUT = Path("data/clean"); REP = Path("results/phase1")
RANGE = {"T": (15.0, 45.0), "T1": (15.0, 45.0), "EC": (20.0, 2000.0), "pH": (3.0, 14.0)}
CYCLE_TOL = pd.Timedelta("3min")
T1_TOL = pd.Timedelta("20min")
SEGMENT_GAP_MIN = 60
HAMPEL_W, HAMPEL_K = 7, 4.0
RAMP_MIN = 6                       # >= 6 points on one straight line = interpolation, not a sensor
MAX_DECIMALS = 3                   # the loggers record T, EC and pH with at most 3 decimals


def load(param, probe=None):
    d = pd.read_csv(SRC / f"{param}_cleaned_records.csv", parse_dates=["Datetime"], dtype={"Value": str})
    d["decimals"] = d.Value.str.split(".").str[1].fillna("").str.len()
    d["Value"] = d.Value.astype(float)
    if probe:
        d = d[d["Probe Name"] == probe]
    return d.sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)


def ramp_mask(t, v):
    """True for points inside runs of >= RAMP_MIN consecutive points with an identical non-zero
    slope, per minute (time-based interpolation) or per row (index-based interpolation)."""
    v = np.asarray(v, float)
    tm = pd.Series(t).astype("int64").to_numpy() / 6e10
    return _runs(np.diff(v) / np.maximum(np.diff(tm), 1e-9)) | _runs(np.diff(v))


def _runs(s):
    same = np.isclose(s[1:], s[:-1], rtol=1e-3, atol=1e-6) & (np.abs(s[1:]) > 0)
    m = np.zeros(len(s) + 1, bool)
    i = 0
    while i < len(same):
        if same[i]:
            j = i
            while j < len(same) and same[j]:
                j += 1
            if j - i + 2 >= RAMP_MIN:                # same[i..j-1] covers points i..j+1
                m[i:j + 2] = True
            i = j
        else:
            i += 1
    return m


def prepare(param, probe=None):
    d = load(param, probe)
    n0, n_imp = len(d), int(d.Was_Imputed.sum())
    d = d[~d.Was_Imputed]
    comp = d.decimals > MAX_DECIMALS
    d = d[~comp].reset_index(drop=True)               # ramps must be found among real rows only
    d["ramp"] = ramp_mask(d.Datetime, d.Value)
    info = {"rows": n0, "imputed_dropped": n_imp, "computed_dropped": int(comp.sum()),
            "ramp_points": int(d.ramp.sum())}
    d.loc[d.ramp, "Value"] = np.nan
    return d[["Datetime", "Value"]].dropna(), info


def hampel_flags(x, w=HAMPEL_W, k=HAMPEL_K):
    med = x.rolling(w, center=True, min_periods=3).median()
    mad = (x - med).abs().rolling(w, center=True, min_periods=3).median() * 1.4826
    return ((x - med).abs() > k * mad) & (mad > 0)


def attach(base, other, name, tol):
    o = other.rename(columns={"Datetime": f"t_{name}", "Value": name})
    m = pd.merge_asof(base, o, left_on="t", right_on=f"t_{name}", direction="nearest", tolerance=tol)
    return m.drop(columns=[f"t_{name}"])


def main():
    OUT.mkdir(parents=True, exist_ok=True); REP.mkdir(parents=True, exist_ok=True)
    report = {}
    ec, report["EC"] = prepare("conductivity")
    ph, report["pH"] = prepare("ph")
    t2, report["T"] = prepare("temperature", "Temperature Sensor Two")
    t1, report["T1"] = prepare("temperature", "Temperature Sensor One")
    c = ec.rename(columns={"Datetime": "t", "Value": "EC"})
    c = attach(c, ph, "pH", CYCLE_TOL)
    c = attach(c, t2, "T", CYCLE_TOL)
    c = attach(c, t1, "T1", T1_TOL)
    for v, (lo, hi) in RANGE.items():
        c[f"{v}_range"] = c[v].notna() & ~c[v].between(lo, hi)
        c.loc[c[f"{v}_range"], v] = np.nan
        report[v]["range_fail"] = int(c[f"{v}_range"].sum())
    gap = c.t.diff().dt.total_seconds() / 60
    c["segment"] = (gap.isna() | (gap > SEGMENT_GAP_MIN)).cumsum()
    for v in RANGE:
        c[f"{v}_spike"] = c.groupby("segment")[v].transform(lambda s: hampel_flags(s)).fillna(False).astype(bool)
        report[v]["spike_flag"] = int(c[f"{v}_spike"].sum())
        report[v]["in_cycles"] = int(c[v].notna().sum())
    c["complete_T_EC"] = c[["T", "EC"]].notna().all(axis=1)
    c["complete_T_EC_pH"] = c[["T", "EC", "pH"]].notna().all(axis=1)
    seg = c[c.complete_T_EC].groupby("segment").agg(n=("t", "size"), start=("t", "min"), end=("t", "max"))
    report["cycles"] = {
        "n": int(len(c)), "start": str(c.t.min()), "end": str(c.t.max()),
        "median_step_min": float(gap.median()),
        "complete_T_EC": int(c.complete_T_EC.sum()), "complete_T_EC_pH": int(c.complete_T_EC_pH.sum()),
        "last_complete_T_EC": str(c.t[c.complete_T_EC].max()),
        "segments_T_EC": int(len(seg)), "segments_T_EC_ge_1day": int(((seg.end - seg.start) >= pd.Timedelta("1D")).sum()),
        "pH_share_above_9": float((c.pH > 9).mean()),
    }
    c.to_csv(OUT / "weija_cycles.csv", index=False)
    (REP / "weija_quality.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
