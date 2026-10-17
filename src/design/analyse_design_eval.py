"""Judge H1-H4 of docs/DESIGN_EVAL_PLAN.md (rules written before the all-site results were seen).

Reads results/design/<site>_{events,energy,picture}.csv; writes results/design/summary_*.csv and
prints the verdicts. Medians are over sites; Wilcoxon signed-rank across sites for directional claims.
Usage (from Paper2/): python -I src/design/analyse_design_eval.py
"""
import glob

import numpy as np
import pandas as pd
from scipy import stats

D = "results/design"
TRACES = ["none", "UVA", "Weija", "InWaterSense"]


def load(kind):
    return pd.concat((pd.read_csv(f, dtype={"site": str}) for f in sorted(glob.glob(f"{D}/*_{kind}.csv"))),
                     ignore_index=True)


def wilcoxon(a, b):
    d = np.asarray(a) - np.asarray(b)
    d = d[np.isfinite(d)]
    if len(d) < 6 or np.all(d == 0):
        return np.nan
    return stats.wilcoxon(d).pvalue


def main():
    ev, en, pic = load("events"), load("energy"), load("picture")
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = set(elig[elig.status == "ok"].site)                  # plan rule: >= 50 % of the YEAR (deviation D2)
    ev, en, pic = ev[ev.site.isin(ok)], en[en.site.isin(ok)], pic[pic.site.isin(ok)]
    step_h = elig.set_index("site").step_min / 60
    ev["step_h"] = ev.site.map(step_h)
    print(f"sites: {ev.site.nunique()}; injected events per site x setting: "
          f"{ev.groupby(['site', 'setting']).size().div(ev.trace.nunique() * ev.radio.nunique() * ev.strategy.nunique()).median():.0f}")

    # ---------------- detection (detector only, identical for complete strategies)
    det = ev[(ev.trace == "none") & (ev.radio == ev.radio.iloc[0]) & (ev.strategy == "design")]
    print("\nnode detector: share of injected events detected (median over sites)")
    print(det.groupby(["setting", "site"]).node_detected.mean().groupby("setting").median().round(3).to_string())

    # ---------------- H1: link up at onset, detected events
    up = ev[ev.link_up_at_onset & ev.node_detected & np.isfinite(ev.latency_h)]
    med = up.groupby(["trace", "radio", "strategy", "site"]).latency_h.median().unstack("strategy")
    rows = []
    for (tr, rl), g in med.groupby(level=[0, 1]):
        g = g.droplevel([0, 1])
        steps = step_h.reindex(g.index)
        diff_slots = (g["design"] - g["arq_buffer"]) / steps
        rows.append({"trace": tr, "radio": rl,
                     "lat_unconf_h": g["unconf"].median(), "lat_arq_buffer_h": g["arq_buffer"].median(),
                     "lat_batch1h_h": g["batch1h"].median(), "lat_design_h": g["design"].median(),
                     "design_minus_arq_slots_median": diff_slots.median(),
                     "H1_pass": diff_slots.median() <= 1.0,
                     "batch_minus_design_h": (g["batch1h"] - g["design"]).median(),
                     "p_batch_vs_design": wilcoxon(g["batch1h"], g["design"])})
    h1 = pd.DataFrame(rows); h1.to_csv(f"{D}/summary_H1_latency_up.csv", index=False)
    print("\nH1 (link up at onset; median over sites of per-site median latency, hours)")
    print(h1.round(3).to_string(index=False))

    # ---------------- H2: energy
    e_clean = en[en.setting == "clean"].pivot_table(index=["trace", "radio", "site"], columns="strategy",
                                                    values="energy_j_per_day")
    e_ev = en[(en.strategy == "design") & (en.setting != "clean")].groupby(["trace", "radio", "site"]).energy_j_per_day.mean()
    e_clean["design_with_events"] = e_ev
    rows = []
    for (tr, rl), g in e_clean.groupby(level=[0, 1]):
        r_batch = (g["design_with_events"] / g["batch1h"]).median()
        r_arq = (g["arq_buffer"] / g["design_with_events"]).median()
        rows.append({"trace": tr, "radio": rl, "E_unconf": g["unconf"].median(), "E_arq_buffer": g["arq_buffer"].median(),
                     "E_batch1h": g["batch1h"].median(), "E_design_clean": g["design"].median(),
                     "E_design_events": g["design_with_events"].median(),
                     "design_over_batch": r_batch, "arq_over_design": r_arq,
                     "H2_pass": (r_batch <= 1.10) and (r_arq >= 1.3)})
    h2 = pd.DataFrame(rows); h2.to_csv(f"{D}/summary_H2_energy.csv", index=False)
    print("\nH2 (energy, J/day, medians over sites)")
    print(h2.round(3).to_string(index=False))

    # ---------------- H3: onset during an outage
    out = ev[~ev.link_up_at_onset & ev.node_detected]
    if len(out):
        rows = []
        for (tr, rl, k), g in out.groupby(["trace", "radio", "strategy"]):
            rows.append({"trace": tr, "radio": rl, "strategy": k, "n_events": len(g),
                         "known_ever": np.isfinite(g.latency_h).mean(),
                         "known_24h": (g.latency_h <= 24).mean(),
                         "latency_median_h": np.median(g.latency_h[np.isfinite(g.latency_h)]) if np.isfinite(g.latency_h).any() else np.nan})
        h3 = pd.DataFrame(rows); h3.to_csv(f"{D}/summary_H3_outage_onset.csv", index=False)
        print("\nH3 (detected events whose onset fell in an outage; pooled over sites)")
        print(h3.round(3).to_string(index=False))

    # ---------------- all events: known within X hours of onset (detection x delivery)
    rows = []
    for (tr, rl, k), g in ev.groupby(["trace", "radio", "strategy"]):
        rows.append({"trace": tr, "radio": rl, "strategy": k,
                     **{f"known_{x}h": (g.latency_h <= x).mean() for x in (1, 3, 24)},
                     "known_ever": np.isfinite(g.latency_h).mean()})
    kn = pd.DataFrame(rows); kn.to_csv(f"{D}/summary_known_within.csv", index=False)
    print("\nAll injected events: share the server knows within X h of onset (pooled)")
    print(kn.round(3).to_string(index=False))

    # ---------------- H4: real-time picture
    pv = pic.pivot_table(index=["trace", "radio", "param", "site"], columns="strategy", values="within_tol")
    rows = []
    for (tr, rl, p), g in pv.groupby(level=[0, 1, 2]):
        d = (g["design"] - g["arq_buffer"]) * 100
        rows.append({"trace": tr, "radio": rl, "param": p, "within_unconf": g["unconf"].median(),
                     "within_arq_buffer": g["arq_buffer"].median(), "within_batch1h": g["batch1h"].median(),
                     "within_design": g["design"].median(), "design_minus_arq_pp": d.median(),
                     "H4_pass": d.median() >= -5.0})
    h4 = pd.DataFrame(rows); h4.to_csv(f"{D}/summary_H4_picture.csv", index=False)
    print("\nH4 (share of time the server picture is within L2 tolerance; medians over sites)")
    print(h4.round(3).to_string(index=False))

    # ================= Part 2: bounded-error trigger (H5-H7, rules in DESIGN_EVAL_PLAN Part 2)
    # H5 picture: design_bounded >= arq_buffer - 1 pp, every param x trace x radio
    rows = []
    for (tr, rl, p), g in pv.groupby(level=[0, 1, 2]):
        d = (g["design_bounded"] - g["arq_buffer"]) * 100
        rows.append({"trace": tr, "radio": rl, "param": p, "within_arq_buffer": g["arq_buffer"].median(),
                     "within_design": g["design"].median(), "within_design_bounded": g["design_bounded"].median(),
                     "bounded_minus_arq_pp": d.median(), "H5_pass": d.median() >= -1.0})
    h5 = pd.DataFrame(rows); h5.to_csv(f"{D}/summary_H5_picture_bounded.csv", index=False)
    print("\nH5 (bounded design picture vs per-reading ARQ; medians over sites)")
    print(h5.round(3).to_string(index=False))

    # H6 energy: design_bounded (mean over event settings) <= arq_buffer, every trace x radio
    eb = en[(en.strategy == "design_bounded") & (en.setting != "clean")].groupby(["trace", "radio", "site"]).energy_j_per_day.mean()
    e_clean["design_bounded_events"] = eb
    rows = []
    for (tr, rl), g in e_clean.groupby(level=[0, 1]):
        rows.append({"trace": tr, "radio": rl, "E_arq_buffer": g["arq_buffer"].median(), "E_batch1h": g["batch1h"].median(),
                     "E_design": g["design_with_events"].median(), "E_design_bounded": g["design_bounded_events"].median(),
                     "bounded_over_batch": (g["design_bounded_events"] / g["batch1h"]).median(),
                     "arq_over_bounded": (g["arq_buffer"] / g["design_bounded_events"]).median(),
                     "sites_bounded_le_arq": (g["design_bounded_events"] <= g["arq_buffer"]).mean(),
                     "H6_pass": (g["design_bounded_events"] / g["arq_buffer"]).median() <= 1.0})
    h6 = pd.DataFrame(rows); h6.to_csv(f"{D}/summary_H6_energy_bounded.csv", index=False)
    print("\nH6 (energy J/day, medians over sites; bounded design with events)")
    print(h6.round(3).to_string(index=False))

    # H7 alarm latency (link up): design_bounded - design <= 1 slot (median site)
    rows = []
    for (tr, rl), g in med.groupby(level=[0, 1]):
        g = g.droplevel([0, 1])
        dslots = (g["design_bounded"] - g["design"]) / step_h.reindex(g.index)
        rows.append({"trace": tr, "radio": rl, "lat_design_h": g["design"].median(),
                     "lat_design_bounded_h": g["design_bounded"].median(),
                     "bounded_minus_design_slots": dslots.median(), "H7_pass": dslots.median() <= 1.0})
    h7 = pd.DataFrame(rows); h7.to_csv(f"{D}/summary_H7_latency_bounded.csv", index=False)
    print("\nH7 (alarm latency, link up)")
    print(h7.round(3).to_string(index=False))

    print("\nVERDICTS")
    print(f"  H1 pass in {h1.H1_pass.sum()}/{len(h1)} trace x radio")
    print(f"  H2 pass in {h2.H2_pass.sum()}/{len(h2)} trace x radio")
    print(f"  H4 pass in {h4.H4_pass.sum()}/{len(h4)} trace x radio x param")
    print(f"  H5 pass in {h5.H5_pass.sum()}/{len(h5)} trace x radio x param")
    print(f"  H6 pass in {h6.H6_pass.sum()}/{len(h6)} trace x radio")
    print(f"  H7 pass in {h7.H7_pass.sum()}/{len(h7)} trace x radio")


if __name__ == "__main__":
    main()
