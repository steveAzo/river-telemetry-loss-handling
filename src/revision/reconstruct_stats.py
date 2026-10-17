"""Review E9/M9 (dependence between site pairs) and M13 (spatial structure of the reconstruction test).

Input: results/revision/chains/chain_*.csv (chain_outage.py with the D5 inclusive tolerance).
E9: the ordered pairs are not independent: a site appears in several pairs, and pairs sit inside 9 river chains.
    Every statistic used in the text is given a chain-blocked bootstrap 95% CI: resample the chains with
    replacement, then the ordered pairs within each drawn chain with replacement (B = 5,000).
M13: per ordered pair, the straight-line distance, the drainage areas, whether the neighbour is upstream or
    downstream of the target, the selected lag and the 6-h-change correlation, per parameter.
    Order along the river: by NWIS drainage area; three sites without one are placed by position (Klamath flows
    west from Upper Klamath Lake: Miller Island -> above Keno Dam -> at Keno; Tualatin RM 24.5 lies between
    Hillsboro and Oswego Dam).
Usage (from Paper2/): python -I src/revision/reconstruct_stats.py results/revision/reconstruct
"""
import glob
import sys

import numpy as np
import pandas as pd

B = 5000
ORDER_FILL = {"420853121505500": ("klamath", 0), "11509370": ("klamath", 1), "11509500": ("klamath", 2),
              "14203500": ("tualatin", 0), "14206241": ("tualatin", 1), "14206694": ("tualatin", 2),
              "14207200": ("tualatin", 3)}


def load_pairs():
    d = pd.concat(pd.read_csv(f, dtype={"target": str, "neighbour": str})
                  for f in sorted(glob.glob("results/revision/chains/chain_*.csv")))
    d["best_own_rt"] = d[["med_persist", "med_diel"]].min(axis=1)
    d["best_nb_rt"] = d[["med_nb_delta", "med_diel_nb"]].min(axis=1)
    d["nb_wins_rt"] = d.best_nb_rt < d.best_own_rt
    d["nb_gain_rt"] = 1 - d.best_nb_rt / d.best_own_rt
    d["nb_wins_bf"] = d.med_interp_nb < d.med_interp
    d["nb_gain_bf"] = 1 - d.med_interp_nb / d.med_interp
    d["diel_beats_persist"] = d.med_diel < d.med_persist
    d["naive_nb_wins"] = d.best_nb_rt < d.med_persist
    oks = [c for c in d.columns if c.startswith("ok_")]
    d["ok_best_all"] = d[oks].max(axis=1)
    d["ok_best_own_rt"] = d[["ok_persist", "ok_diel"]].max(axis=1)
    return d


STATS = {  # name -> (column, aggregator)
    "nb_wins_rt": ("nb_wins_rt", "mean"), "nb_gain_rt": ("nb_gain_rt", "median"),
    "nb_wins_bf": ("nb_wins_bf", "mean"), "nb_gain_bf": ("nb_gain_bf", "median"),
    "diel_beats_persist": ("diel_beats_persist", "mean"), "naive_nb_wins": ("naive_nb_wins", "mean"),
    "ok_best_all": ("ok_best_all", "median"), "ok_best_own_rt": ("ok_best_own_rt", "median"),
    "med_persist": ("med_persist", "median"), "med_diel": ("med_diel", "median"), "best_nb_rt": ("best_nb_rt", "median"),
}


def agg(x, how):
    x = x[np.isfinite(x.astype(float))]
    return float(x.mean()) if how == "mean" else float(np.median(x))


def blocked_ci(g, col, how, rng):
    chains = g.chain.unique()
    by = {c: g[g.chain == c][col].to_numpy() for c in chains}
    vals = []
    for _ in range(B):
        pick = rng.choice(chains, len(chains), replace=True)
        parts = [by[c][rng.integers(0, len(by[c]), len(by[c]))] for c in pick]
        vals.append(agg(pd.Series(np.concatenate(parts)), how))
    return np.percentile(vals, [2.5, 97.5])


def main(out):
    d = load_pairs()
    rng = np.random.default_rng(20261017)
    rows = []
    for (p, H), g in d.groupby(["param", "H_h"]):
        if H not in (1, 24):
            continue
        g = g.copy()
        if p == "pH":                              # relative gain undefined where the own error is exactly zero
            g.loc[g.best_own_rt == 0, "nb_gain_rt"] = np.nan
        for name, (col, how) in STATS.items():
            lo, hi = blocked_ci(g.dropna(subset=[col]), col, how, rng)
            rows.append({"param": p, "H_h": H, "stat": name, "value": agg(g[col].dropna(), how), "ci_lo": lo, "ci_hi": hi,
                         "pairs": int(g[col].notna().sum()), "chains": g.chain.nunique()})
    # pooled over parameters, as in the text: best-of-all within tolerance at 24 h, best own-data at 1 h
    for H, col in ((24, "ok_best_all"), (1, "ok_best_own_rt")):
        g = d[d.H_h == H]
        lo, hi = blocked_ci(g, col, "median", rng)
        rows.append({"param": "all", "H_h": H, "stat": col, "value": agg(g[col], "median"), "ci_lo": lo, "ci_hi": hi,
                     "pairs": len(g), "chains": g.chain.nunique()})
    s = pd.DataFrame(rows)
    s.to_csv(f"{out}_bootstrap.csv", index=False, float_format="%.6g")
    print(s.round(3).to_string(index=False))

    # ---------------- M13: spatial structure per ordered pair
    meta = pd.read_csv("results/revision/chain_sites_usgs.rdb", sep="\t", comment="#", dtype=str).iloc[1:]
    meta = meta.set_index("site_no")
    lat = meta.dec_lat_va.astype(float); lon = meta.dec_long_va.astype(float)
    area = pd.to_numeric(meta.drain_area_va, errors="coerce")

    def order(site):
        if site in ORDER_FILL:
            return ORDER_FILL[site][1]
        return area[site]

    def km(a, b):
        p1, p2 = np.radians(lat[a]), np.radians(lat[b])
        dl = np.radians(lon[b] - lon[a])
        h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
        return 6371 * 2 * np.arcsin(np.sqrt(h))
    sp = d[d.H_h == 24][["chain", "target", "neighbour", "param", "lag_h", "r6h", "slope"]].copy()
    sp["distance_km"] = [km(a, b) for a, b in zip(sp.target, sp.neighbour)]
    sp["area_target_mi2"] = sp.target.map(area); sp["area_neighbour_mi2"] = sp.neighbour.map(area)
    sp["neighbour_is"] = np.where([order(n) < order(t) for t, n in zip(sp.target, sp.neighbour)], "upstream", "downstream")
    sp.to_csv(f"{out}_pairs_spatial.csv", index=False, float_format="%.6g")
    print("\nM13: per parameter, by neighbour position (median over pairs)")
    print(sp.groupby(["param", "neighbour_is"]).agg(pairs=("lag_h", "size"), dist_km=("distance_km", "median"),
                                                    lag_h=("lag_h", "median"), lag_pos=("lag_h", lambda v: np.mean(v > 0)),
                                                    r6h=("r6h", "median")).round(2).to_string())
    print(f"\ndistance range {sp.distance_km.min():.1f}-{sp.distance_km.max():.1f} km, median {sp.distance_km.median():.1f}")


if __name__ == "__main__":
    main(sys.argv[1])
