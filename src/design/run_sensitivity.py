"""Part 3 of docs/DESIGN_EVAL_PLAN.md: newest-first packing (H8) and tolerance sensitivity (H9, H10).

Clean series only (no injected events), same sites, links, seeds and radios as run_design_eval.py.
Strategies: arq_buffer, design, design_bounded at L1 / L2 / L3 (FIFO packing), design_bounded_nf at L2.
Pictures: arq_buffer and design scored at L1, L2, L3; each bounded variant at its own level.
Consistency check: design_bounded at L2 must reproduce run_design_eval.py's clean energy exactly.
Outputs: results/design/sensitivity/<site>_{energy,picture}.csv (resumable).
Usage (from Paper2/): python -I src/design/run_sensitivity.py [site ...]
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, "src/design")
from design.sitedata import (P_RADIO, PARAMS, load_records, load_site, make_trigger, map_link,  # noqa: E402
                             within_tol, run_detector, server_picture, train_hours)
from energy.loss_handling import simulate, summary  # noqa: E402
from run_design_eval import BATTERY, RADIOS, floor_j_per_day, radio  # noqa: E402

OUT = Path("results/design/sensitivity")
# Paper 1 LEVELS (src/sim/run_phase2.py); EC as a share of the whole-record median (Part 3 note)
LEVELS = {"L1": {"T": 0.1, "DO": 1.0, "pH": 0.05, "EC": 0.01},
          "L2": {"T": 0.2, "DO": 2.0, "pH": 0.1, "EC": 0.02},
          "L3": {"T": 0.5, "DO": 5.0, "pH": 0.2, "EC": 0.05}}


def tol_vec(st, lvl):
    ec_med = np.nanmedian(st.Xg[:, PARAMS.index("EC")])
    return np.array([LEVELS[lvl][p] * (ec_med if p == "EC" else 1.0) for p in PARAMS])


def evaluate_site(site_id, seed, recs):
    st = load_site(site_id)
    ds, n, step = st.ds, len(st.grid_t), st.step_s
    spd = int(round(86400 / step)); M = max(1, int(round(3600 / step))); cap = max(1, int(round(6 * 3600 / step)))
    has_g = np.isfinite(st.Xg).all(axis=1)
    al_clean = run_detector(ds, ds.X, st.res, train_hours(ds))
    urgent = np.zeros(n, bool); urgent[st.cyc2grid[al_clean.any(axis=1)]] = True
    tols = {lv: tol_vec(st, lv) for lv in LEVELS}
    # links exactly as in run_design_eval.py (same rng, same order)
    rng = np.random.default_rng(seed)
    links = {"none": np.ones(n, bool)}
    for k, rec in recs.items():
        links[k] = map_link(rec, st.grid_t, float(rng.uniform(0, len(rec[2]) * rec[1])))
    scored = st.test_g & has_g
    en_rows, pic_rows = [], []
    for tr, link in links.items():
        kw = dict(slot_s=step, p_radio=P_RADIO[tr], seed=seed)
        for rl in RADIOS:
            r = radio(rl)
            floor = floor_j_per_day(r, step)
            base = dict(M_check=M, probe_cap=cap, urgent=urgent, **kw)
            runs = {("arq_buffer", None): simulate(link, r, "arq_buffer", probe_cap=cap, **kw),
                    ("design", None): simulate(link, r, "batch_events", **base)}
            for lv in LEVELS:
                runs[("design_bounded", lv)] = simulate(link, r, "batch_events", trigger=make_trigger(st.Xg, tols[lv], spd, step), **base)
            runs[("design_bounded_nf", "L2")] = simulate(link, r, "batch_events", trigger=make_trigger(st.Xg, tols["L2"], spd, step),
                                                         newest_first=True, valid=has_g, **base)
            for (k, lv), v in runs.items():
                s_ = summary(v, n, step)
                en_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k, "level": lv or "-",
                                "energy_j_per_day": s_["energy_j_per_day"],
                                "lifetime_y": BATTERY / (floor + s_["energy_j_per_day"]) / 365})
                arr = np.where(has_g, st.grid_t + v.arrival_delay_s, np.inf)
                for lv_score in ([lv] if lv else list(LEVELS)):
                    for j, p in enumerate(PARAMS):
                        est = server_picture(st.Xg[:, j], arr, st.grid_t, spd, scored)
                        err = np.abs(est - st.Xg[scored, j]); ok = np.isfinite(err)
                        pic_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k, "level": lv_score,
                                         "param": p, "within_tol": np.mean(within_tol(err[ok], tols[lv_score][j]))})
    return pd.DataFrame(en_rows), pd.DataFrame(pic_rows)


def main(sites=None):
    OUT.mkdir(parents=True, exist_ok=True)
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    elig = elig[elig.status == "ok"]
    recs = load_records()
    for sid in elig.site:
        if sites and sid not in sites:
            continue
        if all((OUT / f"{sid}_{k}.csv").exists() for k in ("energy", "picture")):
            print(f"skip {sid}", flush=True); continue
        t0 = time.time()
        en, pic = evaluate_site(sid, int(sid) % (2 ** 31 - 1), recs)
        en.to_csv(OUT / f"{sid}_energy.csv", index=False, float_format="%.6g")
        pic.to_csv(OUT / f"{sid}_picture.csv", index=False, float_format="%.6g")
        print(f"{sid} done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
