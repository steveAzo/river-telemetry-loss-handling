"""Rescoping screen (docs/RESCOPING_2026-10-31.md, S5): headroom for sampling the EXPENSIVE probes less often.

Energy split (src/energy/model.py at 96 samples and 24 batches per day): with hourly batching the radio is
5-45% of a node's energy and sensing 40-89% once probes need >= 5 s awake per sample. So the lever is how often
the slow probes (DO, pH) are woken, not how reports are sent.

Question: at a bounded server error, how far below fixed-rate sampling can DO/pH sampling go, and how much of
that can a node reach from (a) its own expensive samples only (self-adaptive, the classic baseline) or
(b) cheap, fast probes (T, EC) read every slot?
Server value of DO and pH at each slot = the last expensive sample (zero-order hold). A slot VIOLATES when the
true DO or pH differs from it by more than the tolerance (TOL, as v0.3: DO 2 % sat, pH 0.1). Rows with a
missing DO or pH are not scored; a missing T/EC is treated as no change.
Policies (DO and pH are woken together, one sonde wake = one expensive sample):
  fixed(k)          every k slots
  selfadapt(kmax)   interval doubles (to kmax) while the change between the last two samples is < tol/2,
                    resets to 1 when it is > tol (Alippi-style adaptive sampling on the probe's own signal)
  gated(a, b, kmax) sample when |T - T_at_last| > a degC or |EC - EC_at_last| > b x EC_at_last, or kmax slots
                    have passed
  oracle            sample exactly at the first slot that would violate (needs the true values; lower bound)
Data: 2023 USGS records only (data/clean/usgs); the 2024 held-out year is not touched.
Usage (from Paper2/): python -I src/rescoping/sensing_headroom.py
"""
import glob
import os

import numpy as np
import pandas as pd

OUT = "results/rescoping"
TOL_DO, TOL_PH = 2.0, 0.1


def load(path):
    d = pd.read_csv(path)
    if not {"DO", "pH", "EC", "T"} <= set(d.columns):
        return None
    return tuple(d[c].to_numpy(float) for c in ("DO", "pH", "T", "EC"))      # d.T would be the transpose


def run(do, ph, T, ec, want):
    """want(i, last) -> bool: take an expensive sample at slot i (last = index of the previous sample).
    Returns (samples, violations, scored)."""
    n = len(do)
    ok = np.isfinite(do) & np.isfinite(ph)
    last, hd, hp = -1, np.nan, np.nan
    samples = viol = 0
    for i in range(n):
        if ok[i] and (last < 0 or want(i, last)):
            last, hd, hp = i, do[i], ph[i]
            samples += 1
        elif ok[i] and (abs(do[i] - hd) > TOL_DO + 1e-9 or abs(ph[i] - hp) > TOL_PH + 1e-9):
            viol += 1
    return samples, viol, int(ok.sum())


def policies():
    yield "oracle", 0, None
    for k in (1, 2, 4, 8, 16, 32, 64):
        yield "fixed", k, ("fixed", k)
    for kmax in (4, 8, 16, 32, 64, 96):
        yield "selfadapt", kmax, ("self", kmax)
    for a in (0.1, 0.2, 0.4):
        for b in (0.01, 0.02, 0.05):
            for kmax in (16, 32, 96):
                yield "gated", f"{a}/{b}/{kmax}", ("gated", a, b, kmax)


def make_want(spec, do, ph, T, ec):
    if spec is None:                                      # oracle: sample when the hold would violate now
        def want(i, last):
            return abs(do[i] - do[last]) > TOL_DO + 1e-9 or abs(ph[i] - ph[last]) > TOL_PH + 1e-9
        return want
    if spec[0] == "fixed":
        k = spec[1]
        return lambda i, last: i - last >= k
    if spec[0] == "self":
        kmax = spec[1]
        st = {"k": 1, "prev": None}

        def want(i, last):
            if i - last < st["k"]:
                return False
            if st["prev"] is not None:
                ch = max(abs(do[last] - do[st["prev"]]) / TOL_DO, abs(ph[last] - ph[st["prev"]]) / TOL_PH)
                st["k"] = 1 if ch > 1 else (min(2 * st["k"], kmax) if ch < 0.5 else st["k"])
            st["prev"] = last
            return True
        return want
    _, a, b, kmax = spec
    Tf = pd.Series(T).ffill().to_numpy(); Ef = pd.Series(ec).ffill().to_numpy()

    def want(i, last):
        if i - last >= kmax:
            return True
        dT = abs(Tf[i] - Tf[last]) if np.isfinite(Tf[i]) and np.isfinite(Tf[last]) else 0.0
        dE = abs(Ef[i] - Ef[last]) / max(abs(Ef[last]), 1e-9) if np.isfinite(Ef[i]) and np.isfinite(Ef[last]) else 0.0
        return dT > a or dE > b
    return want


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for path in sorted(glob.glob("data/clean/usgs/*.csv")):
        site = os.path.basename(path)[:-4]
        x = load(path)
        if x is None:
            continue
        do, ph, T, ec = x
        if np.isfinite(do).sum() < 5000:
            continue
        for kind, par, spec in policies():
            s, v, sc = run(do, ph, T, ec, make_want(spec, do, ph, T, ec))
            rows.append({"site": site, "kind": kind, "param": par, "samples_per_day": s / sc * 96,
                         "viol": v / sc, "scored": sc})
        print(site, flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(f"{OUT}/sensing_headroom.csv", index=False)
    g = d.groupby(["kind", "param"]).agg(samples_per_day=("samples_per_day", "median"),
                                         viol=("viol", "median"), viol_p90=("viol", lambda x: x.quantile(0.9)))
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(g.round(4).to_string())


if __name__ == "__main__":
    main()
