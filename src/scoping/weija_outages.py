"""Outage record of the Weija deployment (Ghana, 2018-19), from the received per-parameter files.
Only real (non-imputed) records count as delivered. For each parameter/probe, the cadence is the
median step within each month; a gap of k cadence steps = k-1 missing slots.
Usage: python -I src/scoping/weija_outages.py data/weija_raw [out.csv]
"""
import sys, glob, pandas as pd, numpy as np
ROWS = []
for f in sorted(glob.glob(sys.argv[1] + "/*_cleaned_records.csv")):
    d = pd.read_csv(f, parse_dates=["Datetime"])
    d = d[d.Was_Imputed.astype(str) != "True"]
    for probe, g in d.groupby("Probe Name"):
        t = g.Datetime.drop_duplicates().sort_values()
        if len(t) < 200: continue
        dt = t.diff().dt.total_seconds().dropna()
        step = dt.median()
        k = (dt / step).round() - 1
        out = k[k >= 1]
        lost = out.sum()
        def share(lo, hi):
            m = (out >= lo) & (out <= hi); return f"{m.mean():.2f}/{out[m].sum()/max(lost,1):.2f}"
        h = 3600 / step
        L24 = int(24 * h) + 1                     # >= 1 day (same cut as the printed column)
        ROWS.append({"file": f.split("/")[-1].split("\\")[-1], "probe": probe, "start": t.min(), "end": t.max(),
                     "step_min": step / 60, "rx": len(t), "missing": int(lost), "loss": lost / (lost + len(t)),
                     "events": len(out), "lost_share_ge_1d": out[out >= L24].sum() / max(lost, 1),
                     "max_outage_d": out.max() * step / 86400 if len(out) else 0.0})
        print(f"{probe[:28]:28s} {t.min():%Y-%m-%d}..{t.max():%Y-%m-%d} step={step/60:5.1f}min rx={len(t):6d} "
              f"loss={lost/(lost+len(t)):.2f} events={len(out):4d} | events/lost-share: 1slot {share(1,1)}  "
              f"<6h {share(2,int(6*h))}  6-24h {share(int(6*h)+1,int(24*h))}  >=1d {share(int(24*h)+1,1e9)}  max={out.max()*step/86400 if len(out) else 0:.1f}d")
if len(sys.argv) > 2:
    pd.DataFrame(ROWS).to_csv(sys.argv[2], index=False, float_format="%.6g")
