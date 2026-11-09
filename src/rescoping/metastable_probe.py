"""Rescoping screen (docs/RESCOPING_2026-10-31.md, S4): is post-outage recovery in a LoRaWAN cell METASTABLE?

Metastable (Bronson et al. 2021) means: the cell is stable under its normal load, a trigger (here a shared outage)
pushes it into a bad state, and the bad state persists after the trigger is gone because the system's own reaction
(retries of frames that were received but not acknowledged, give-ups, re-probes) keeps the load above capacity.
A slow but steady drain is NOT metastability.

This replays src/revision/netsim.py's model unchanged (same gateway, nodes, back-off, retries, duty cycle) but
  - runs to a long horizon instead of stopping when every node has cleared once, and
  - records, every hour after the outage, the total backlog (readings buffered at the nodes), the nodes in each
    mode, uplink attempts, acknowledged frames, and received-but-unacknowledged frames.
Decision rule per (N, SF, outage): backlog at the horizon vs backlog at the end of the outage, and the same
N without an outage (control) must show no growth.
Usage (from Paper2/): python -I src/rescoping/metastable_probe.py
"""
import heapq
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from energy.loss_handling import FRAME_OVERHEAD, LIVE_BYTES, READING_BYTES, Radio  # noqa: E402
from revision.netsim import CAPTURE_DB, CHANNELS, DEMODULATORS, RX2_DELAY, Gateway, ack_air, air  # noqa: E402

OUT = "results/rescoping"


def trajectory(n_nodes, sf, outage_h, slot_s=900.0, K_h=6.0, jitter_s=3600.0, nbtrans=8, horizon_h=240.0,
               seed=0, rssi_sd=8.0, live_batch_h=1.0):
    """As netsim.simulate_recovery, with hourly state samples after the outage and no early stop."""
    rng = np.random.default_rng(seed)
    radio = Radio(f"LoRaWAN SF{sf}", dr_step=False)
    per = radio.readings_per_frame()
    K = max(1, int(round(K_h * 3600 / slot_s)))
    T0 = outage_h * 3600.0
    horizon = T0 + horizon_h * 3600
    rssi = rng.normal(-110, rssi_sd, n_nodes)
    rank = rng.permutation(n_nodes)
    gw = Gateway()
    st = [{"buf": 0, "mode": "outage", "n_fail": 1, "next_ok": 0.0, "last_gen": 0.0} for _ in range(n_nodes)]
    ev, seq = [], [0]

    def push(t, kind, i, data=None):
        seq[0] += 1; heapq.heappush(ev, (t, seq[0], kind, i, data))

    for i in range(n_nodes):
        push(min(2, K) * slot_s + rng.uniform(0, jitter_s), "probe", i)
    active = []
    hour = {"att": 0, "ok": 0, "noack": 0}
    rows, next_sample = [], T0

    def generated(i, t):
        n_new = int(t // slot_s) - int(st[i]["last_gen"] // slot_s)
        st[i]["last_gen"] = t
        st[i]["buf"] += max(0, n_new)

    def transmit(i, t, kind, nbytes, att):
        t = max(t, st[i]["next_ok"])
        a = air(sf, nbytes)
        st[i]["next_ok"] = t + 100 * a
        push(t, "tx_start", i, (t, t + a, int(rng.integers(CHANNELS)), kind, nbytes, att))

    def sample(ts):
        backlog = sum(x["buf"] + max(0, int(ts // slot_s) - int(x["last_gen"] // slot_s)) for x in st)
        modes = pd.Series([x["mode"] for x in st]).value_counts()
        rows.append({"t_h": (ts - T0) / 3600, "backlog": backlog, "outage": int(modes.get("outage", 0)),
                     "drain": int(modes.get("drain", 0)), "normal": int(modes.get("normal", 0)), **hour})
        hour.update(att=0, ok=0, noack=0)

    while ev:
        t, _, kind, i, data = heapq.heappop(ev)
        while next_sample <= min(t, horizon):
            sample(next_sample); next_sample += 3600
        if t > horizon:
            break
        s = st[i]
        if kind == "probe":
            generated(i, t)
            transmit(i, t, "probe", LIVE_BYTES, 1)
        elif kind == "batch":
            generated(i, t)
            if s["mode"] == "normal" and s["buf"] > 0:
                s["mode"] = "drain"
                transmit(i, t, "frame", FRAME_OVERHEAD + READING_BYTES * min(per, s["buf"]), 1)
            elif s["mode"] == "normal":
                push(t + live_batch_h * 3600, "batch", i)
        elif kind == "tx_start":
            start, end, ch, k2, nbytes, att = data
            active.append((start, end, ch, sf, i, k2, nbytes, att))
            push(end, "tx_end", i, data)
        elif kind == "tx_end":
            start, end, ch, k2, nbytes, att = data
            me = next(x for x in active if x[4] == i and x[0] == start)
            others = [x for x in active if x is not me and x[0] < end and x[1] > start]
            same = [x for x in others if x[2] == ch and x[3] == sf]
            received = t >= T0
            busy = [x for x in others if x[0] < start or (x[0] == start and rank[x[4]] < rank[i])]
            if received and len(busy) >= DEMODULATORS:
                received = False
            if received and same and any(rssi[i] - rssi[x[4]] < CAPTURE_DB for x in same):
                received = False
            if received and gw.overlaps_tx(start, end):
                received = False
            acked = received and gw.ack(end, sf)
            if start >= T0:
                hour["att"] += 1; hour["ok"] += int(acked); hour["noack"] += int(received and not acked)
            active[:] = [x for x in active if x[1] > t - 400]
            push(end + RX2_DELAY + ack_air(12), "result", i, (k2, nbytes, att, acked))
        elif kind == "result":
            k2, nbytes, att, acked = data
            if k2 == "probe":
                if acked:
                    s["mode"], s["n_fail"] = "drain", 0
                    generated(i, t)
                    if s["buf"] > 0:
                        transmit(i, t, "frame", FRAME_OVERHEAD + READING_BYTES * min(per, s["buf"]), 1)
                    else:
                        s["mode"] = "normal"; push(t + live_batch_h * 3600, "batch", i)
                else:
                    s["n_fail"] += 1
                    push(t + min(2 ** s["n_fail"], K) * slot_s + rng.uniform(0, jitter_s), "probe", i)
            else:
                if acked:
                    s["buf"] -= min(per, s["buf"])
                    generated(i, t)
                    if s["buf"] > 0:
                        transmit(i, t, "frame", FRAME_OVERHEAD + READING_BYTES * min(per, s["buf"]), 1)
                    else:
                        s["mode"] = "normal"; push(t + live_batch_h * 3600, "batch", i)
                elif att < nbtrans:
                    transmit(i, t + rng.uniform(1, 3), "frame", nbytes, att + 1)
                else:
                    s["mode"], s["n_fail"] = "outage", 1
                    push(t + min(2, K) * slot_s + rng.uniform(0, jitter_s), "probe", i)
    d = pd.DataFrame(rows)
    d.insert(0, "n_nodes", n_nodes); d.insert(1, "sf", sf); d.insert(2, "outage_h", outage_h); d.insert(3, "seed", seed)
    return d


def main():
    import os
    import time
    os.makedirs(OUT, exist_ok=True)
    cases = [(n, 12, L) for n in (25, 50, 100, 200) for L in (0.25, 24)]
    out = []
    for n, sf, L in cases:
        t0 = time.time()
        d = trajectory(n, sf, L, horizon_h=240.0)
        out.append(d)
        b = d.backlog.values
        print(f"SF{sf} N={n:3d} outage {L:5.2f} h: backlog at 0/24/72/168/240 h = "
              f"{b[0]}/{b[24]}/{b[72]}/{b[168]}/{b[-1]}; modes at end out/drain/norm = "
              f"{d.outage.iloc[-1]}/{d.drain.iloc[-1]}/{d.normal.iloc[-1]}; "
              f"acked/h last day = {d.ok.tail(24).mean():.0f}, noack/h = {d.noack.tail(24).mean():.0f} "
              f"[{time.time() - t0:.0f} s]", flush=True)
    pd.concat(out).to_csv(f"{OUT}/metastable_probe.csv", index=False)


if __name__ == "__main__":
    main()
