"""Review E7/M5: back-off cap K and batch period, on the real delivery records.

Strategies: confirmed + buffer + back-off (per reading) and batching, both with back-off cap K.
  K in {1 slot (probe every slot), 1, 2, 3, 6, 12, 24} h with 1-h batches;
  batch period in {15 min (or one slot), 30 min, 1, 2, 3, 6, 12} h with K = 6 h.
Metrics: transmission energy (J/day), share of readings within 1 h, and the RECOVERY LATENCY: for every gap that
ends while the record continues, the time from the link's return to the arrival of the gap's last reading (how
long back-off and batching keep the server waiting once the network is back; an alarm raised in the gap waits
about as long, unless the design's alarm probe fires). Records: InWaterSense, Weija (node record); radios:
NB-IoT (10-s search), LoRaWAN SF7, SF12.
Usage (from Paper2/): python -I src/revision/sweep_k_batch.py results/revision/sweep_k_batch.csv
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from energy.loss_handling import simulate, summary  # noqa: E402
from revision.run_loss_revision import radios, traces  # noqa: E402

K_H = [0, 1, 2, 3, 6, 12, 24]                  # 0 = probe every slot
B_H = [0.25, 0.5, 1, 2, 3, 6, 12]


def recovery_latency_h(link, res, slot):
    m = np.r_[False, ~link, False]
    d = np.diff(m.astype(int))
    ends = np.flatnonzero(d == -1)                 # first up slot after each gap
    out = []
    for b in ends:
        if b >= len(link):
            continue
        a = res.arrival_delay_s[b - 1]
        if np.isfinite(a):
            out.append(((b - 1) * slot + a - b * slot) / 3600)
    return np.array(out)


def main(out):
    rows = []
    for tr, link, slot in traces():
        if tr.startswith("Weija (v0.1"):
            continue
        for rl, mk in radios():
            r = mk()
            combos = [("arq_buffer", k, None) for k in K_H] + [("batch", k, 1) for k in K_H] + \
                     [("batch", 6, b) for b in B_H if b != 1]
            for strat, k_h, b_h in combos:
                cap = 1 if k_h == 0 else max(1, int(round(k_h * 3600 / slot)))
                M = max(1, int(round((b_h or 1) * 3600 / slot)))
                res = simulate(link, r, strat, seed=20261011, slot_s=slot, probe_cap=cap, M_check=M)
                s = summary(res, len(link), slot)
                lat = recovery_latency_h(link, res, slot)
                rows.append({"trace": tr, "radio": rl, "strategy": strat, "K_h": k_h, "batch_h": b_h if b_h else np.nan,
                             "batch_slots": M if strat == "batch" else np.nan, "energy_j_per_day": s["energy_j_per_day"],
                             "delivered": s["on_time"] + s["late"], "within_1h": s["within_1h"],
                             "recovery_h_median": float(np.median(lat)) if len(lat) else np.nan,
                             "recovery_h_p90": float(np.percentile(lat, 90)) if len(lat) else np.nan})
            print(f"{tr} {rl} done", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(out, index=False, float_format="%.6g")
    print(d.round(3).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
