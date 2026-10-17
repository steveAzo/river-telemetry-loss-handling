"""Tail checks for the outage models (complements outage_models.py).
1. Bootstrap 95% CI of the observed share of lost slots in outages >= 6 h and >= 24 h
   (resampling outages with replacement, 5000 draws, seed 20261011).
2. Empirical vs model survival P(outage >= L) at L = 1 h, 6 h, 24 h, 72 h.
3. Dependence: Spearman correlation between an outage's length and the following up-run's length,
   and lag-1 correlation of consecutive outage lengths (memoryless models assume both are zero).
Usage: python -I src/scoping/outage_tail_check.py
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats
sys.path.insert(0, "src/scoping")
from outage_models import runs_from_times, FITTERS, pmf  # noqa: E402

rng = np.random.default_rng(20261011)
CI_ROWS = []          # written to results/scoping/outage_ci.csv (for the paper's numbers)


def sequence(t, slot):
    """Alternating (up, outage) pairs in time order."""
    t = pd.Series(pd.to_datetime(t)).drop_duplicates().sort_values()
    k = np.maximum(np.rint(t.diff().dt.total_seconds().dropna().values / slot).astype(int), 1)
    ups, outs, run = [], [], 1
    for step in k:
        if step == 1:
            run += 1
        else:
            ups.append(run); outs.append(step - 1); run = 1
    return np.array(ups), np.array(outs)  # ups[i] precedes outs[i]


def check(label, t, slot):
    ups, outs = sequence(t, slot)
    h = 3600 / slot
    print(f"\n== {label} ({len(outs)} outages)")
    for L in (6, 24):
        Ls = int(np.ceil(L * h))
        obs = outs[outs >= Ls].sum() / outs.sum()
        bs = [(b[b >= Ls].sum() / b.sum()) for b in (rng.choice(outs, len(outs)) for _ in range(5000))]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        CI_ROWS.append({"record": label, "L_h": L, "share_obs": obs, "ci_lo": lo, "ci_hi": hi,
                        "n_outages_ge": int(np.sum(outs >= Ls)), "n_outages": len(outs)})
        print(f"  share of lost slots in outages >= {L:2d} h: {obs:.2f}  95% CI [{lo:.2f}, {hi:.2f}]  "
              f"(from {np.sum(outs >= Ls)} outages)")
    k = np.arange(1, outs.max() * 3 + 1, dtype=float)
    print("  P(outage >= L):      " + "  ".join(f"{L:>3d}h" for L in (1, 6, 24, 72)))
    print("    observed           " + "  ".join(f"{np.mean(outs >= np.ceil(L*h)):.3f}" for L in (1, 6, 24, 72)))
    for name, fit in FITTERS.items():
        par, _, _ = fit(outs.astype(float))
        p = pmf(name, par, k); p = p / p.sum()
        sf = lambda L: p[k >= np.ceil(L * h)].sum()
        print(f"    {name:17s}  " + "  ".join(f"{sf(L):.3f}" for L in (1, 6, 24, 72)))
    sr1 = stats.spearmanr(outs[:-1], ups[1:]); r1 = sr1.statistic   # outage -> following up-run
    sr2 = stats.spearmanr(outs[:-1], outs[1:]); r2 = sr2.statistic   # consecutive outages
    print(f"  Spearman(outage, next up-run) = {r1:+.2f};  Spearman(outage, next outage) = {r2:+.2f}  (memoryless: 0)")
    CI_ROWS.append({"record": label, "L_h": "spearman", "share_obs": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                    "n_outages_ge": np.nan, "n_outages": len(outs), "rho_out_next_up": r1, "p_out_next_up": sr1.pvalue, "rho_out_next_out": r2, "p_out_next_out": sr2.pvalue})


d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
check("InWaterSense node 1", d[d.node == 1].t, 611)
w = pd.read_csv("data/weija_raw/conductivity_cleaned_records.csv", parse_dates=["Datetime"])
w = w[w.Was_Imputed.astype(str) != "True"].Datetime
check("Weija conductivity", w, float(np.median(w.drop_duplicates().sort_values().diff().dt.total_seconds().dropna())))
pd.DataFrame(CI_ROWS).to_csv(sys.argv[1] if len(sys.argv) > 1 else "results/scoping/outage_ci.csv", index=False, float_format="%.6g")
