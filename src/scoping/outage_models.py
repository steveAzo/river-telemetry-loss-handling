"""Fit outage-process models to real delivery records (PAPER2_SCOPING.md section 2.5).

A delivery record is reduced to alternating up-runs (consecutive delivered slots) and outages
(consecutive missing slots), in units of the nominal reporting slot. For outage lengths k >= 1 we fit:
  geom      geometric (memoryless loss; = Gilbert two-state Markov model)
  geom2     mixture of two geometrics (= Markov chain with one up state and two down states:
            'short loss' and 'long outage'); fitted by EM
  dlnorm    discretised lognormal (probability of [k-0.5, k+0.5), renormalised to k >= 1)
  zeta      discrete power law P(k) ~ k^-a, k >= 1
Up-run lengths are fitted with geom and geom2 as well.
Model choice: AIC (a fit score that penalises extra parameters; lower is better), plus two checks
that matter for the paper: the share of lost slots that falls in outages >= 6 h and >= 24 h,
predicted by each fitted model vs observed.

Records:
  InWaterSense node 1: cycles from data/clean/inws_cycles.csv, slot 611 s.
  Weija: non-imputed conductivity records (data/weija_raw), slot = median step (32.5 min).
         Unflagged interpolation hides some short outages (Paper 1), so short counts are lower bounds.
Usage: python -I src/scoping/outage_models.py results/scoping/outage_models.csv
"""
import sys
import numpy as np
import pandas as pd
from scipy import optimize, special, stats


def runs_from_times(t, slot_s):
    """Up-run and outage lengths (in slots) from delivery timestamps."""
    t = pd.Series(pd.to_datetime(t)).drop_duplicates().sort_values()
    k = np.rint(t.diff().dt.total_seconds().dropna().values / slot_s).astype(int)
    k = np.maximum(k, 1)
    outages = k[k > 1] - 1
    ups, run = [], 1  # up-run = delivered slots between outages
    for step in k:
        if step == 1:
            run += 1
        else:
            ups.append(run); run = 1
    ups.append(run)
    return np.array(ups), outages


# ---- discrete distributions on k >= 1: log-pmf functions and fitters ----
def ll_geom(k, q):
    return np.log(1 - q) + (k - 1) * np.log(q)


def fit_geom(k):
    q = 1 - 1 / k.mean()
    return {"q": q}, ll_geom(k, q).sum(), 1


def fit_geom2(k, iters=2000):
    # EM for a two-component geometric mixture; start from short/long split at the median
    w, q1, q2 = 0.7, 1 - 1 / max(1.01, k[k <= np.median(k)].mean()), 1 - 1 / max(1.5, k[k > np.median(k)].mean())
    prev = -np.inf
    for _ in range(iters):
        a = np.log(w) + ll_geom(k, q1); b = np.log(1 - w) + ll_geom(k, q2)
        m = np.logaddexp(a, b); r = np.exp(a - m)
        ll = m.sum()
        w = np.clip(r.mean(), 1e-6, 1 - 1e-6)
        q1 = 1 - r.sum() / max((r * k).sum(), 1e-12); q2 = 1 - (1 - r).sum() / max(((1 - r) * k).sum(), 1e-12)
        q1, q2 = np.clip([q1, q2], 1e-9, 1 - 1e-9)
        if ll - prev < 1e-9:
            break
        prev = ll
    if q1 > q2:  # component 1 = short
        w, q1, q2 = 1 - w, q2, q1
    return {"w_short": w, "q_short": q1, "q_long": q2}, ll, 3


def logpmf_dlnorm(k, mu, s):
    """log P(K = k | K >= 1) for a lognormal discretised to [k - 0.5, k + 0.5).
    Computed with log upper-tail probabilities (special.log_ndtr) so that it stays exact in the far
    tails. (The first version divided two underflowed probabilities; with clipping, the optimiser could
    reach a spurious 'perfect' fit at extreme mu. Fixed 2026-10-12.)"""
    k = np.asarray(k, dtype=float)
    la = special.log_ndtr(-(np.log(k - 0.5) - mu) / s)      # log P(X > k - 0.5)
    lb = special.log_ndtr(-(np.log(k + 0.5) - mu) / s)      # log P(X > k + 0.5)
    lc = special.log_ndtr(-(np.log(0.5) - mu) / s)          # log P(X > 0.5)
    return la + np.log1p(-np.exp(np.minimum(lb - la, -1e-16))) - lc


def pmf_dlnorm(k, mu, s):
    return np.exp(logpmf_dlnorm(k, mu, s))


def fit_dlnorm(k):
    """Weighted maximum likelihood on the unique lengths, multi-start over a grid of starting points."""
    v, c = np.unique(np.asarray(k, dtype=float), return_counts=True)
    f = lambda p: -(c * logpmf_dlnorm(v, p[0], np.exp(p[1]))).sum()
    best = None
    for mu0 in np.linspace(-20, 8, 15):
        for ls0 in np.linspace(-1.0, 2.5, 8):
            r = optimize.minimize(f, [mu0, ls0], method="Nelder-Mead",
                                  options={"maxiter": 8000, "xatol": 1e-10, "fatol": 1e-12})
            if np.isfinite(r.fun) and (best is None or r.fun < best.fun):
                best = r
    return {"mu": best.x[0], "sigma": np.exp(best.x[1])}, -best.fun, 2


def fit_zeta(k):
    f = lambda a: -(-a * np.log(k) - np.log(special.zeta(a, 1))).sum()
    r = optimize.minimize_scalar(f, bounds=(1.0001, 10), method="bounded")
    return {"alpha": r.x}, -r.fun, 1


def pmf(name, par, k):
    if name == "geom":
        return np.exp(ll_geom(k, par["q"]))
    if name == "geom2":
        return par["w_short"] * np.exp(ll_geom(k, par["q_short"])) + (1 - par["w_short"]) * np.exp(ll_geom(k, par["q_long"]))
    if name == "dlnorm":
        return pmf_dlnorm(k, par["mu"], par["sigma"])
    if name == "zeta":
        return k ** -par["alpha"] / special.zeta(par["alpha"], 1)


def long_share(name, par, L, kmax):
    """Share of lost slots in outages >= L slots, under the fitted model, truncated at kmax
    (the observed record length): power laws with a <= 2 have no finite mean otherwise."""
    k = np.arange(1, kmax + 1, dtype=float)
    p = pmf(name, par, k)
    return (k * p)[k >= L].sum() / (k * p).sum()


FITTERS = {"geom": fit_geom, "geom2": fit_geom2, "dlnorm": fit_dlnorm, "zeta": fit_zeta}


def analyse(label, ups, outs, slot_s, n_slots):
    rows = []
    h = 3600 / slot_s
    obs6 = outs[outs >= 6 * h].sum() / outs.sum(); obs24 = outs[outs >= 24 * h].sum() / outs.sum()
    print(f"\n== {label}: slot {slot_s/60:.1f} min, {len(outs)} outages, loss {outs.sum()/n_slots:.3f}, "
          f"median outage {np.median(outs):.0f} slots, max {outs.max()} slots ({outs.max()/h/24:.1f} d); "
          f"observed share of lost slots in outages >=6h {obs6:.2f}, >=24h {obs24:.2f}")
    for name, fit in FITTERS.items():
        par, ll, npar = fit(outs.astype(float))
        aic = 2 * npar - 2 * ll
        s6 = long_share(name, par, int(np.ceil(6 * h)), n_slots); s24 = long_share(name, par, int(np.ceil(24 * h)), n_slots)
        rows.append({"record": label, "what": "outage", "model": name, "aic": aic, "share6h_model": s6, "share6h_obs": obs6,
                     "share24h_model": s24, "share24h_obs": obs24, "params": par})
        print(f"  outage {name:7s} AIC {aic:9.1f}  share>=6h {s6:.2f} (obs {obs6:.2f})  share>=24h {s24:.2f} (obs {obs24:.2f})  {fmt(par)}")
    for name in ["geom", "geom2"]:
        par, ll, npar = FITTERS[name](ups.astype(float))
        rows.append({"record": label, "what": "up", "model": name, "aic": 2 * npar - 2 * ll, "params": par})
        print(f"  up-run {name:7s} AIC {2*npar-2*ll:9.1f}  mean up-run {ups.mean():.1f} slots  {fmt(par)}")
    best = min((r for r in rows if r["what"] == "outage"), key=lambda r: r["aic"])
    print(f"  -> best outage model by AIC: {best['model']}")
    return rows


def fmt(par):
    return " ".join(f"{k}={v:.4g}" for k, v in par.items())


def main(out):
    rows = []
    d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    t = d[d.node == 1].t
    ups, outs = runs_from_times(t, 611)
    rows += analyse("InWaterSense node 1", ups, outs, 611, ups.sum() + outs.sum())
    w = pd.read_csv("data/weija_raw/conductivity_cleaned_records.csv", parse_dates=["Datetime"])
    w = w[w.Was_Imputed.astype(str) != "True"]
    tw = w.Datetime.drop_duplicates().sort_values()
    slot = float(np.median(tw.diff().dt.total_seconds().dropna()))
    ups, outs = runs_from_times(tw, slot)
    rows += analyse("Weija conductivity", ups, outs, slot, ups.sum() + outs.sum())
    pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main(sys.argv[1])
