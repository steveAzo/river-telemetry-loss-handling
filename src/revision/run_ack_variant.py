"""Review C6: the bounded-error trigger when the node may NOT treat a LoRaWAN network-server ACK as proof that the
application server shows the reading (sitedata.make_trigger, ack='application': the node keeps the bound for both
possible server states until an application ACK comes back in the downlink of a later uplink).

Development sites (2023), series without injected events, every link, LoRaWAN SF7 and SF12 (NB-IoT's confirmed
report is already acknowledged by the application, so it needs no variant). Final design: newest-first packing, L2.
Reports energy and picture for ack = network vs application, plus ARQ + buffer for reference.
Usage (from Paper2/): python -I src/revision/run_ack_variant.py results/revision/ack_variant.csv
"""
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, "src/design")
from design.sitedata import (P_RADIO, PARAMS, load_records, load_site, make_trigger, map_link, run_detector,  # noqa: E402
                             server_picture, train_hours, within_tol)
from energy.loss_handling import simulate, summary  # noqa: E402
from run_design_eval import radio  # noqa: E402
from run_sensitivity import tol_vec  # noqa: E402


def main(out):
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    recs = load_records()
    rows = []
    for sid in elig[elig.status == "ok"].site:
        t0 = time.time()
        st = load_site(sid)
        n, step = len(st.grid_t), st.step_s
        spd = int(round(86400 / step)); M = max(1, int(round(3600 / step))); cap = max(1, int(round(6 * 3600 / step)))
        has_g = np.isfinite(st.Xg).all(axis=1)
        al = run_detector(st.ds, st.ds.X, st.res, train_hours(st.ds))
        urgent = np.zeros(n, bool); urgent[st.cyc2grid[al.any(axis=1)]] = True
        tol = tol_vec(st, "L2")
        seed = int(sid) % (2 ** 31 - 1)
        rng = np.random.default_rng(seed)
        links = {"none": np.ones(n, bool)}
        for k, rec in recs.items():
            links[k] = map_link(rec, st.grid_t, float(rng.uniform(0, len(rec[2]) * rec[1])))
        scored = st.test_g & has_g
        for tr, link in links.items():
            kw = dict(slot_s=step, p_radio=P_RADIO[tr], seed=seed)
            for rl in ("LoRaWAN SF7", "LoRaWAN SF12"):
                r = radio(rl)
                runs = {"arq_buffer": simulate(link, r, "arq_buffer", probe_cap=cap, **kw)}
                for ack in ("network", "application"):
                    runs[f"bounded_{ack}"] = simulate(link, r, "batch_events", M_check=M, probe_cap=cap, urgent=urgent,
                                                      trigger=make_trigger(st.Xg, tol, spd, step, ack=ack),
                                                      newest_first=True, valid=has_g, **kw)
                for k, v in runs.items():
                    arr = np.where(has_g, st.grid_t + v.arrival_delay_s, np.inf)
                    row = {"site": sid, "trace": tr, "radio": rl, "strategy": k,
                           "energy_j_per_day": summary(v, n, step)["energy_j_per_day"]}
                    for j, p in enumerate(PARAMS):
                        err = np.abs(server_picture(st.Xg[:, j], arr, st.grid_t, spd, scored) - st.Xg[scored, j])
                        ok = np.isfinite(err)
                        row[f"within_{p}"] = float(np.mean(within_tol(err[ok], tol[j])))
                    rows.append(row)
        pd.DataFrame(rows).to_csv(out, index=False, float_format="%.6g")
        print(f"{sid} done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
