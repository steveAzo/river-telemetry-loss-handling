"""Review C4/E4: contemporary deep imputers on the river-chain gap protocol.

Models (PyPOTS 1.5, CPU): SAITS (self-attention imputation, transformer; Du et al. 2023) and StemGNN (graph neural
network with a learned inter-series graph; Cao et al. 2020). GRIN/SPIN need torch-geometric, which this machine
(3.6 GB RAM, < 5 GB disk) cannot hold; ImputeFormer (KDD 2024) was tried and dropped because it did not finish
training the smallest chain in 20 min on this CPU (SAITS: 73 s).

Normalisation: per window and series, from the window's observed values (RevIN-style). A first run with global
z-scores (half-year mean and SD) under-fitted by an order of magnitude even on 1-h gaps; it was discarded before any
reporting, and the change is stated in the paper.
Protocol (strictly time-split, no leakage):
  * per river chain, every site's T, EC, pH, DO on a common 1-h grid for 2023 (as chain_outage.py);
  * training and model selection on the first half only: 192-h windows, stride 12 h; the last 15% of the first
    half is the validation set. Training masks: PyPOTS's random point masking PLUS, in half the windows, one
    random site losing all four parameters for 1-72 h (the evaluation scenario: an outage removes the whole
    node). Validation windows carry such a site block, and the checkpoint with the best block error is kept;
  * evaluation on gaps drawn from the SECOND half only: a gap of H in {1, 6, 24, 72} h at a target site removes
    all four of its parameters; the other sites stay observed. 'bridging': the gap sits in the middle of the
    window (data after the gap visible, as after a backfill); 'real time': the window ends with the gap (nothing
    of the target after it is visible; the neighbours are visible up to the end of the gap, which is optimistic
    for the deep models);
  * the classic estimators of the paper are scored on the SAME gaps: persistence and own diel (real time),
    interpolation (bridging), and the neighbour estimators with the neighbour chosen on the first half
    (highest 6-h-change correlation) and its lag and slope fitted there.
Metric per gap and parameter: maximum absolute error over the gap; within the L2 tolerance (inclusive, D5).
Run with the deep-learning environment:  .venv_deep/Scripts/python -I src/revision/deep_baselines.py <out dir> [chain ...]
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

import pypots.imputation.saits.data as saits_data
from pygrinder import mcar
from pypots.imputation import SAITS, StemGNN

CHAINS = {"delaware": "01427510,01438500,01458500,01463500", "illinois": "05537980,05543010,05553700,05559900,05586300",
          "tualatin": "14203500,14206241,14206694,14207200", "clackamas": "14209710,14210000,14211010",
          "mckenzie": "14162500,14163900", "monongahela": "03072655,03075070", "youghiogheny": "03081000,03083500",
          "schuylkill": "01473500,01474500", "klamath": "420853121505500,11509370,11509500"}
PARAMS = ["T", "EC", "pH", "DO"]
TOL = {"T": 0.2, "DO": 2.0, "pH": 0.1}             # EC: 2% of the target's median (as chain_outage.py)
W, STRIDE, HALF = 192, 12, 0.5
HOURS = [1, 6, 24, 72]
N_GAPS = 60                                       # per target site and gap length
EPS = 1e-9
_BLOCK = {"n_sites": 1, "rng": np.random.default_rng(0)}


def block_mcar(X, p):
    """PyPOTS's point masking plus, in half the windows, a whole-site block of 1-72 h (training augmentation)."""
    Xm = mcar(X, p=p)
    rng = _BLOCK["rng"]
    if rng.random() < 0.5:
        X_np = Xm.numpy() if hasattr(Xm, "numpy") else np.asarray(Xm)
        s = int(rng.integers(_BLOCK["n_sites"])); L = int(rng.integers(1, 73)); a = int(rng.integers(0, W - L))
        X_np[a:a + L, 4 * s:4 * s + 4] = np.nan
        Xm = torch.as_tensor(X_np) if hasattr(Xm, "numpy") else X_np
    return Xm


saits_data.mcar = block_mcar                      # used by every PyPOTS model that trains with MIT


def load(site):
    d = pd.read_csv(f"data/clean/usgs/{site}.csv", parse_dates=["t"], index_col="t")
    d.index = d.index.tz_convert(None) if d.index.tz is not None else d.index
    return d[[p for p in PARAMS if p in d.columns]].resample("1h").mean()


def chain_array(sites):
    data = {s: load(s) for s in sites}
    idx = pd.date_range("2023-01-01", "2023-12-31 23:00", freq="1h")
    Z = np.full((len(idx), 4 * len(sites)), np.nan)
    for k, s in enumerate(sites):
        Z[:, 4 * k:4 * k + 4] = data[s].reindex(idx).reindex(columns=PARAMS).to_numpy()
    return idx, Z


def fit_lag_slope(x, y, n_train):
    """as chain_outage.fit_lag_slope, on the first half; returns (lag, slope, r)"""
    xs, ys = pd.Series(x), pd.Series(y)
    dx = (xs - xs.shift(6)).iloc[:n_train]
    best = (0, 0.0, -1.0)
    for L in range(0, 49):
        dy = (ys.shift(L) - ys.shift(L + 6)).iloc[:n_train]
        m = dx.notna() & dy.notna()
        if m.sum() < 200:
            continue
        r = np.corrcoef(dx[m], dy[m])[0, 1]
        if r > best[2]:
            best = (L, float(np.dot(dx[m], dy[m]) / np.dot(dy[m], dy[m])), r)
    return best


def norm(X):
    """Per-window, per-series normalisation (RevIN-style) with the window's OBSERVED values; returns (Xn, mean, std).
    Global z-scores over the half-year left the within-window signal far from zero and the models made level errors
    of about 0.3 SD even across 1-h gaps (first run, discarded before reporting; see the module docstring)."""
    m = np.nanmean(X, axis=1, keepdims=True); s = np.nanstd(X, axis=1, keepdims=True)
    m = np.where(np.isfinite(m), m, 0.0); s = np.where(np.isfinite(s) & (s > 1e-6), s, 1.0)
    return (X - m) / s, m, s


def windows(Z, lo, hi):
    starts = np.arange(lo, hi - W + 1, STRIDE)
    return np.stack([Z[a:a + W] for a in starts]) if len(starts) else np.empty((0, W, Z.shape[1]))


def make_models(F, seed):
    torch.manual_seed(seed)
    common = dict(batch_size=32, epochs=100, patience=10, device="cpu", verbose=False)
    return {
        "SAITS": SAITS(n_steps=W, n_features=F, n_layers=2, d_model=64, n_heads=4, d_k=16, d_v=16, d_ffn=128,
                       dropout=0.1, **common),
        "StemGNN": StemGNN(n_steps=W, n_features=F, n_layers=1, n_stacks=1, d_model=16, dropout=0.3, **common),   # 7.5 M parameters; the 2x2x64 setting has 49 M at a 192-h window (its spectral layers grow with the window squared) and did not fit this machine
    }


def run_chain(name, out):
    sites = CHAINS[name].split(",")
    idx, Zraw = chain_array(sites)
    T = len(idx); half = int(HALF * T); F = Zraw.shape[1]
    Z = Zraw                                         # normalised per window (norm), never with data after the window
    _BLOCK["n_sites"] = len(sites); _BLOCK["rng"] = np.random.default_rng(20261017)
    va0 = int(0.85 * half)
    Xtr = norm(windows(Z, 0, va0))[0]
    Xva_ori = windows(Z, va0 - W // 2, half)
    rng = np.random.default_rng(1)
    Xva = Xva_ori.copy()
    for w in Xva:                                   # validation: one whole-site block per window
        s = int(rng.integers(len(sites))); L = int(rng.integers(1, 73)); a = int(rng.integers(0, W - L))
        w[a:a + L, 4 * s:4 * s + 4] = np.nan
    Xva_n, mv, sv = norm(Xva); Xva_on = (Xva_ori - mv) / sv
    models = make_models(F, seed=20261017)
    t0 = time.time()
    for mname, m in models.items():
        m.fit({"X": Xtr}, {"X": Xva_n, "X_ori": Xva_on})
        print(f"  {name}: {mname} trained ({time.time() - t0:.0f} s)", flush=True)

    # ---- evaluation gaps in the second half
    tol = {p: TOL.get(p) for p in PARAMS}
    rows = []
    nb_choice = {}
    for k, s in enumerate(sites):
        for j, p in enumerate(PARAMS):
            best = None
            for k2, s2 in enumerate(sites):
                if k2 == k:
                    continue
                L, b, r = fit_lag_slope(Zraw[:, 4 * k + j], Zraw[:, 4 * k2 + j], half)
                if r > 0 and (best is None or r > best[3]):
                    best = (k2, L, b, r)
            nb_choice[(k, j)] = best
    for k, s in enumerate(sites):
        med = np.nanmedian(Zraw[:, 4 * k:4 * k + 4], axis=0)
        for H in HOURS:
            cand = []
            for t in range(max(half, W), T - H - 1):
                if np.isfinite(Zraw[t - 25:t + H + 1, 4 * k:4 * k + 4]).any(axis=1).all():
                    cand.append(t)
            if len(cand) < 20:
                continue
            gaps = rng.choice(cand, min(N_GAPS, len(cand)), replace=False)
            for mode in ("bridging", "realtime"):
                starts = [t - (W - H) // 2 if mode == "bridging" else t + H - W for t in gaps]
                ok = [(a, t) for a, t in zip(starts, gaps) if a >= 0 and a + W <= T]
                Xin = np.stack([Z[a:a + W].copy() for a, _ in ok])
                for n_, (a, t) in enumerate(ok):
                    Xin[n_, t - a:t - a + H, 4 * k:4 * k + 4] = np.nan
                    if mode == "realtime":
                        Xin[n_, t - a + H:, 4 * k:4 * k + 4] = np.nan     # nothing after the gap (window ends there)
                Xin_n, m_in, s_in = norm(Xin)
                preds = {mn: m.predict({"X": Xin_n})["imputation"] * s_in + m_in for mn, m in models.items()}
                for n_, (a, t) in enumerate(ok):
                    for j, p in enumerate(PARAMS):
                        c = 4 * k + j
                        truth = Zraw[t:t + H, c]
                        if not (np.isfinite(truth).all() and np.isfinite(Zraw[[t - 1, t - 25], c]).all()):
                            continue
                        tl = tol[p] if tol[p] is not None else 0.02 * med[j]
                        est = {mn: pr[n_, t - a:t - a + H, c] for mn, pr in preds.items()}
                        x0 = Zraw[t - 1, c]
                        diel = x0 + (Zraw[t - 24:t - 24 + H, c] - Zraw[t - 25, c])
                        if mode == "realtime":
                            est["persistence"] = np.full(H, x0)
                            est["own diel"] = diel
                            nb = nb_choice[(k, j)]
                            if nb is not None:
                                k2, L, b, _ = nb
                                y = pd.Series(Zraw[:, 4 * k2 + j]).shift(L).to_numpy()
                                if np.isfinite(y[[t - 1, t - 25]]).all() and np.isfinite(y[t:t + H]).all() \
                                        and np.isfinite(y[t - 24:t - 24 + H]).all():
                                    est["diel + neighbour"] = diel + b * ((y[t:t + H] - y[t - 1])
                                                                          - (y[t - 24:t - 24 + H] - y[t - 25]))
                                    est["neighbour change"] = x0 + b * (y[t:t + H] - y[t - 1])
                        else:
                            if not np.isfinite(Zraw[t + H, c]):
                                continue
                            ramp = np.linspace(0, 1, H + 2)[1:-1]
                            est["interpolation"] = x0 + (Zraw[t + H, c] - x0) * ramp
                            nb = nb_choice[(k, j)]
                            if nb is not None:
                                k2, L, b, _ = nb
                                y = pd.Series(Zraw[:, 4 * k2 + j]).shift(L).to_numpy()
                                if np.isfinite(y[[t - 1, t + H]]).all() and np.isfinite(y[t:t + H]).all():
                                    ylin = y[t - 1] + (y[t + H] - y[t - 1]) * ramp
                                    est["interp. + neighbour"] = est["interpolation"] + b * (y[t:t + H] - ylin)
                        for en, e in est.items():
                            err = float(np.nanmax(np.abs(truth - e)))
                            rows.append({"chain": name, "target": s, "param": p, "H_h": H, "mode": mode, "method": en,
                                         "max_err": err, "within": err <= tl + EPS, "tol": tl})
        print(f"  {name}: target {s} evaluated", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(out / f"deep_{name}.csv", index=False, float_format="%.6g")
    return d


def main(out, chains):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    for c in chains or list(CHAINS):
        if (out / f"deep_{c}.csv").exists():
            print(f"skip {c}"); continue
        t0 = time.time()
        run_chain(c, out)
        print(f"{c} done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
