"""Verdicts and secondary analyses for docs/CONFIRMATORY_PLAN.md, from src/confirm/run_confirm.py output.

The same script judges the development rerun (2023, salt 0) and the confirmatory run (2024, salt 2024),
so both are analysed identically. "Bounded" is the final design: bounded event-driven batching with
newest-first packing (design_bounded_nf); FIFO packing (design_bounded) is reported alongside, as in v0.1.

Primary rules (CONFIRMATORY_PLAN §5), each on the median site of every link x radio (12 combinations) or
link x radio x parameter (48):
  CH1  link up: Event alarm latency - ARQ+buffer latency <= 1 slot
  CH2  Event (event-averaged) / Batch 1 h <= 1.10 and ARQ+buffer / Event >= 1.3
  CH4  Event picture >= ARQ+buffer - 5 pp at L2 (expected to FAIL for DO and pH, as in development)
  CH5  Bounded picture >= ARQ+buffer - 1 pp at L2
  CH6  Bounded energy (event-averaged, L2) <= ARQ+buffer energy
  CH7  link up: Bounded alarm latency - Event alarm latency <= 1 slot
  CH8  no-outage link: Bounded within tolerance at every scored slot, for every site x parameter x radio (L2)
  CH9  CH5 at L1 and at L3 (series without events)
  CH10 CH6 at L1 and at L3 (series without events)
Secondary (no pass rule): site-bootstrap 95% CIs of the median-site statistics; all-event share known
within 1/6/24 h (M11); CH1/CH7 restricted to physically plausible events (§6).
Usage (from Paper2/): python -I src/confirm/analyse_confirm.py <run dir> <eligibility csv> <out prefix>
"""
import glob
import json
import sys

import numpy as np
import pandas as pd

LEVELS = ("L1", "L2", "L3")
B_BOOT = 10_000
PLAUSIBLE = {"T": (-0.5, 40.0), "EC": (0.0, np.inf), "pH": (4.0, 11.0), "DO": (0.0, 250.0)}   # §6


def load(d, kind):
    return pd.concat((pd.read_csv(f, dtype={"site": str}) for f in sorted(glob.glob(f"{d}/*_{kind}.csv"))),
                     ignore_index=True)


def boot_ci(per_site, stat=np.median, seed=0):
    """95% percentile CI of stat over sites, resampling sites with replacement."""
    v = np.asarray(per_site, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    b = np.array([stat(v[rng.integers(0, len(v), len(v))]) for _ in range(B_BOOT)])
    return tuple(np.percentile(b, [2.5, 97.5]))


def plausible(ev):
    lo = ev.param.map(lambda p: PLAUSIBLE[p][0]); hi = ev.param.map(lambda p: PLAUSIBLE[p][1])
    return (ev.inj_min >= lo) & (ev.inj_max <= hi)


def latency_table(ev, step_h):
    up = ev[ev.link_up_at_onset & ev.node_detected & np.isfinite(ev.latency_h)]
    return up.groupby(["trace", "radio", "strategy", "site"]).latency_h.median().unstack("strategy"), step_h


def main(run_dir, elig_csv, out):
    ev, en, pic = load(run_dir, "events"), load(run_dir, "energy"), load(run_dir, "picture")
    elig = pd.read_csv(elig_csv, dtype={"site": str})
    ok = set(elig[elig.status == "ok"].site)
    ev, en, pic = ev[ev.site.isin(ok)], en[en.site.isin(ok)], pic[pic.site.isin(ok)]
    step_h = elig.set_index("site").step_min / 60
    res = {"sites": int(ev.site.nunique()), "verdicts": {}}
    print(f"sites: {res['sites']}")

    # ---------------- latency (CH1, CH7), all events and plausible events only
    def lat_rules(evs, tag):
        med = evs[evs.link_up_at_onset & evs.node_detected & np.isfinite(evs.latency_h)] \
            .groupby(["trace", "radio", "strategy", "site"]).latency_h.median().unstack("strategy")
        rows = []
        for (tr, rl), g in med.groupby(level=[0, 1]):
            g = g.droplevel([0, 1]); st = step_h.reindex(g.index)
            d1 = (g["design"] - g["arq_buffer"]) / st
            d7 = (g["design_bounded_nf"] - g["design"]) / st
            d7f = (g["design_bounded"] - g["design"]) / st
            rows.append({"set": tag, "trace": tr, "radio": rl, "lat_arq_h": g["arq_buffer"].median(),
                         "lat_batch_h": g["batch1h"].median(), "lat_event_h": g["design"].median(),
                         "lat_bounded_h": g["design_bounded_nf"].median(),
                         "event_minus_arq_slots": d1.median(), "event_minus_arq_slots_ci": boot_ci(d1),
                         "bounded_minus_event_slots": d7.median(), "bounded_minus_event_slots_ci": boot_ci(d7),
                         "fifo_bounded_minus_event_slots": d7f.median(),
                         "batch_minus_event_h": (g["batch1h"] - g["design"]).median(),
                         "CH1": d1.median() <= 1.0, "CH7": d7.median() <= 1.0})
        return pd.DataFrame(rows)
    lat = lat_rules(ev, "all")
    pl = plausible(ev)
    lat_pl = lat_rules(ev[pl], "plausible")
    pd.concat([lat, lat_pl]).to_csv(f"{out}_latency.csv", index=False)
    res["plausible_event_share"] = float(pl[(ev.strategy == "design")].mean())

    # ---------------- energy (CH2, CH6 at L2 with events; CH10 at L1/L3 clean)
    clean = en[en.setting == "clean"]
    ec = clean[clean.level.isin(["-"])].pivot_table(index=["trace", "radio", "site"], columns="strategy",
                                                     values="energy_j_per_day")
    evm = en[en.setting != "clean"].groupby(["trace", "radio", "site", "strategy"]).energy_j_per_day.mean().unstack()
    rows = []
    for (tr, rl), g in ec.groupby(level=[0, 1]):
        e = evm.loc[(tr, rl)]
        g = g.droplevel([0, 1])
        r_eb = e["design"] / g["batch1h"]; r_ae = g["arq_buffer"] / e["design"]
        r_ba = e["design_bounded_nf"] / g["arq_buffer"]; r_bf = e["design_bounded"] / g["arq_buffer"]
        rows.append({"trace": tr, "radio": rl, "E_unconf": g["unconf"].median(), "E_arq": g["arq_buffer"].median(),
                     "E_batch": g["batch1h"].median(), "E_event": e["design"].median(),
                     "E_bounded": e["design_bounded_nf"].median(), "E_bounded_fifo": e["design_bounded"].median(),
                     "event_over_batch": r_eb.median(), "event_over_batch_ci": boot_ci(r_eb),
                     "arq_over_event": r_ae.median(), "arq_over_event_ci": boot_ci(r_ae),
                     "bounded_over_batch": (e["design_bounded_nf"] / g["batch1h"]).median(),
                     "arq_over_bounded": (1 / r_ba).median(), "arq_over_bounded_ci": boot_ci(1 / r_ba),
                     "bounded_over_arq_fifo": r_bf.median(),
                     "CH2": (r_eb.median() <= 1.10) and (r_ae.median() >= 1.3), "CH6": r_ba.median() <= 1.0})
    energy = pd.DataFrame(rows); energy.to_csv(f"{out}_energy.csv", index=False)

    rows = []
    ea = clean[clean.strategy == "arq_buffer"].set_index(["trace", "radio", "site"]).energy_j_per_day
    for lv in LEVELS:
        eb = clean[(clean.strategy == "design_bounded_nf") & (clean.level == lv)].set_index(["trace", "radio", "site"]).energy_j_per_day
        ebf = clean[(clean.strategy == "design_bounded") & (clean.level == lv)].set_index(["trace", "radio", "site"]).energy_j_per_day
        df = pd.DataFrame({"arq": ea, "b": eb, "bf": ebf})
        for (tr, rl), g in df.groupby(level=[0, 1]):
            r = g.b / g.arq
            rows.append({"level": lv, "trace": tr, "radio": rl, "E_arq": g.arq.median(), "E_bounded": g.b.median(),
                         "arq_over_bounded": (g.arq / g.b).median(), "arq_over_bounded_ci": boot_ci(g.arq / g.b),
                         "arq_over_bounded_fifo": (g.arq / g.bf).median(), "CH10": r.median() <= 1.0})
    elev = pd.DataFrame(rows); elev.to_csv(f"{out}_energy_levels.csv", index=False)

    # ---------------- picture (CH4, CH5 at L2; CH9 at L1/L3; CH8)
    rows = []
    for lv in LEVELS:
        p = pic[pic.level == lv]
        a = p[p.strategy == "arq_buffer"].set_index(["trace", "radio", "param", "site"]).within_tol
        d = p[p.strategy == "design"].set_index(["trace", "radio", "param", "site"]).within_tol
        b = p[p.strategy == "design_bounded_nf"].set_index(["trace", "radio", "param", "site"]).within_tol
        bf = p[p.strategy == "design_bounded"].set_index(["trace", "radio", "param", "site"]).within_tol
        u = p[p.strategy == "unconf"].set_index(["trace", "radio", "param", "site"]).within_tol
        bt = p[p.strategy == "batch1h"].set_index(["trace", "radio", "param", "site"]).within_tol
        df = pd.DataFrame({"arq": a, "event": d, "b": b, "bf": bf, "unconf": u, "batch": bt})
        for (tr, rl, pa), g in df.groupby(level=[0, 1, 2]):
            d4 = (g.event - g.arq) * 100; d5 = (g.b - g.arq) * 100
            rows.append({"level": lv, "trace": tr, "radio": rl, "param": pa, "within_unconf": g.unconf.median(),
                         "within_arq": g.arq.median(), "within_batch": g.batch.median(), "within_event": g.event.median(),
                         "within_bounded": g.b.median(), "within_bounded_fifo": g.bf.median(),
                         "event_minus_arq_pp": d4.median(), "bounded_minus_arq_pp": d5.median(),
                         "bounded_minus_arq_pp_ci": boot_ci(d5),
                         "CH4": d4.median() >= -5.0, "CH5": d5.median() >= -1.0})
    picture = pd.DataFrame(rows); picture.to_csv(f"{out}_picture.csv", index=False)
    nf_none = pic[(pic.trace == "none") & (pic.strategy == "design_bounded_nf") & (pic.level == "L2")]
    ch8 = bool((nf_none.within_tol >= 1.0 - 1e-12).all())
    res["CH8_min_within"] = float(nf_none.within_tol.min())

    # ---------------- M11: all injected events known within X h (detection x delivery), pooled
    rows = []
    for (tr, rl, k), g in ev.groupby(["trace", "radio", "strategy"]):
        rows.append({"trace": tr, "radio": rl, "strategy": k, "n": len(g),
                     **{f"known_{x}h": float((g.latency_h <= x).mean()) for x in (1, 6, 24)},
                     "known_ever": float(np.isfinite(g.latency_h).mean())})
    pd.DataFrame(rows).to_csv(f"{out}_known_within.csv", index=False)

    L2 = picture[picture.level == "L2"]
    v = res["verdicts"]
    v["CH1"] = f"{int(lat.CH1.sum())}/{len(lat)}"
    v["CH2"] = f"{int(energy.CH2.sum())}/{len(energy)}"
    v["CH4"] = f"{int(L2.CH4.sum())}/{len(L2)}"
    v["CH5"] = f"{int(L2.CH5.sum())}/{len(L2)}"
    v["CH6"] = f"{int(energy.CH6.sum())}/{len(energy)}"
    v["CH7"] = f"{int(lat.CH7.sum())}/{len(lat)}"
    v["CH8"] = "pass" if ch8 else "FAIL"
    for lv in ("L1", "L3"):
        p = picture[picture.level == lv]; e = elev[elev.level == lv]
        v[f"CH9_{lv}"] = f"{int(p.CH5.sum())}/{len(p)}"
        v[f"CH10_{lv}"] = f"{int(e.CH10.sum())}/{len(e)}"
    v["CH1_plausible"] = f"{int(lat_pl.CH1.sum())}/{len(lat_pl)}"
    v["CH7_plausible"] = f"{int(lat_pl.CH7.sum())}/{len(lat_pl)}"
    with open(f"{out}_verdicts.json", "w") as f:
        json.dump(res, f, indent=2, default=str)
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:4])
