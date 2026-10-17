"""Review M1: absolute goodness of fit of the outage-length models, not only their AIC ranking.

For each record and model (geometric, two-geometric mixture, discrete lognormal, discrete power law):
  * discrete Kolmogorov-Smirnov statistic D = max_k |F_emp(k) - F_fit(k)|, with a parametric-bootstrap p-value
    (B draws from the fitted model, each refitted; Lilliefors-type, so estimation is accounted for);
  * 95% bootstrap CIs of the parameters (outages resampled with replacement);
  * empirical and fitted survival S(k) = P(K >= k) for a diagnostic figure;
  * robustness: AIC ranking without the single longest outage.
Censoring: an outage is a run of missing slots between two delivered slots, so every outage length in these
records is fully observed; only the first and last UP-runs are censored, and up-runs are not modelled here.
Records: InWaterSense node 1; Weija conductivity (v0.1 record) and the Weija node record (gap_cause.py); UVA
(all missing-frame runs of all sensors, results/scoping/uva_loss_runs.csv).
Usage (from Paper2/): python -I src/revision/outage_gof.py results/revision/gof [B]
"""
import sys

import numpy as np
import pandas as pd
from scipy import optimize, special, stats

sys.path.insert(0, "src")
sys.path.insert(0, "src/scoping")
from outage_models import FITTERS, logpmf_dlnorm, pmf, runs_from_times  # noqa: E402
from revision.gap_cause import runs, weija_links  # noqa: E402

KMAX_CDF = 200_000


def fit_dlnorm_from(k, start):
    v, c = np.unique(np.asarray(k, dtype=float), return_counts=True)
    f = lambda p: -(c * logpmf_dlnorm(v, p[0], np.exp(p[1]))).sum()
    r = optimize.minimize(f, [start["mu"], np.log(start["sigma"])], method="Nelder-Mead",
                          options={"maxiter": 4000, "xatol": 1e-8, "fatol": 1e-10})
    return {"mu": r.x[0], "sigma": np.exp(r.x[1])}


def refit(name, k, start):
    """Fast refit for the bootstrap (single start at the original estimate where the full fitter is slow)."""
    if name == "dlnorm":
        return fit_dlnorm_from(k, start)
    return FITTERS[name](k.astype(float))[0]


def sample(name, par, n, rng):
    if name == "geom":
        return rng.geometric(1 - par["q"], n)
    if name == "geom2":
        short = rng.random(n) < par["w_short"]
        return np.where(short, rng.geometric(1 - par["q_short"], n), rng.geometric(1 - par["q_long"], n))
    if name == "dlnorm":
        # exact draw from the lognormal truncated to X >= 0.5 (i.e. K >= 1) by inverse CDF; rejection sampling
        # stalls when mu is very negative (almost all mass below 0.5)
        lo = stats.norm.cdf((np.log(0.5) - par["mu"]) / par["sigma"])
        u = lo + (1 - lo) * rng.random(n)
        u = np.minimum(u, 1 - 1e-16)
        x = np.exp(par["mu"] + par["sigma"] * stats.norm.ppf(u))
        return np.maximum(1, np.floor(x + 0.5)).astype(np.int64)
    if name == "zeta":
        return stats.zipf.rvs(par["alpha"], size=n, random_state=rng)


def cdf(name, par, kmax):
    k = np.arange(1, kmax + 1, dtype=float)
    p = pmf(name, par, k)
    if name == "zeta":                               # exact normaliser; pmf already uses zeta(alpha)
        return np.cumsum(p)
    return np.cumsum(p) / max(p.sum(), 1e-300) if name == "dlnorm" else np.cumsum(p)


def ks(k, name, par):
    k = np.asarray(k, int)
    kmax = int(k.max())
    F = cdf(name, par, kmax)
    v, c = np.unique(k, return_counts=True)
    Fe = np.cumsum(c) / c.sum()                        # empirical CDF at the observed values
    Fe_before = np.r_[0, Fe[:-1]]
    Ff = F[v - 1]; Ff_before = np.where(v > 1, F[np.maximum(v - 2, 0)], 0.0)
    return float(max(np.abs(Fe - Ff).max(), np.abs(Fe_before - Ff_before).max()))


def records():
    # InWaterSense and the v0.1 Weija record: outages exactly as in Table II (outage_models.runs_from_times)
    d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    yield "InWaterSense", runs_from_times(d[d.node == 1].t, 611)[1], 611.0
    w = pd.read_csv("data/weija_raw/conductivity_cleaned_records.csv", parse_dates=["Datetime"])
    tw = w[w.Was_Imputed.astype(str) != "True"].Datetime.drop_duplicates().sort_values()
    wslot = float(np.median(tw.diff().dt.total_seconds().dropna()))
    yield "Weija (v0.1 EC record)", runs_from_times(tw, wslot)[1], wslot
    slot, up_v01, _, alive, _ = weija_links()
    yield "Weija (node record)", runs(~alive)[0], slot
    u = pd.read_csv("results/scoping/uva_loss_runs.csv")
    yield "UVA", u.len.to_numpy(int), 300.0


def main(out, B=200):
    B = int(B)
    rows, surv = [], []
    for rec, k, slot in records():
        k = np.asarray(k, int)
        rng = np.random.default_rng(20261017)
        ks_k = np.unique(np.r_[np.arange(1, 50), np.geomspace(50, k.max(), 60).astype(int)])
        for name, fitter in FITTERS.items():
            par, ll, npar = fitter(k.astype(float))
            D = ks(k, name, par)
            Db, pars = [], []
            for b in range(B):
                kb = sample(name, par, len(k), rng)
                try:
                    Db.append(ks(kb, name, refit(name, kb, par)))
                except Exception:
                    pass
                kr = rng.choice(k, len(k), replace=True)          # nonparametric resample for parameter CIs
                pars.append(refit(name, kr, par))
            Db = np.array(Db)
            p_val = (1 + np.sum(Db >= D)) / (1 + len(Db))
            ci = {f"{p}_lo": np.percentile([q[p] for q in pars], 2.5) for p in par}
            ci.update({f"{p}_hi": np.percentile([q[p] for q in pars], 97.5) for p in par})
            k_wo = np.sort(k)[:-1]
            _, ll_wo, _ = fitter(k_wo.astype(float))
            rows.append({"record": rec, "model": name, "n_outages": len(k), "aic": 2 * npar - 2 * ll,
                         "aic_without_longest": 2 * npar - 2 * ll_wo, "ks_D": D, "ks_p_boot": p_val, "B": len(Db),
                         **{f"par_{p}": v for p, v in par.items()}, **ci})
            print(f"{rec:24s} {name:7s} AIC {2 * npar - 2 * ll:10.1f}  KS D {D:.4f}  p {p_val:.4f}  {par}", flush=True)
            Fk = cdf(name, par, int(ks_k.max()))
            for kk in ks_k:
                surv.append({"record": rec, "model": name, "k": int(kk), "hours": kk * slot / 3600,
                             "S_fit": 1 - (Fk[kk - 2] if kk > 1 else 0.0)})
        for kk in ks_k:
            surv.append({"record": rec, "model": "empirical", "k": int(kk), "hours": kk * slot / 3600,
                         "S_fit": float(np.mean(k >= kk))})
    df = pd.DataFrame(rows)
    df["best_aic"] = df.groupby("record").aic.transform("min") == df.aic
    df["best_aic_without_longest"] = df.groupby("record").aic_without_longest.transform("min") == df.aic_without_longest
    df.to_csv(f"{out}_models.csv", index=False, float_format="%.6g")
    pd.DataFrame(surv).to_csv(f"{out}_survival.csv", index=False, float_format="%.6g")
    print(df[["record", "model", "aic", "best_aic", "best_aic_without_longest", "ks_D", "ks_p_boot"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:3])
