"""Judge H8-H10 of docs/DESIGN_EVAL_PLAN.md Part 3 (rules written before implementation).
Reads results/design/sensitivity/<site>_{energy,picture}.csv; writes summary CSVs there.
Usage (from Paper2/): python -I src/design/analyse_sensitivity.py
"""
import glob

import numpy as np
import pandas as pd

D = "results/design/sensitivity"


def load(kind):
    return pd.concat((pd.read_csv(f, dtype={"site": str}) for f in sorted(glob.glob(f"{D}/*_{kind}.csv"))),
                     ignore_index=True)


def main():
    en, pic = load("energy"), load("picture")
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = set(elig[elig.status == "ok"].site)
    en, pic = en[en.site.isin(ok)], pic[pic.site.isin(ok)]
    print(f"sites: {en.site.nunique()}")

    # ---------------- H8 newest-first
    nf = pic[(pic.trace == "none") & (pic.strategy == "design_bounded_nf")]
    fifo = pic[(pic.trace == "none") & (pic.strategy == "design_bounded") & (pic.level == "L2")]
    h8a = nf.groupby(["radio", "param"]).within_tol.agg(["min", "median"])
    h8a["fifo_min"] = fifo.groupby(["radio", "param"]).within_tol.min()
    e = en[en.level.isin(["L2"]) & en.strategy.isin(["design_bounded", "design_bounded_nf"])]
    ep = e.pivot_table(index=["trace", "radio", "site"], columns="strategy", values="energy_j_per_day")
    ratio = ep["design_bounded_nf"] / ep["design_bounded"]
    h8a.to_csv(f"{D}/summary_H8_newest_first.csv")
    print("\nH8 picture on the no-outage link (newest-first; FIFO min for comparison)")
    print(h8a.round(4).to_string())
    print(f"H8 energy nf / FIFO over all trace x radio x site: min {ratio.min():.4f}, max {ratio.max():.4f}")
    h8_pass = bool((nf.within_tol >= 1.0 - 1e-12).all()) and bool(((ratio - 1).abs() <= 0.01).all())
    print("   all-trace picture (nf vs FIFO, medians):")
    pv = pic[(pic.level == "L2") & pic.strategy.isin(["design_bounded", "design_bounded_nf"])].pivot_table(
        index=["trace", "radio", "param", "site"], columns="strategy", values="within_tol")
    print(pv.groupby(level=[0, 1, 2]).median().round(4).to_string())

    # ---------------- H9 picture at each level
    rows = []
    for lv in ("L1", "L2", "L3"):
        a = pic[(pic.strategy == "arq_buffer") & (pic.level == lv)].set_index(["trace", "radio", "param", "site"]).within_tol
        d = pic[(pic.strategy == "design") & (pic.level == lv)].set_index(["trace", "radio", "param", "site"]).within_tol
        b = pic[(pic.strategy == "design_bounded") & (pic.level == lv)].set_index(["trace", "radio", "param", "site"]).within_tol
        df = pd.DataFrame({"arq": a, "design": d, "bounded": b})
        for (tr, rl, p), g in df.groupby(level=[0, 1, 2]):
            diff = (g.bounded - g.arq) * 100
            rows.append({"level": lv, "trace": tr, "radio": rl, "param": p, "within_arq": g.arq.median(),
                         "within_design": g.design.median(), "within_bounded": g.bounded.median(),
                         "bounded_minus_arq_pp": diff.median(), "pass": diff.median() >= -1.0})
    h9 = pd.DataFrame(rows); h9.to_csv(f"{D}/summary_H9_picture_levels.csv", index=False)
    print("\nH9 (picture vs per-reading ARQ at each level; medians over sites) - LoRaWAN SF7 shown; full table in CSV")
    print(h9[h9.radio == "LoRaWAN SF7"].round(3).to_string(index=False))

    # ---------------- H10 energy at each level
    rows = []
    ea = en[en.strategy == "arq_buffer"].set_index(["trace", "radio", "site"]).energy_j_per_day
    ed = en[en.strategy == "design"].set_index(["trace", "radio", "site"]).energy_j_per_day
    for lv in ("L1", "L2", "L3"):
        eb = en[(en.strategy == "design_bounded") & (en.level == lv)].set_index(["trace", "radio", "site"]).energy_j_per_day
        df = pd.DataFrame({"arq": ea, "design": ed, "bounded": eb})
        for (tr, rl), g in df.groupby(level=[0, 1]):
            r = g.bounded / g.arq
            rows.append({"level": lv, "trace": tr, "radio": rl, "E_arq": g.arq.median(), "E_design": g.design.median(),
                         "E_bounded": g.bounded.median(), "bounded_over_design": (g.bounded / g.design).median(),
                         "arq_over_bounded": (g.arq / g.bounded).median(), "sites_bounded_le_arq": (r <= 1 + 1e-9).mean(),
                         "pass": r.median() <= 1.0})
    h10 = pd.DataFrame(rows); h10.to_csv(f"{D}/summary_H10_energy_levels.csv", index=False)
    print("\nH10 (energy J/day at each level; medians over sites)")
    print(h10.round(3).to_string(index=False))

    print("\nVERDICTS")
    print(f"  H8 {'pass' if h8_pass else 'FAIL'} (nf 100% within tolerance on the no-outage link everywhere; energy within 1%)")
    for lv in ("L1", "L3"):
        print(f"  H9  at {lv}: {h9[h9.level == lv]['pass'].sum()}/{(h9.level == lv).sum()} param x trace x radio")
        print(f"  H10 at {lv}: {h10[h10.level == lv]['pass'].sum()}/{(h10.level == lv).sum()} trace x radio")


if __name__ == "__main__":
    main()
