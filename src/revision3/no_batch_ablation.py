"""Revision 3, audit issue 11: what does the hourly batch add to the bounded-error trigger? (post hoc ablation)

Plain dual prediction (send-on-delta) is the standard reporting-reduction baseline: the node sends only when the
server's estimate would leave the tolerance. The ablation removes the hourly batch from the final design and keeps
everything else (bounded-error trigger at L2, immediate alarm uploads, buffering with back-off, newest-first
packing); a triggered or alarm upload drains the whole buffer, so every reading is still delivered eventually.
  final design  : simulate(..., 'batch_events', M_check = 1 h, trigger, urgent, newest_first)   (as run_confirm.py)
  trigger only  : the same call with M_check larger than the record (no hourly upload), the same flush period
Held-out 2024 sites, corrected energy model and DO (src/revision3), the same seeds, links, detector, and tolerances
as results/revision3/corrected_2024 (the final design's energy is reproduced and asserted against that file).
Not run: injected events (alarm uploads are identical in both variants).
Output: results/revision3/no_batch/<site>.csv (one row per link x radio x variant), resumable.
Usage (from Paper2/): python -I src/revision3/no_batch_ablation.py
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from revision3 import corrected  # noqa: E402

corrected.apply()
from design.sitedata import (P_RADIO, PARAMS, load_records, load_site, make_trigger, map_link,  # noqa: E402
                             run_detector, server_picture, train_hours, within_tol)
from energy.loss_handling import simulate, summary  # noqa: E402
from run_confirm import site_seed  # noqa: E402
from run_design_eval import RADIOS, radio  # noqa: E402
from run_sensitivity import tol_vec  # noqa: E402

ROOT, ELIG, SALT = "data/clean/usgs_2024_baro", "results/confirm/eligibility_2024.csv", 2024
REF = "results/revision3/corrected_2024"
OUT = "results/revision3/no_batch"


def evaluate(site_id, recs):
    seed = site_seed(site_id, SALT)
    st = load_site(site_id, root=ROOT)
    ds, n, step = st.ds, len(st.grid_t), st.step_s
    spd = int(round(86400 / step)); M = max(1, int(round(3600 / step))); cap = max(1, int(round(6 * 3600 / step)))
    has_g = np.isfinite(st.Xg).all(axis=1)
    c2g = st.cyc2grid
    tol = tol_vec(st, "L2")
    al = run_detector(ds, ds.X, st.res, train_hours(ds))
    uc = np.zeros(n, bool); uc[c2g[al.any(axis=1)]] = True
    rng = np.random.default_rng(seed)                  # links exactly as in run_confirm.py
    links = {"none": np.ones(n, bool)}
    for k, rec in recs.items():
        links[k] = map_link(rec, st.grid_t, float(rng.uniform(0, len(rec[2]) * rec[1])))
    scored = st.test_g & has_g
    flush = 4 * cap + M + 16                           # the final design's flush period
    rows = []
    for tr, link in links.items():
        kw = dict(slot_s=step, p_radio=P_RADIO[tr], seed=seed)
        for rl in RADIOS:
            r = radio(rl)
            for var, m_check in (("final design", M), ("trigger only", n + 1)):
                v = simulate(link, r, "batch_events", M_check=m_check, probe_cap=cap, urgent=uc,
                             trigger=make_trigger(st.Xg, tol, spd, step), newest_first=True, valid=has_g,
                             flush=flush, **kw)
                s = summary(v, n, step)
                a = np.where(has_g, st.grid_t + v.arrival_delay_s, np.inf)
                row = {"site": site_id, "trace": tr, "radio": rl, "variant": var,
                       "energy_j_per_day": s["energy_j_per_day"],
                       "delivered": np.isfinite(a[scored]).mean(),
                       "within_1h": np.mean(a[scored] - st.grid_t[scored] <= 3600),
                       "delay_h_median": np.median((a[scored] - st.grid_t[scored]) / 3600)}
                for j, p in enumerate(PARAMS):
                    est = server_picture(st.Xg[:, j], a, st.grid_t, spd, scored)
                    err = np.abs(est - st.Xg[scored, j]); ok = np.isfinite(err)
                    row[f"within_{p}"] = np.mean(within_tol(err[ok], tol[j])) if ok.any() else np.nan
                rows.append(row)
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    elig = pd.read_csv(ELIG, dtype={"site": str})
    recs = load_records()
    for sid in elig[elig.status == "ok"].site:
        f = f"{OUT}/{sid}.csv"
        if os.path.exists(f):
            print(f"skip {sid}", flush=True); continue
        t0 = time.time()
        d = evaluate(sid, recs)
        ref = pd.read_csv(f"{REF}/{sid}_energy.csv", dtype={"site": str})
        ref = ref[(ref.strategy == "design_bounded_nf") & (ref.setting == "clean") & (ref.level == "L2")]
        chk = d[d.variant == "final design"].merge(ref, on=["trace", "radio"], suffixes=("", "_ref"))
        assert len(chk) == len(ref) > 0 and np.allclose(chk.energy_j_per_day, chk.energy_j_per_day_ref, rtol=1e-5), \
            f"{sid}: final design not reproduced"
        d.to_csv(f, index=False, float_format="%.6g")
        print(f"{sid} done in {time.time() - t0:.0f} s", flush=True)
    print("NO_BATCH_DONE", flush=True)


if __name__ == "__main__":
    main()
