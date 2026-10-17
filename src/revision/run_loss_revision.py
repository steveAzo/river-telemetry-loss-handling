"""Loss-handling sensitivity analyses asked for by the review, on the real delivery records.

Records (link state = the record): InWaterSense node 1 (611-s slots), Weija conductivity as in v0.1, and the
Weija NODE record (a slot is up if any stream delivered a genuine reading; src/revision/gap_cause.py).
Radios: NB-IoT N211 RAI (10-s search), LoRaWAN SF7, SF12.

Part A, ARQ timing and specification version (review C2, M7):
  ARQ variants: 'arq8_v102'  8 transmissions, data rate stepped down every two (LoRaWAN 1.0.2 Sec. 18.4; v0.1)
                'arq3_v102'  3 transmissions, stepped (the v0.1 sensitivity)
                'arq8_v104'  NbTrans = 8, no stepping (LoRaWAN L2 1.0.4 Sec. 4.3.1.3: NbTrans in [1, 15])
                'arq3_v104'  NbTrans = 3, no stepping
                NB-IoT: 3 attempts (unchanged)
  link-timing models: full / uniform / burst (energy.loss_handling.intra_slot_model), 5 draws for the random ones;
  independent radio loss p = 0 and 0.096. Also unconf and arq_buffer under each model.
Part B, gap cause (review C1): a share f of the slots in gaps >= 6 h belong to gaps in which the NODE was off
  (whole gaps drawn at random, 20 draws): no reading generated, no energy. f in {0, 0.1, 0.25, 0.5}.
Part C, storage and backlog (review C5): finite RAM buffers (2, 8, 64 KB of 12-B readings, oldest dropped),
  flash with write/read energy (Winbond W25Q128JV Rev F: typical and worst case, incl. the host awake), and
  drain limits (none; the most frames the 1% duty cycle allows per slot, keeping one for live traffic; 1 frame).
Outputs: results/revision/loss_{A,B,C}.csv. Usage (from Paper2/): python -I src/revision/run_loss_revision.py [A B C]
"""
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from design.sitedata import record_up  # noqa: E402
from energy import params as P  # noqa: E402
from energy.loss_handling import (FRAME_OVERHEAD, READING_BYTES, Radio, intra_slot_model,  # noqa: E402
                                  simulate, summary)
from revision.gap_cause import weija_links  # noqa: E402

OUT = "results/revision"
P_RADIO_LOED, Q_BURST = 0.096, 0.248          # LoED well-heard devices: loss rate, P(loss | previous loss)
SEEDS_TIMING, SEEDS_OFF = range(5), range(20)
# Flash (W25Q128JV Rev F, Sec. 9.4/9.6): page program 20 (typ) / 25 (max) mA for 0.4 / 3 ms per 256-B page;
# 4-KB sector erase 20 / 25 mA for 45 / 400 ms; VCC 3.3 V. Host (Waspmote, 69 mW) assumed awake throughout.
V_FLASH = 3.3


def flash_energy(case):
    i, t_pp, t_se = (20e-3, 0.4e-3, 45e-3) if case == "typical" else (25e-3, 3e-3, 400e-3)
    per_page, per_sector = 256 // READING_BYTES, 4096 // READING_BYTES
    host = P.P_HOST_ON
    write = (i * V_FLASH + host) * t_pp / per_page + (i * V_FLASH + host) * t_se / per_sector
    read = 1e-6                                   # 12 B at SPI speed: microseconds; 1 uJ is a generous bound
    return write, read


def traces():
    d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    t0, slot, up = record_up((d[d.node == 1].t.astype("int64") // 1_000_000_000).to_numpy(), 611.0)
    yield "InWaterSense", up, slot
    wslot, up_v01, _, alive, _ = weija_links()
    yield "Weija (v0.1 EC record)", up_v01, wslot
    yield "Weija (node record)", alive, wslot


def radios():
    yield "NB-IoT", lambda **k: Radio("NB-IoT N211 RAI", t_search=10.0, **k)
    yield "LoRaWAN SF7", lambda **k: Radio("LoRaWAN SF7", **k)
    yield "LoRaWAN SF12", lambda **k: Radio("LoRaWAN SF12", **k)


def row(tr, rl, strat, res, n, slot, **extra):
    s = summary(res, n, slot)
    return {"trace": tr, "radio": rl, "strategy": strat, "energy_j_per_day": s["energy_j_per_day"],
            "delivered": s["on_time"] + s["late"], "delivered_of_expected": s["delivered_of_expected"],
            "within_1h": s["within_1h"], "max_buffer": res.max_buffer, "storage_j_per_day": s["storage_j_per_day"],
            **extra}


def part_a():
    rows = []
    for tr, link, slot in traces():
        cap = max(1, int(round(6 * 3600 / slot)))
        for rl, mk in radios():
            if rl == "NB-IoT":
                variants = {"unconf": ("unconf", {}, None), "arq": ("arq", {}, 3), "arq_buffer": ("arq_buffer", {}, None)}
            else:
                variants = {"unconf": ("unconf", {}, None), "arq8_v102": ("arq", {}, 8), "arq3_v102": ("arq", {}, 3),
                            "arq8_v104": ("arq", {"dr_step": False}, 8), "arq3_v104": ("arq", {"dr_step": False}, 3),
                            "arq_buffer": ("arq_buffer", {}, None)}
            for model in ("full", "uniform", "burst"):
                for seed in ([0] if model == "full" else SEEDS_TIMING):
                    restore, fail = intra_slot_model(link, slot, model, seed=seed, q_burst=Q_BURST)
                    for p in (0.0, P_RADIO_LOED):
                        for name, (strat, rk, R) in variants.items():
                            res = simulate(link, mk(**rk), strat, p_radio=p, R=R, seed=20261011 + seed, slot_s=slot,
                                           probe_cap=cap, restore=restore, down_retry_fail=fail)
                            rows.append(row(tr, rl, name, res, len(link), slot, model=model, draw=seed, p_radio=p))
        print(f"A {tr} done", flush=True)
    pd.DataFrame(rows).to_csv(f"{OUT}/loss_A.csv", index=False, float_format="%.6g")


def node_off_mask(link, slot, f, rng, long_h=6.0):
    m = np.r_[False, ~link, False]
    d = np.diff(m.astype(int))
    st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    long = [(a, b) for a, b in zip(st, en) if (b - a) * slot >= long_h * 3600]
    total = sum(b - a for a, b in long)
    off = np.zeros(len(link), bool)
    if f <= 0 or not long:
        return off, 0.0
    got = 0
    for i in rng.permutation(len(long)):
        if got >= f * total:
            break
        a, b = long[i]; off[a:b] = True; got += b - a
    return off, got / total


def part_b():
    rows = []
    for tr, link, slot in traces():
        cap = max(1, int(round(6 * 3600 / slot))); M = max(1, int(round(3600 / slot)))
        for rl, mk in radios():
            strats = {"unconf": ("unconf", {}), "arq_buffer": ("arq_buffer", {"probe_cap": cap}),
                      "batch1h": ("batch", {"probe_cap": cap, "M_check": M})}
            if rl == "NB-IoT":
                strats["unconf_backoff"] = ("unconf_backoff", {"probe_cap": cap})
            for f in (0.0, 0.1, 0.25, 0.5):
                for seed in ([0] if f == 0 else SEEDS_OFF):
                    off, real_f = node_off_mask(link, slot, f, np.random.default_rng(seed))
                    for name, (strat, kw) in strats.items():
                        res = simulate(link, mk(), strat, seed=20261011, slot_s=slot, node_off=off, **kw)
                        rows.append(row(tr, rl, name, res, len(link), slot, f=f, f_realised=real_f, draw=seed,
                                        not_generated=res.not_generated / len(link)))
        print(f"B {tr} done", flush=True)
    pd.DataFrame(rows).to_csv(f"{OUT}/loss_B.csv", index=False, float_format="%.6g")


def part_c():
    rows = []
    fl = {c: flash_energy(c) for c in ("typical", "worst")}
    for tr, link, slot in traces():
        cap = max(1, int(round(6 * 3600 / slot))); M = max(1, int(round(3600 / slot)))
        for rl, mk in radios():
            r = mk()
            per = r.readings_per_frame()
            if r.nb:
                limits = {"none": None, "1 frame/slot": 1}
            else:
                full_air = r.airtime_s(FRAME_OVERHEAD + READING_BYTES * per)
                duty = max(1, int(slot // (100 * full_air)) - 1)
                limits = {"none": None, f"duty cycle ({duty} frames/slot)": duty, "1 frame/slot": 1}
            storages = {"unlimited, no energy": (None, None)}
            for kb in (2, 8, 64):
                storages[f"RAM {kb} KB"] = (kb * 1024 // READING_BYTES, None)
            for c, e in fl.items():
                storages[f"flash ({c})"] = (None, e)
            for strat, kw in (("arq_buffer", {"probe_cap": cap}), ("batch1h", {"probe_cap": cap, "M_check": M})):
                base = "batch" if strat == "batch1h" else strat
                for sname, (bcap, energy) in storages.items():
                    for lname, lim in limits.items():
                        if sname != "unlimited, no energy" and lname != "none":
                            continue                     # storage x limit: the two effects are separable
                        # long flush: a drain-limited backlog still queued when the record ends is not a loss
                        res = simulate(link, r, base, seed=20261011, slot_s=slot, buffer_cap=bcap, storage=energy,
                                       drain_max_frames=lim, flush=20_000, **kw)
                        clear_h = [(b - a) * slot / 3600 for a, b, _ in res.backlogs]
                        # readings generated while a backlog was draining: their delay
                        live = np.zeros(len(link), bool)
                        for a, b, _ in res.backlogs:
                            live[a:b + 1] = True
                        dl = res.arrival_delay_s[live & np.isfinite(res.arrival_delay_s)] / 3600
                        rows.append(row(tr, rl, strat, res, len(link), slot, storage=sname, drain_limit=lname,
                                        buffer_cap=bcap or 0, lost=res.lost / len(link),
                                        backlogs=len(res.backlogs), clear_h_median=np.median(clear_h) if clear_h else 0.0,
                                        clear_h_max=max(clear_h) if clear_h else 0.0,
                                        live_delay_h_median=np.median(dl) if len(dl) else 0.0,
                                        live_delay_h_p95=np.percentile(dl, 95) if len(dl) else 0.0,
                                        max_buffer_kb=res.max_buffer * READING_BYTES / 1024))
        print(f"C {tr} done", flush=True)
    pd.DataFrame(rows).to_csv(f"{OUT}/loss_C.csv", index=False, float_format="%.6g")


if __name__ == "__main__":
    parts = sys.argv[1:] or ["A", "B", "C"]
    for p_ in parts:
        t0 = time.time()
        {"A": part_a, "B": part_b, "C": part_c}[p_]()
        print(f"part {p_}: {time.time() - t0:.0f} s", flush=True)
