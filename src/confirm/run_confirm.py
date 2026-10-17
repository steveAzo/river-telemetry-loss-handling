"""Confirmatory run of the frozen design on held-out data (docs/CONFIRMATORY_PLAN.md).

Same functions, parameters and rules as the development runs (src/design/run_design_eval.py and
run_sensitivity.py); only the data root, the eligibility file, the seed salt and the output directory change.
In addition to the development strategies it runs the FINAL design, bounded event-driven batching with
newest-first packing (design_bounded_nf, after the D4 fix), with injected events, and at L1/L2/L3.

Per site (one set of files in <out>/):
  <site>_events.csv   one row per injected event x link x radio x strategy
  <site>_energy.csv   one row per link x radio x strategy x setting (x level for the bounded variants)
  <site>_picture.csv  one row per link x radio x strategy x level x parameter (series without events)
Seed per site: (int(site ID) + salt) mod (2^31 - 1). Development: salt 0. Confirmatory: salt 2024.
Usage (from Paper2/): python -I src/confirm/run_confirm.py <clean dir> <eligibility csv> <out dir> <salt> [site ...]
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, "src/design")
from design.inject import inject, noise_scale  # noqa: E402
from design.sitedata import (P_RADIO, PARAMS, load_records, load_site, make_trigger, map_link,  # noqa: E402
                             within_tol, run_detector, run_detector_on_subset, server_picture, train_hours)
from energy.loss_handling import simulate, summary  # noqa: E402
from run_design_eval import BATTERY, DUR_MIN, RADIOS, SETTINGS, floor_j_per_day, radio  # noqa: E402
from run_sensitivity import LEVELS, tol_vec  # noqa: E402

BOUNDED = ("design_bounded", "design_bounded_nf")


def site_seed(site_id, salt):
    return (int(site_id) + int(salt)) % (2 ** 31 - 1)


def evaluate_site(site_id, seed, recs, root):
    st = load_site(site_id, root=root)
    ds, n, step = st.ds, len(st.grid_t), st.step_s
    spd = int(round(86400 / step)); M = max(1, int(round(3600 / step))); cap = max(1, int(round(6 * 3600 / step)))
    days = n * step / 86400
    trh = train_hours(ds)
    sc = noise_scale(ds, st.res)
    has_g = np.isfinite(st.Xg).all(axis=1)
    c2g = st.cyc2grid
    tols = {lv: tol_vec(st, lv) for lv in LEVELS}

    al_clean = run_detector(ds, ds.X, st.res, trh)
    inj = {}
    for shape, amp in SETTINGS:
        X, ev = inject(ds, shape, amp, DUR_MIN, seed=0, scale=sc, res=st.res)
        inj[(shape, amp)] = (X, ev, run_detector(ds, X, st.res, trh))
    test_days = (ds.t[ds.test].iloc[-1] - ds.t[ds.test].iloc[0]).total_seconds() / 86400
    fa30 = al_clean[ds.test].sum() / test_days * 30 / len(PARAMS)

    def urgent_mask(al):
        u = np.zeros(n, bool); u[c2g[al.any(axis=1)]] = True
        return u

    rng = np.random.default_rng(seed)                  # links exactly as in the development runners
    links = {"none": np.ones(n, bool)}
    for k, rec in recs.items():
        links[k] = map_link(rec, st.grid_t, float(rng.uniform(0, len(rec[2]) * rec[1])))

    scored = st.test_g & has_g
    ev_rows, en_rows, pic_rows = [], [], []

    def bounded_run(link, r, kw, nf, tol, Xg, urgent):
        extra = dict(newest_first=True, valid=has_g) if nf else {}
        return simulate(link, r, "batch_events", M_check=M, probe_cap=cap, urgent=urgent,
                        trigger=make_trigger(Xg, tol, spd, step), **extra, **kw)

    def energy_row(tr, rl, k, setting, level, s_, floor, arr, alarms):
        return {"site": site_id, "trace": tr, "radio": rl, "strategy": k, "setting": setting, "level": level,
                "energy_j_per_day": s_["energy_j_per_day"], "lifetime_y": BATTERY / (floor + s_["energy_j_per_day"]) / 365,
                "delivered": np.isfinite(arr[scored]).mean(),
                "within_1h": np.mean(arr[scored] - st.grid_t[scored] <= 3600),
                "fa_per30d_param": fa30, "alarms_per_day": alarms}

    for tr, link in links.items():
        kw = dict(slot_s=step, p_radio=P_RADIO[tr], seed=seed)
        u0 = simulate(link, radio(next(iter(RADIOS))), "unconf", **kw)
        keep_cyc = np.isfinite(u0.arrival_delay_s)[c2g]
        srv_al = {s: run_detector_on_subset(st, inj[s][0], keep_cyc, st.res, trh) for s in SETTINGS}
        for rl in RADIOS:
            r = radio(rl)
            floor = floor_j_per_day(r, step)
            uc = urgent_mask(al_clean)
            runs = {
                ("unconf", "-"): simulate(link, r, "unconf", **kw),
                ("arq_buffer", "-"): simulate(link, r, "arq_buffer", probe_cap=cap, **kw),
                ("batch1h", "-"): simulate(link, r, "batch", M_check=M, probe_cap=cap, **kw),
                ("design", "-"): simulate(link, r, "batch_events", M_check=M, probe_cap=cap, urgent=uc, **kw),
            }
            for lv in LEVELS:
                runs[("design_bounded", lv)] = bounded_run(link, r, kw, False, tols[lv], st.Xg, uc)
                runs[("design_bounded_nf", lv)] = bounded_run(link, r, kw, True, tols[lv], st.Xg, uc)
            arr = {}
            for (k, lv), v in runs.items():
                a = np.where(has_g, st.grid_t + v.arrival_delay_s, np.inf)
                arr[(k, lv)] = a
                en_rows.append(energy_row(tr, rl, k, "clean", lv, summary(v, n, step), floor, a, uc.sum() / days))
                for lv_score in ([lv] if lv != "-" else list(LEVELS)):
                    for j, p in enumerate(PARAMS):
                        est = server_picture(st.Xg[:, j], a, st.grid_t, spd, scored)
                        err = np.abs(est - st.Xg[scored, j]); ok = np.isfinite(err)
                        pic_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k, "level": lv_score,
                                         "param": p,
                                         "within_tol": np.mean(within_tol(err[ok], tols[lv_score][j])) if ok.any() else np.nan,
                                         "median_abs_err": np.median(err[ok]) if ok.any() else np.nan,
                                         "shown_share": ok.mean(), "tol": tols[lv_score][j]})
            # injected events: L2 only (the reference level), every strategy
            pm = {k: np.maximum.accumulate(arr[(k, "-")][c2g]) for k in ("arq_buffer", "batch1h")}
            for (shape, amp) in SETTINGS:
                X, ev, al = inj[(shape, amp)]
                Xg_inj = st.Xg.copy(); Xg_inj[c2g] = X
                ua = urgent_mask(al)
                arr_ev = {}
                for k in ("design",) + BOUNDED:
                    if k == "design":
                        v = simulate(link, r, "batch_events", M_check=M, probe_cap=cap, urgent=ua, **kw)
                    else:
                        v = bounded_run(link, r, kw, k.endswith("_nf"), tols["L2"], Xg_inj, ua)
                    a = np.where(has_g, st.grid_t + v.arrival_delay_s, np.inf)
                    arr_ev[k] = a
                    en_rows.append(energy_row(tr, rl, k, f"{shape}{amp}", "L2" if k in BOUNDED else "-",
                                              summary(v, n, step), floor, a, ua.sum() / days))
                for e in ev.itertuples():
                    s, end, j = int(e.s), int(e.e), int(e.j)
                    t_on = st.grid_t[c2g[s]]
                    up = bool(link[c2g[s]])
                    node_hit = np.flatnonzero(al[s:end, j])
                    srv_hit = np.flatnonzero(srv_al[(shape, amp)][s:end, j])
                    hit = s + node_hit[0] if len(node_hit) else None
                    out = {"unconf": arr[("unconf", "-")][c2g[s + srv_hit[0]]] if len(srv_hit) else np.inf,
                           "arq_buffer": pm["arq_buffer"][hit] if hit is not None else np.inf,
                           "batch1h": pm["batch1h"][hit] if hit is not None else np.inf}
                    for k in ("design",) + BOUNDED:
                        out[k] = arr_ev[k][c2g[hit]] if hit is not None else np.inf
                    # physical plausibility of the injected values (CONFIRMATORY_PLAN §6, secondary analysis)
                    xv = X[s:end, j]
                    for k, t_known in out.items():
                        ev_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k,
                                        "setting": f"{shape}{amp}", "param": PARAMS[j], "link_up_at_onset": up,
                                        "node_detected": len(node_hit) > 0,
                                        "latency_h": (t_known - t_on) / 3600 if np.isfinite(t_known) else np.inf,
                                        "inj_min": float(np.nanmin(xv)), "inj_max": float(np.nanmax(xv))})
    return pd.DataFrame(ev_rows), pd.DataFrame(en_rows), pd.DataFrame(pic_rows)


def main(clean_dir, elig_csv, out_dir, salt, sites=None):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    elig = pd.read_csv(elig_csv, dtype={"site": str})
    elig = elig[elig.status == "ok"]
    recs = load_records()
    for sid in elig.site:
        if sites and sid not in sites:
            continue
        if all((out / f"{sid}_{k}.csv").exists() for k in ("events", "energy", "picture")):
            print(f"skip {sid}", flush=True); continue
        t0 = time.time()
        ev, en, pic = evaluate_site(sid, site_seed(sid, salt), recs, clean_dir)
        ev.to_csv(out / f"{sid}_events.csv", index=False, float_format="%.6g")
        en.to_csv(out / f"{sid}_energy.csv", index=False, float_format="%.6g")
        pic.to_csv(out / f"{sid}_picture.csv", index=False, float_format="%.6g")
        print(f"{sid} done in {time.time() - t0:.0f} s ({len(ev)} event rows)", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:5], sites=sys.argv[5:])
