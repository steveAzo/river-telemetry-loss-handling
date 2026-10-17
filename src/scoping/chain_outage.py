"""Outage-reconstruction test along a USGS river chain (PAPER2_SCOPING.md section 2.2, generalised).

For every ordered pair (target, neighbour) of sites in the chain, simulate outages of length H at the
target and reconstruct the missing values with:
  real-time (only data up to the outage start, plus the neighbour during the outage)
    persist   last value before the outage
    diel      last value + the target's own change over the same hours one day earlier
    nb_delta  last value + b * (neighbour change since outage start), neighbour lagged by L
    diel_nb   diel + b * (neighbour change minus the neighbour's own change one day earlier):
              the neighbour contributes only what its own diel pattern does not explain
  delay-tolerant (the first value after the outage is also known: backfill)
    interp    straight line between the values before and after the outage
    interp_nb interp + b * (neighbour's deviation from its own straight line over the same window)
The lag L (0..48 h) and the slope b are fitted on the first 20% of the year only (6-h differences);
outages are drawn from the remaining 80%. All series on a common 1-h grid (Trenton is hourly).
Metric: max |error| over the outage; reported as the median over outages, and as the share of
outages whose max error is within the Paper 1 L2 tolerance (T 0.2 degC, DO 2 %sat, pH 0.1, EC 2%).
Usage: python -I src/scoping/chain_outage.py <chain name> <site1,site2,...> <out.csv>
"""
import sys
import numpy as np
import pandas as pd

PARAMS = ["T", "EC", "pH", "DO"]
HOURS = [1, 3, 6, 12, 24, 48, 72]
N_OUT = 300
TRAIN = 0.2


def load(site):
    d = pd.read_csv(f"data/clean/usgs/{site}.csv", parse_dates=["t"], index_col="t")
    d.index = d.index.tz_convert(None) if d.index.tz is not None else d.index
    return d[[p for p in PARAMS if p in d.columns]].resample("1h").mean()


def tolerance(p, x):
    return {"T": 0.2, "DO": 2.0, "pH": 0.1}.get(p, 0.02 * np.nanmedian(x))


def fit_lag_slope(x, y, n_train):
    """Lag (h) and slope of 6-h changes of x on lagged 6-h changes of y, on the training part."""
    dx = (x - x.shift(6)).iloc[:n_train]
    best = (0, 0.0, -1.0)
    for L in range(0, 49):
        dy = (y.shift(L) - y.shift(L + 6)).iloc[:n_train]
        m = dx.notna() & dy.notna()
        if m.sum() < 200:
            continue
        r = np.corrcoef(dx[m], dy[m])[0, 1]
        if r > best[2]:
            b = np.dot(dx[m], dy[m]) / np.dot(dy[m], dy[m])
            best = (L, b, r)
    return best


def run_pair(chain, tname, nname, A, B, rng):
    rows = []
    for p in PARAMS:
        if p not in A or p not in B:
            continue
        # align the neighbour to the target's timestamps (positional indexing below)
        x = A[p]
        y = B[p].reindex(x.index)
        n_train = int(TRAIN * len(x))
        L, b, r = fit_lag_slope(x, y, n_train)
        if r < 0:
            continue
        yl = y.shift(L)
        tol = tolerance(p, x)
        xv, yv = x.values, yl.values
        for H in HOURS:
            # outage covers slots s .. s+H-1; needs s-1 and s+H observed, and 24 h of history
            ok = [s for s in range(max(n_train, 25), len(xv) - H - 1)
                  if not np.isnan(xv[s - 1 - 24:s + H + 1]).any() and not np.isnan(yv[s - 1 - 24:s + H + 1]).any()]
            if len(ok) < 50:
                continue
            errs = {k: [] for k in ["persist", "diel", "nb_delta", "diel_nb", "interp", "interp_nb"]}
            for s in rng.choice(ok, min(N_OUT, len(ok)), replace=False):
                truth = xv[s:s + H]
                x0, x1 = xv[s - 1], xv[s + H]
                y0, y1 = yv[s - 1], yv[s + H]
                ramp = np.linspace(0, 1, H + 2)[1:-1]
                ylin = y0 + (y1 - y0) * ramp
                est = {
                    "persist": np.full(H, x0),
                    "diel": x0 + (xv[s - 24:s - 24 + H] - xv[s - 25]),
                    "nb_delta": x0 + b * (yv[s:s + H] - y0),
                    "diel_nb": x0 + (xv[s - 24:s - 24 + H] - xv[s - 25])
                               + b * ((yv[s:s + H] - y0) - (yv[s - 24:s - 24 + H] - yv[s - 25])),
                    "interp": x0 + (x1 - x0) * ramp,
                    "interp_nb": x0 + (x1 - x0) * ramp + b * (yv[s:s + H] - ylin),
                }
                for k, e in est.items():
                    errs[k].append(np.nanmax(np.abs(truth - e)))
            row = {"chain": chain, "target": tname, "neighbour": nname, "param": p, "H_h": H,
                   "lag_h": L, "slope": round(b, 3), "r6h": round(r, 3), "n": len(errs["persist"]), "tol": tol}
            for k, v in errs.items():
                v = np.array(v)
                row[f"med_{k}"] = np.median(v)
                row[f"ok_{k}"] = np.mean(v <= tol + 1e-9)     # inclusive, robust to decimal round-off (D5)
            rows.append(row)
    return rows


def main(chain, sites, out):
    sites = sites.split(",")
    data = {s: load(s) for s in sites}
    rng = np.random.default_rng(20261011)
    rows = []
    for t in sites:
        for n in sites:
            if t != n:
                rows += run_pair(chain, t, n, data[t], data[n], rng)
                print(f"{chain}: target {t} neighbour {n} done", flush=True)
    pd.DataFrame(rows).to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    main(*sys.argv[1:4])
