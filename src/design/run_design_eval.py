"""Design evaluation, as fixed in docs/DESIGN_EVAL_PLAN.md (written before any result).

Per eligible site (results/scoping/design_site_eligibility.csv):
  links   : InWaterSense, Weija, UVA records mapped onto the site grid (offset seeded by site index) + none
  radios  : NB-IoT N211 RAI (10-s search), LoRaWAN SF7, LoRaWAN SF12
  strategies: unconf, arq_buffer (back-off <= 6 h), batch1h (back-off <= 6 h), design (= batch_events)
  events  : Paper 1 injected step/ramp, amp 5/8 sigma, 180 min; Paper 1 frozen detector
Outputs (resumable, one set per site) in results/design/:
  <site>_events.csv   one row per injected event x trace x radio x strategy
  <site>_energy.csv   one row per trace x radio x strategy (x setting for the design)
  <site>_picture.csv  one row per trace x radio x strategy x parameter (clean series)
Usage (from Paper2/): python -I src/design/run_design_eval.py [site ...]
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from design.inject import inject, noise_scale  # noqa: E402
from design.sitedata import (P_RADIO, PARAMS, TOL, load_records, load_site, make_trigger, map_link,  # noqa: E402
                             within_tol, run_detector, run_detector_on_subset, server_picture, train_hours)
from energy import params as P  # noqa: E402
from energy.loss_handling import Radio, simulate, summary  # noqa: E402

OUT = Path("results/design")
SETTINGS = [("step", 5), ("step", 8), ("ramp", 5), ("ramp", 8)]
DUR_MIN = 180
RADIOS = {"NB-IoT N211 RAI (search 10 s)": ("NB-IoT N211 RAI", 10.0), "LoRaWAN SF7": ("LoRaWAN SF7", None),
          "LoRaWAN SF12": ("LoRaWAN SF12", None)}
BATTERY = P.BATTERIES["6600 mAh Li-ion (Weija node, paper 22)"]


def radio(label):
    name, ts = RADIOS[label]
    return Radio(name, t_search=ts) if ts is not None else Radio(name)


def floor_j_per_day(r, step_s):
    return 86400 * (r.prof["p_sleep"] + P.P_HOST_SLEEP) + 86400 / step_s * P.P_HOST_ON * P.T_SENSE["typical"]


def evaluate_site(site_id, site_index, recs):
    st = load_site(site_id)
    ds, n = st.ds, len(st.grid_t)
    step = st.step_s
    spd = int(round(86400 / step)); M = max(1, int(round(3600 / step))); cap = max(1, int(round(6 * 3600 / step)))
    days = n * step / 86400
    trh = train_hours(ds)
    sc = noise_scale(ds, st.res)
    has_g = np.isfinite(st.Xg).all(axis=1)                       # slot holds a complete reading
    c2g = st.cyc2grid
    onset_t = lambda s: st.grid_t[c2g[s]]

    # node-side detection: clean series and each injected setting (Paper 1 detector, frozen)
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

    rng = np.random.default_rng(site_index)            # site_index is the site-ID seed (deviation D3)
    links = {"none": np.ones(n, bool)}
    for k, rec in recs.items():
        span = len(rec[2]) * rec[1]
        links[k] = map_link(rec, st.grid_t, float(rng.uniform(0, span)))

    ev_rows, en_rows, pic_rows = [], [], []
    xg_scored = st.test_g & has_g
    tolv = np.array([TOL.get(p, 0.02 * np.nanmedian(st.Xg[:, j])) for j, p in enumerate(PARAMS)])
    for tr, link in links.items():
        pr = P_RADIO[tr]
        kw = dict(slot_s=step, p_radio=pr, seed=site_index)
        # unconfirmed delivery: one attempt per slot, so the random draws (and the delivered set) are the
        # same for every radio; server-side detection on the delivered readings, once per setting
        u0 = simulate(link, radio(next(iter(RADIOS))), "unconf", **kw)
        keep_cyc = np.isfinite(u0.arrival_delay_s)[c2g]
        srv_al = {s: run_detector_on_subset(st, inj[s][0], keep_cyc, st.res, trh) for s in SETTINGS}
        for rl in RADIOS:
            r = radio(rl)
            floor = floor_j_per_day(r, step)
            runs = {
                "unconf": simulate(link, r, "unconf", **kw),
                "arq_buffer": simulate(link, r, "arq_buffer", probe_cap=cap, **kw),
                "batch1h": simulate(link, r, "batch", M_check=M, probe_cap=cap, **kw),
                "design": simulate(link, r, "batch_events", M_check=M, probe_cap=cap,
                                   urgent=urgent_mask(al_clean), **kw),
                # Part 2: design + bounded-error trigger (a fresh trigger per run: it keeps state)
                "design_bounded": simulate(link, r, "batch_events", M_check=M, probe_cap=cap,
                                           urgent=urgent_mask(al_clean), trigger=make_trigger(st.Xg, tolv, spd, step), **kw),
            }
            assert np.array_equal(np.isfinite(runs["unconf"].arrival_delay_s), np.isfinite(u0.arrival_delay_s))
            arr = {k: np.where(has_g, st.grid_t + v.arrival_delay_s, np.inf) for k, v in runs.items()}
            for k, v in runs.items():
                s_ = summary(v, n, step)
                e_tot = floor + s_["energy_j_per_day"]
                en_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k, "setting": "clean",
                                "energy_j_per_day": s_["energy_j_per_day"], "lifetime_y": BATTERY / e_tot / 365,
                                "delivered": np.isfinite(arr[k][xg_scored]).mean(),
                                "within_1h": np.mean(arr[k][xg_scored] - st.grid_t[xg_scored] <= 3600),
                                "fa_per30d_param": fa30, "alarms_per_day": urgent_mask(al_clean).sum() / days})
                # real-time picture on the clean series
                for j, p in enumerate(PARAMS):
                    est = server_picture(st.Xg[:, j], arr[k], st.grid_t, spd, xg_scored)
                    err = np.abs(est - st.Xg[xg_scored, j])
                    shown = np.isfinite(err)
                    pic_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k, "param": p,
                                     "within_tol": np.mean(within_tol(err[shown], tolv[j])) if shown.any() else np.nan,
                                     "median_abs_err": np.median(err[shown]) if shown.any() else np.nan,
                                     "shown_share": shown.mean(), "tol": tolv[j]})
            # events: per setting
            pm = {k: np.maximum.accumulate(arr[k][c2g]) for k in ("arq_buffer", "batch1h")}
            for (shape, amp) in SETTINGS:
                X, ev, al = inj[(shape, amp)]
                # the node's trigger works on the readings it actually takes (with the injected event)
                Xg_inj = st.Xg.copy(); Xg_inj[c2g] = X
                arr_ds = {}
                for k, trig in (("design", None), ("design_bounded", make_trigger(Xg_inj, tolv, spd, step))):
                    dsg = simulate(link, r, "batch_events", M_check=M, probe_cap=cap, urgent=urgent_mask(al),
                                   trigger=trig, **kw)
                    arr_ds[k] = np.where(has_g, st.grid_t + dsg.arrival_delay_s, np.inf)
                    s_ = summary(dsg, n, step)
                    en_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k,
                                    "setting": f"{shape}{amp}", "energy_j_per_day": s_["energy_j_per_day"],
                                    "lifetime_y": BATTERY / (floor + s_["energy_j_per_day"]) / 365,
                                    "delivered": np.isfinite(arr_ds[k][xg_scored]).mean(),
                                    "within_1h": np.mean(arr_ds[k][xg_scored] - st.grid_t[xg_scored] <= 3600),
                                    "fa_per30d_param": fa30, "alarms_per_day": urgent_mask(al).sum() / days})
                for e in ev.itertuples():
                    s, end, j = int(e.s), int(e.e), int(e.j)
                    t_on = onset_t(s)
                    up = bool(link[c2g[s]])
                    node_hit = np.flatnonzero(al[s:end, j])
                    srv_hit = np.flatnonzero(srv_al[(shape, amp)][s:end, j])
                    out = {
                        "unconf": arr["unconf"][c2g[s + srv_hit[0]]] if len(srv_hit) else np.inf,
                        "arq_buffer": pm["arq_buffer"][s + node_hit[0]] if len(node_hit) else np.inf,
                        "batch1h": pm["batch1h"][s + node_hit[0]] if len(node_hit) else np.inf,
                        "design": arr_ds["design"][c2g[s + node_hit[0]]] if len(node_hit) else np.inf,
                        "design_bounded": arr_ds["design_bounded"][c2g[s + node_hit[0]]] if len(node_hit) else np.inf,
                    }
                    for k, t_known in out.items():
                        ev_rows.append({"site": site_id, "trace": tr, "radio": rl, "strategy": k,
                                        "setting": f"{shape}{amp}", "param": PARAMS[j], "link_up_at_onset": up,
                                        "node_detected": len(node_hit) > 0,
                                        "latency_h": (t_known - t_on) / 3600 if np.isfinite(t_known) else np.inf})
    return pd.DataFrame(ev_rows), pd.DataFrame(en_rows), pd.DataFrame(pic_rows)


def main(sites=None):
    OUT.mkdir(parents=True, exist_ok=True)
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    elig = elig[elig.status == "ok"].reset_index(drop=True)
    recs = load_records()
    for i, row in elig.iterrows():
        sid = row.site
        if sites and sid not in sites:
            continue
        if all((OUT / f"{sid}_{k}.csv").exists() for k in ("events", "energy", "picture")):
            print(f"skip {sid}", flush=True); continue
        t0 = time.time()
        ev, en, pic = evaluate_site(sid, int(sid) % (2 ** 31 - 1), recs)   # seed from the site ID (D3)
        ev.to_csv(OUT / f"{sid}_events.csv", index=False, float_format="%.6g")
        en.to_csv(OUT / f"{sid}_energy.csv", index=False, float_format="%.6g")
        pic.to_csv(OUT / f"{sid}_picture.csv", index=False, float_format="%.6g")
        print(f"{sid} done in {time.time() - t0:.0f} s ({len(ev)} event rows)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
