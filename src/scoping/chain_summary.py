"""Summarise chain_outage.py results: per parameter and outage length, the median (over ordered site
pairs) of each method's median max-error, and how often the neighbour beats the best own-data method.
Usage: python -I src/scoping/chain_summary.py results/scoping/chain_*.csv
"""
import sys, pandas as pd
d = pd.concat(pd.read_csv(f, dtype={"target": str, "neighbour": str}) for f in sys.argv[1:])
d["best_own_rt"] = d[["med_persist", "med_diel"]].min(axis=1)
d["best_nb_rt"] = d[["med_nb_delta", "med_diel_nb"]].min(axis=1)
d["nb_wins_rt"] = d.best_nb_rt < d.best_own_rt
d["nb_gain_rt"] = 1 - d.best_nb_rt / d.best_own_rt
d["nb_wins_bf"] = d.med_interp_nb < d.med_interp
d["nb_gain_bf"] = 1 - d.med_interp_nb / d.med_interp
pd.set_option("display.width", 250)
g = d.groupby(["param", "H_h"]).agg(pairs=("n", "size"),
    persist=("med_persist", "median"), diel=("med_diel", "median"), nb_delta=("med_nb_delta", "median"), diel_nb=("med_diel_nb", "median"),
    nb_wins_rt=("nb_wins_rt", "mean"), nb_gain_rt=("nb_gain_rt", "median"),
    interp=("med_interp", "median"), interp_nb=("med_interp_nb", "median"),
    nb_wins_bf=("nb_wins_bf", "mean"), nb_gain_bf=("nb_gain_bf", "median"),
    ok_best_rt=("ok_diel", "median"), ok_diel_nb=("ok_diel_nb", "median"), ok_interp=("ok_interp", "median"))
print(g.round(3).to_string())
print("\nlags / r6h (median over pairs):"); print(d.groupby(["chain","param"])[["lag_h", "r6h", "slope"]].median().round(2).to_string())
