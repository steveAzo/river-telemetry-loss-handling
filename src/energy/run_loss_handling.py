"""Compare loss-handling strategies on real delivery records (PAPER2_SCOPING.md section 2.6).

Link traces (True = a reading in that slot reached the server in the real deployment):
  InWaterSense node 1, 611-s slots (data/clean/inws_cycles.csv)
  Weija conductivity, non-imputed records, 32.5-min slots (data/weija_raw)
The real record is used as the link state: real gaps = slots in which the network path was down.
(Short real gaps may be radio losses; the extra i.i.d. radio loss p_radio is a sensitivity on top.)
Lifetime adds Paper 1's sleep floor and sensing energy (5 s awake per sample) to the transmission
energy simulated here; 6600 mAh Li-ion battery (Weija node), ideal battery.
Usage (from Paper2/): python -I src/energy/run_loss_handling.py results/scoping/loss_handling.csv
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from energy.loss_handling import Radio, simulate, summary  # noqa: E402
from energy import params as P  # noqa: E402

BATTERY = P.BATTERIES["6600 mAh Li-ion (Weija node, paper 22)"]


def record_to_link(times, slot_s):
    t = pd.Series(pd.to_datetime(times)).drop_duplicates().sort_values()
    idx = np.rint((t - t.iloc[0]).dt.total_seconds().values / slot_s).astype(int)
    link = np.zeros(idx.max() + 1, bool); link[idx] = True
    return link


def traces():
    d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    yield "InWaterSense", record_to_link(d[d.node == 1].t, 611), 611.0
    w = pd.read_csv("data/weija_raw/conductivity_cleaned_records.csv", parse_dates=["Datetime"])
    w = w[w.Was_Imputed.astype(str) != "True"].Datetime.drop_duplicates().sort_values()
    slot = float(np.median(w.diff().dt.total_seconds().dropna()))
    yield "Weija", record_to_link(w, slot), slot


def configs():
    for t_search in (2.2, 10.0, 60.0):
        yield f"NB-IoT N211 RAI (search {t_search:g} s)", Radio("NB-IoT N211 RAI", t_search=t_search), \
            ["unconf", "unconf_backoff", "arq", "arq_buffer", "modem_buffer", "batch1h", "batch6h"]
    for sf in (7, 12):
        yield f"LoRaWAN SF{sf}", Radio(f"LoRaWAN SF{sf}"), ["unconf", "arq", "arq3", "arq_buffer", "checkpoint6", "checkpoint36", "batch1h", "batch6h"]


def main(out):
    rows = []
    for tname, link, slot in traces():
        per_day = 86400 / slot
        for rlabel, radio, strategies in configs():
            floor = 86400 * (radio.prof["p_sleep"] + P.P_HOST_SLEEP) + per_day * P.P_HOST_ON * P.T_SENSE["typical"]
            for strategy in strategies:
                base, m, R = (strategy, 6, None)
                if strategy.startswith("checkpoint"):
                    base, m = "checkpoint", int(strategy[len("checkpoint"):])
                if strategy == "arq3":                      # sensitivity: 3 attempts instead of the spec's 8
                    base, R = "arq", 3
                if strategy.startswith("batch"):            # upload every B hours (reference for energy vs delay)
                    base, m = "batch", max(1, int(round(int(strategy[5:-1]) * 3600 / slot)))
                buffering = base in ("arq_buffer", "modem_buffer", "checkpoint", "unconf_backoff")
                caps = (0, 1, 6) if buffering else ((6,) if base == "batch" else (0,))
                for probe_h in caps:   # 0 = probe every slot
                  cap = max(1, int(round(probe_h * 3600 / slot)))
                  for p_radio in (0.0, 0.096):   # 0.096 = LoED full-dataset radio loss, well-heard devices (section 2.4)
                    res = simulate(link, radio, base, p_radio=p_radio, M_check=m, seed=20261011, slot_s=slot,
                                   probe_cap=cap, R=R)
                    s = summary(res, len(link), slot)
                    e_total = floor + s["energy_j_per_day"]
                    row = {"trace": tname, "radio": rlabel, "strategy": strategy, "probe_cap_h": probe_h, "p_radio": p_radio,
                           "slot_s": slot, "days": len(link) * slot / 86400, **s,
                           "energy_floor_j_per_day": floor, "energy_total_j_per_day": e_total,
                           "lifetime_y": BATTERY / e_total / 365}
                    rows.append(row)
                    print(f"{tname:12s} {rlabel:30s} {strategy:13s} cap={probe_h}h p={p_radio:<5} E_tx={s['energy_j_per_day']:8.1f} J/d "
                          f"life={row['lifetime_y']:5.2f} y on-time={s['on_time']:.3f} late={s['late']:.3f} "
                          f"lost={s['lost']:.3f} delay p50/p95={s['delay_h_median']:.1f}/{s['delay_h_p95']:.1f} h "
                          f"dup/d={s['duplicates_per_day']:.1f}", flush=True)
    pd.DataFrame(rows).to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    main(sys.argv[1])
