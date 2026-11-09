"""Summary of the S7 value-of-information screen (results/rescoping/voi_sensing.csv).

For each variant and information set: the wake-ups per day needed to match F0's violation share at F0 budgets of
24 and 48/day (pooled), the saving relative to F0, and per site the share of sites where the set needs fewer
wake-ups than F0 for the same violation share. Log-linear interpolation along each frontier.
Usage (from Paper2/): python -I src/rescoping/voi_summary.py
"""
import numpy as np
import pandas as pd

SETS = ["F0", "F1", "F2", "F3", "F4", "F5"]


def curve(g):
    a = g.groupby("theta")[["samples", "viol", "scored"]].sum()
    x = (a.samples / a.scored * 96).to_numpy(); v = (a.viol / a.scored).to_numpy()
    o = np.argsort(x)
    return x[o], v[o]


def viol_at(x, v, b):
    return np.nan if b < x.min() or b > x.max() else float(np.interp(np.log(b), np.log(x), v))


def budget_for(x, v, target):
    """smallest budget on the frontier reaching violation share <= target (v decreases with x)"""
    o = np.argsort(v)                                    # interpolate budget as a function of violation
    vs, xs = v[o], x[o]
    if target < vs.min() or target > vs.max():
        return np.nan
    return float(np.exp(np.interp(target, vs, np.log(xs))))


def main():
    r = pd.read_csv("results/rescoping/voi_sensing.csv", dtype={"site": str})
    out = []
    for variant in ("raw", "noise"):
        g = r[r.variant == variant]
        x0, v0 = curve(g[g.set == "F0"])
        for b in (24, 48):
            target = viol_at(x0, v0, b)
            for s in SETS:
                x, v = curve(g[g.set == s])
                need = budget_for(x, v, target)
                # per site: does this set need fewer wake-ups than F0 for F0's violation at budget b?
                wins = tot = 0
                for site, gs in g.groupby("site"):
                    xs0, vs0 = curve(gs[gs.set == "F0"]); t = viol_at(xs0, vs0, b)
                    xs, vs = curve(gs[gs.set == s]); nd = budget_for(xs, vs, t)
                    if np.isfinite(t) and np.isfinite(nd):
                        tot += 1; wins += nd < b
                out.append({"variant": variant, "F0_budget": b, "F0_viol": round(target, 4), "set": s,
                            "budget_needed": round(need, 1), "saving": round(1 - need / b, 3),
                            "sites_fewer": f"{wins}/{tot}"})
    d = pd.DataFrame(out)
    print(d.to_string(index=False))
    d.to_csv("results/rescoping/voi_summary.csv", index=False)


if __name__ == "__main__":
    main()
