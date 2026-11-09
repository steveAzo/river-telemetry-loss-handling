"""Rescoping screen S7 (docs/RESCOPING_2026-10-31.md): VALUE OF INFORMATION for waking the slow probes.

Question: how much of the sensing oracle gap (sensing_headroom.py: fixed sampling needs 48-96 DO/pH wake-ups
per day, the oracle 14) can a CAUSAL policy close, depending on the information it has?

Design (fixed before running; pass/fail rule below):
- Server holds the last expensive sample (zero-order hold); a slot VIOLATES when the true DO (% sat) or pH
  differs from it by more than the v0.3 tolerance (DO 2.0, pH 0.1). Noise variant: truth and samples are
  centred 5-slot rolling medians (the node averages a short burst), so pH flicker cannot fake or hide a gain.
- One learned risk model per information set: P(violation at slot t | last sample k slots ago, features),
  pooled over sites, HistGradientBoostingClassifier. Lags restricted to the grid K; the policy samples at the
  first k in K whose predicted risk exceeds theta (forced at k = 96). Sweeping theta gives a frontier.
- Nested information sets:
    F0 lag only (equivalent to fixed sampling on the grid)
    F1 + clock (local solar hour, day of year) + last sampled DO and pH
    F2 + cheap probes now and their change over the lag (T, relative EC)
    F3 + solar radiation now, its change and its mean over the lag
    F4 + rainfall over the last 6 h and over the lag
    F5 + nearest same-river neighbour site's DO and pH change over the lag (an information BOUND: a real
         node could only learn this through the scarce downlink)
- Train on odd months of 2023, test on even months (every season in both). 2024 is not touched.
- Weather: Open-Meteo archive (ERA5-based) hourly radiation and rain at the site, used causally (the value
  stamped at hour H covers the hour before H); a stand-in for a local light sensor and rain gauge.
PASS RULE: at matched budgets of 24 and 48 samples/day, the best information set must cut the pooled violation
share by >= 30% relative to F0, in BOTH the raw and the noise variant. Otherwise the constructive core fails.
Usage (from Paper2/): python -I src/rescoping/voi_sensing.py
"""
import glob
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

OUT = "results/rescoping"
TOL = {"DO": 2.0, "pH": 0.1}
K = np.array([1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96])
META = ["results/scoping/usgs_scout_sites.csv", "results/scoping/chain_sites.csv"]
SETS = {
    "F0": ["k"],
    "F1": ["k", "hs", "hc", "ds", "dc", "do0", "ph0"],
    "F2": ["k", "hs", "hc", "ds", "dc", "do0", "ph0", "T", "dT", "dEC"],
    "F3": ["k", "hs", "hc", "ds", "dc", "do0", "ph0", "T", "dT", "dEC", "rad", "drad", "mrad"],
    "F4": ["k", "hs", "hc", "ds", "dc", "do0", "ph0", "T", "dT", "dEC", "rad", "drad", "mrad", "rain6", "rainl"],
    "F5": ["k", "hs", "hc", "ds", "dc", "do0", "ph0", "T", "dT", "dEC", "rad", "drad", "mrad", "rain6", "rainl",
           "nDO", "npH"],
}
THETAS = np.r_[np.geomspace(0.002, 0.6, 28)]


def load_site(s, lon, smooth):
    d = pd.read_csv(f"data/clean/usgs/{s}.csv", parse_dates=["t"]).set_index("t")
    d = d[~d.index.duplicated()]
    d = d.reindex(pd.date_range(d.index.min().floor("D"), d.index.max().ceil("D"), freq="15min"))
    if smooth:
        for c in ("DO", "pH"):
            d[c] = d[c].rolling(5, center=True, min_periods=3).median()
    w = pd.read_csv(f"data/raw/openmeteo/{s}_2023.csv", parse_dates=["t"]).set_index("t")
    w = w.reindex(d.index, method="ffill")                 # value stamped at H covers (H-1, H]: causal
    d["rad"], d["precip"] = w.sw_rad.to_numpy(), w.precip.to_numpy()
    d["rain_slot"] = d.precip / 4.0                         # mm per 15-min slot (hourly total spread)
    loc = d.index.hour + d.index.minute / 60 + lon / 15.0   # local solar hour
    d["hs"], d["hc"] = np.sin(2 * np.pi * loc / 24), np.cos(2 * np.pi * loc / 24)
    doy = d.index.dayofyear
    d["ds"], d["dc"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    return d


def features(d, nb, t_idx, k):
    """feature frame for target slots t_idx with the last sample k slots earlier (vectorised)"""
    s_idx = t_idx - k
    f = pd.DataFrame({"k": np.full(len(t_idx), k)})
    for c in ("hs", "hc", "ds", "dc"):
        f[c] = d[c].to_numpy()[t_idx]
    f["do0"], f["ph0"] = d.DO.to_numpy()[s_idx], d.pH.to_numpy()[s_idx]
    T, EC = d["T"].to_numpy(), d.EC.to_numpy()
    f["T"], f["dT"] = T[t_idx], T[t_idx] - T[s_idx]
    f["dEC"] = (EC[t_idx] - EC[s_idx]) / np.maximum(np.abs(EC[s_idx]), 1e-6)
    rad = d.rad.to_numpy(); crad = np.r_[0, np.nancumsum(rad)]
    f["rad"], f["drad"] = rad[t_idx], rad[t_idx] - rad[s_idx]
    f["mrad"] = (crad[t_idx + 1] - crad[s_idx + 1]) / k
    rain = np.r_[0, np.nancumsum(d.rain_slot.to_numpy())]
    f["rain6"] = rain[t_idx + 1] - rain[np.maximum(t_idx + 1 - 24, 0)]
    f["rainl"] = rain[t_idx + 1] - rain[s_idx + 1]
    if nb is not None:
        f["nDO"] = nb.DO.to_numpy()[t_idx] - nb.DO.to_numpy()[s_idx]
        f["npH"] = nb.pH.to_numpy()[t_idx] - nb.pH.to_numpy()[s_idx]
    else:
        f["nDO"] = f["npH"] = np.nan
    return f


def violates(d, t_idx, s_idx):
    do, ph = d.DO.to_numpy(), d.pH.to_numpy()
    return ((np.abs(do[t_idx] - do[s_idx]) > TOL["DO"] + 1e-9) | (np.abs(ph[t_idx] - ph[s_idx]) > TOL["pH"] + 1e-9))


def neighbours(sites, meta):
    out = {}
    for s in sites:
        same = [o for o in sites if o != s and meta.loc[o, "river"] == meta.loc[s, "river"]]
        if same:
            dist = [np.hypot(meta.loc[o, "dec_lat_va"] - meta.loc[s, "dec_lat_va"],
                             meta.loc[o, "dec_long_va"] - meta.loc[s, "dec_long_va"]) for o in same]
            out[s] = same[int(np.argmin(dist))]
    return out


KPOS = {int(k): j for j, k in enumerate(K)}


def simulate(do, ph, valid, test_mask, prob, theta):
    """prob[j][t] = risk at slot t for lag K[j]. The node may only wake when a reading exists (valid).
    Missing readings are skipped (not scored, hold kept); the hold restarts only outside test months.
    Returns (samples, violations, scored) on test slots."""
    samples = viol = scored = 0
    last = -1
    for t in range(len(do)):
        if not test_mask[t]:
            last = -1; continue
        if not valid[t]:
            continue
        scored += 1
        if last < 0:
            last = t; samples += 1; continue
        k = t - last
        j = KPOS.get(k)
        if k >= 96 or (j is not None and prob[j][t] > theta):
            last = t; samples += 1
        elif abs(do[t] - do[last]) > TOL["DO"] + 1e-9 or abs(ph[t] - ph[last]) > TOL["pH"] + 1e-9:
            viol += 1
    return samples, viol, scored


def main(max_sites=None):
    os.makedirs(OUT, exist_ok=True)
    meta = pd.concat([pd.read_csv(f, dtype={"site_no": str}) for f in META]).drop_duplicates("site_no")
    meta = meta.set_index("site_no")
    sites = []
    for p in sorted(glob.glob("data/clean/usgs/*.csv")):
        h = pd.read_csv(p, nrows=2)
        if {"DO", "pH", "EC", "T"} <= set(h.columns):
            sites.append(os.path.basename(p)[:-4])
    sites = sites[:max_sites] if max_sites else sites
    nbmap = neighbours(sites, meta)
    rng = np.random.default_rng(20261103)
    results = []
    for variant, smooth in (("raw", False), ("noise", True)):
        data = {s: load_site(s, meta.loc[s, "dec_long_va"], smooth) for s in sites}
        data = {s: d for s, d in data.items() if d.DO.notna().sum() >= 5000 and d.pH.notna().sum() >= 5000}
        # training rows: odd months, lags on the grid, label = violation of the held value
        X, y = [], []
        for s, d in data.items():
            nb = data.get(nbmap.get(s)) if nbmap.get(s) in data else None
            if nb is not None:
                nb = nb.reindex(d.index)
            ok = d.DO.notna().to_numpy() & d.pH.notna().to_numpy()
            odd = (d.index.month % 2 == 1)
            for k in K:
                t = np.flatnonzero(ok & odd)
                t = t[(t >= k)]
                t = t[ok[t - k] & odd[t - k]]
                if len(t) > 3000:
                    t = rng.choice(t, 3000, replace=False)
                X.append(features(d, nb, t, k)); y.append(violates(d, t, t - k))
        X = pd.concat(X, ignore_index=True); y = np.concatenate(y)
        print(variant, "training rows", len(X), "violation share", round(y.mean(), 3), flush=True)
        models = {}
        for name, cols in SETS.items():
            m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                               random_state=0)
            m.fit(X[cols], y)
            models[name] = m
        # test: even months, simulate the policy per site and theta
        for s, d in data.items():
            nb = data.get(nbmap.get(s)) if nbmap.get(s) in data else None
            if nb is not None:
                nb = nb.reindex(d.index)
            valid = d.DO.notna().to_numpy() & d.pH.notna().to_numpy()
            test = (d.index.month % 2 == 0)
            n = len(d)
            do, ph = d.DO.to_numpy(), d.pH.to_numpy()
            tt = np.flatnonzero(test & valid)                    # only these slots are ever checked
            for name, cols in SETS.items():
                prob = []
                for k in K:
                    t = tt[tt >= k]
                    p = np.zeros(n)
                    p[t] = models[name].predict_proba(features(d, nb, t, k)[cols])[:, 1]
                    prob.append(p)
                for th in THETAS:
                    sm, v, sc = simulate(do, ph, valid, test, prob, th)
                    results.append({"variant": variant, "site": s, "set": name, "theta": th,
                                    "samples": sm, "viol": v, "scored": sc,
                                    "has_nb": nb is not None})
            print(variant, s, flush=True)
    r = pd.DataFrame(results)
    r.to_csv(f"{OUT}/voi_sensing.csv", index=False)
    report(r)


def frontier_at(g, budget):
    """pooled violation share at a pooled budget (samples/day), log-linear interpolation over theta"""
    agg = g.groupby("theta")[["samples", "viol", "scored"]].sum()
    spd = agg.samples / agg.scored * 96
    vio = agg.viol / agg.scored
    o = np.argsort(spd.to_numpy())
    x, yv = spd.to_numpy()[o], vio.to_numpy()[o]
    if budget < x.min() or budget > x.max():
        return np.nan
    return float(np.interp(np.log(budget), np.log(x), yv))


def report(r):
    lines = []
    for variant in ("raw", "noise"):
        for subset, rr in (("all sites", r), ("sites with a neighbour", r[r.has_nb])):
            g = rr[rr.variant == variant]
            row = {b: {name: frontier_at(g[g.set == name], b) for name in SETS} for b in (12, 24, 48)}
            lines.append(f"\n{variant} | {subset} ({g.site.nunique()} sites): pooled violation share at budget")
            for b, vals in row.items():
                base = vals["F0"]
                cells = "  ".join(f"{k} {v:.4f} ({(1 - v / base) * 100:+.0f}%)" if np.isfinite(v) and base > 0
                                  else f"{k} n/a" for k, v in vals.items())
                lines.append(f"  {b:>2}/day: {cells}")
    txt = "\n".join(lines)
    print(txt)
    open(f"{OUT}/voi_sensing.log", "a", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
