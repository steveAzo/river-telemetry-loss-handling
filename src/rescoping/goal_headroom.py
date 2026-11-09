"""Rescoping screen S6 (docs/RESCOPING_2026-10-31.md): headroom for GOAL-ORIENTED sensing.

Goal: the server must know, at every 15-min slot, whether each threshold is crossed: DO < 5 mg/L, pH < 6.5,
pH > 9 (the thresholds confirmed for Paper 3). The server holds the decision of the last expensive sample.
A slot is MISSED when the true decision differs from the held one. Rows with missing DO or pH are not scored.
Policies (DO and pH woken together):
  fixed(k)        every k slots
  safe(q, kmax)   after a sample, sleep k = min over parameters of floor(distance to the nearest threshold /
                  r_q), capped at kmax, at least 1. r_q = q-quantile of the absolute per-slot change of that
                  parameter over the previous 30 days of SAMPLED values, divided by their spacing (causal;
                  the first 30 days use fixed(1))
  oracle          sample exactly when the decision flips (lower bound)
Development data: 2023 USGS records only (data/clean/usgs).
Usage (from Paper2/): python -I src/rescoping/goal_headroom.py
"""
import glob
import os

import numpy as np
import pandas as pd

OUT = "results/rescoping"
TH = {"DO": [5.0], "pH": [6.5, 9.0]}


def state(do, ph):
    return (do < 5.0, ph < 6.5, ph > 9.0)


def run(do, ph, policy):
    n = len(do)
    ok = np.isfinite(do) & np.isfinite(ph)
    held, last = None, -1
    samples = missed = 0
    hist = []                                       # (index, do, ph) of samples
    for i in range(n):
        if not ok[i]:
            continue
        s = state(do[i], ph[i])
        if held is None or policy(i, last, hist, s):
            held, last = s, i
            hist.append((i, do[i], ph[i]))
            samples += 1
        elif s != held:
            missed += 1
    return samples, missed, int(ok.sum())


def fixed(k):
    return lambda i, last, hist, s: i - last >= k


def safe(q, kmax, window=96 * 30):
    cache = {}

    def want(i, last, hist, s):
        if last not in cache:
            h = [x for x in hist if x[0] >= last - window]
            if len(h) < 50 or hist[0][0] > last - window:
                cache[last] = 1
            else:
                a = np.array(h)
                gap = np.diff(a[:, 0])
                k = kmax
                for col, p in ((1, "DO"), (2, "pH")):
                    rate = np.abs(np.diff(a[:, col])) / gap
                    r = max(np.quantile(rate, q), 1e-6)
                    dist = min(abs(a[-1, col] - t) for t in TH[p])
                    k = min(k, int(dist / r))
                cache[last] = max(1, k)
        return i - last >= cache[last]
    return want


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for path in sorted(glob.glob("data/clean/usgs/*.csv")):
        d = pd.read_csv(path)
        if not {"DO_mgL", "pH"} <= set(d.columns) or d.DO_mgL.notna().sum() < 5000:
            continue
        do, ph = d.DO_mgL.to_numpy(float), d.pH.to_numpy(float)
        site = os.path.basename(path)[:-4]
        ok = np.isfinite(do) & np.isfinite(ph)
        flips = sum(state(do[i], ph[i]) != state(do[j], ph[j])
                    for j, i in zip(np.flatnonzero(ok)[:-1], np.flatnonzero(ok)[1:]))
        near = np.mean((np.abs(do[ok] - 5) < 1) | (np.abs(ph[ok] - 6.5) < 0.3) | (np.abs(ph[ok] - 9) < 0.3))
        specs = [("oracle", 0, None)] + [("fixed", k, fixed(k)) for k in (1, 4, 16, 32, 96)] + \
                [("safe", f"{q}/{kmax}", safe(q, kmax)) for q in (0.99, 0.999, 1.0) for kmax in (32, 96, 192)]
        for kind, par, pol in specs:
            if pol is None:
                s, m, sc = flips + 1, 0, int(ok.sum())
            else:
                s, m, sc = run(do, ph, pol)
            rows.append({"site": site, "kind": kind, "param": par, "samples_per_day": s / sc * 96,
                         "missed": m / sc, "near_share": near, "scored": sc})
        print(site, flush=True)
    r = pd.DataFrame(rows)
    r.to_csv(f"{OUT}/goal_headroom.csv", index=False)
    g = r.groupby(["kind", "param"]).agg(spd_median=("samples_per_day", "median"), spd_mean=("samples_per_day", "mean"),
                                         missed_median=("missed", "median"), missed_max=("missed", "max"))
    print(f"sites {r.site.nunique()}; near-threshold share median {r.near_share.median():.3f}")
    with pd.option_context("display.width", 200):
        print(g.round(5).to_string())


if __name__ == "__main__":
    main()
