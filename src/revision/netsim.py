"""Review C8/E8: what happens when MANY LoRaWAN nodes recover from the same outage at once?

A compact discrete-event model of one EU868 gateway and N Class-A nodes that buffered through a common outage
of the gateway or its backhaul (the outage regime of the paper). It is deliberately simple and explicit:
  uplinks    3 default channels (868.1/868.3/868.5 MHz, one 1% sub-band); a node hops at random per frame.
             Two uplinks on the same channel and spreading factor (SF) that overlap in time collide; one
             survives if it is at least 6 dB stronger than every overlapping one (capture). Different SFs are
             treated as orthogonal. At most 8 uplinks are demodulated at once (8-path concentrator).
  gateway    half-duplex: an uplink overlapping any gateway transmission is lost. ACK for a confirmed uplink:
             RX1 (1 s after the uplink ends, same channel and SF) if the gateway is idle and its 1% sub-band
             allows (off-time 99 x airtime after each RX1 transmission); else RX2 (2 s after, 869.525 MHz, SF12,
             10% sub-band, off-time 9 x airtime); else no ACK (the node sees a failure).
  nodes      readings every slot_s are buffered during the outage. Back-off as in the paper: after the n-th
             failed probe wait min(2^n, K) slots; every node failed its first probe when the outage began, so
             without jitter all nodes probe at the same instants. Optional jitter: each probe is delayed by
             U(0, jitter_s). A successful probe starts the drain: confirmed bulk frames of `per` readings;
             a frame is retried after RETRANSMIT_TIMEOUT (1-3 s, RP002) up to `nbtrans` times (LoRaWAN 1.0.4,
             no data-rate stepping); after that the node returns to outage mode (back-off). The node's 1%
             duty cycle: a new frame no earlier than 100 x airtime after the previous one started.
             Live readings keep arriving during the drain and join the buffer; once the buffer is empty the node
             returns to hourly batches (which keep contending with the drains of other nodes).
  energy     per attempt, from the paper's energy model (energy.loss_handling.Radio.attempt, no DR stepping).
Metrics (from the end of the outage until every node has cleared its backlog, or the horizon):
  clearance time (all nodes / median node), uplink PDR (attempts that were received AND acknowledged),
  collision share, half-duplex losses, unacknowledged-but-received share, gateway downlink duty usage (RX1 and
  RX2), node energy relative to the same node recovering alone (N = 1).
Usage (from Paper2/): python -I src/revision/netsim.py results/revision/netsim.csv
"""
import heapq
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from energy import model as M  # noqa: E402
from energy.loss_handling import FRAME_OVERHEAD, LIVE_BYTES, READING_BYTES, Radio  # noqa: E402

CHANNELS = 3
CAPTURE_DB = 6.0
DEMODULATORS = 8
RX1_DELAY, RX2_DELAY = 1.0, 2.0


def air(sf, nbytes):
    return M.lora_frame_ms(sf, nbytes) / 1e3


def ack_air(sf):
    return M.lora_frame_ms(sf, 0, uplink=False) / 1e3


class Gateway:
    def __init__(self):
        self.tx = []                      # (start, end) of gateway transmissions
        self.rx1_free_at = 0.0            # 1% sub-band off-time
        self.rx2_free_at = 0.0            # 10% sub-band off-time
        self.busy_until = 0.0
        self.rx1_air = self.rx2_air = 0.0

    def overlaps_tx(self, a, b):
        return any(s < b and e > a for s, e in self.tx[-50:])

    def ack(self, end, sf):
        """Schedule an ACK for an uplink that ended at `end`; returns True if one is sent."""
        t1, d1 = end + RX1_DELAY, ack_air(sf)
        if t1 >= self.busy_until and t1 >= self.rx1_free_at:
            self.tx.append((t1, t1 + d1)); self.busy_until = t1 + d1
            self.rx1_free_at = t1 + 100 * d1; self.rx1_air += d1
            return True
        t2, d2 = end + RX2_DELAY, ack_air(12)
        if t2 >= self.busy_until and t2 >= self.rx2_free_at:
            self.tx.append((t2, t2 + d2)); self.busy_until = t2 + d2
            self.rx2_free_at = t2 + 10 * d2; self.rx2_air += d2
            return True
        return False


def simulate_recovery(n_nodes, sf, outage_h, slot_s=900.0, K_h=6.0, jitter_s=0.0, nbtrans=8, horizon_h=72.0,
                      seed=0, rssi_sd=8.0, live_batch_h=1.0):
    rng = np.random.default_rng(seed)
    radio = Radio(f"LoRaWAN SF{sf}", dr_step=False)
    per = radio.readings_per_frame()
    K = max(1, int(round(K_h * 3600 / slot_s)))
    T0 = outage_h * 3600.0                     # the outage spans [0, T0); time 0 = outage start
    horizon = T0 + horizon_h * 3600
    rssi = rng.normal(-110, rssi_sd, n_nodes)
    rank = rng.permutation(n_nodes)
    gw = Gateway()
    st = [{"buf": 0, "mode": "outage", "n_fail": 1, "energy": 0.0, "attempt": 0, "next_ok": 0.0,
           "last_gen": 0.0, "cleared": None, "frame_n": 0} for _ in range(n_nodes)]
    ev = []                                    # (time, seq, kind, node, payload)
    seq = [0]

    def push(t, kind, i, data=None):
        seq[0] += 1; heapq.heappush(ev, (t, seq[0], kind, i, data))

    # every node's first probe failed at t = 0 (the outage began); probes at slot multiples of the back-off
    for i in range(n_nodes):
        push(min(2, K) * slot_s + rng.uniform(0, jitter_s), "probe", i)
    active = []                                # uplinks in the air: (start, end, ch, sf, node, kind, nbytes, att)
    stats = {"attempts": 0, "ok": 0, "collided": 0, "halfduplex": 0, "noack": 0, "demod": 0}

    def generated(i, t):
        """readings generated by node i up to time t (one per slot) not yet counted"""
        n_new = int(t // slot_s) - int(st[i]["last_gen"] // slot_s)
        st[i]["last_gen"] = t
        st[i]["buf"] += max(0, n_new)

    def transmit(i, t, kind, nbytes, att):
        t = max(t, st[i]["next_ok"])
        a = air(sf, nbytes)
        st[i]["next_ok"] = t + 100 * a
        ch = int(rng.integers(CHANNELS))
        push(t, "tx_start", i, (t, t + a, ch, kind, nbytes, att))

    while ev:
        t, _, kind, i, data = heapq.heappop(ev)
        if t > horizon:
            break
        s = st[i]
        if kind == "probe":
            generated(i, t)
            transmit(i, t, "probe", LIVE_BYTES, 1)
        elif kind == "batch":
            generated(i, t)
            if s["mode"] == "normal" and s["buf"] > 0:
                s["mode"] = "drain"; s["frame_n"] = 0
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
            up = t >= T0                                          # gateway/backhaul back
            received = up
            rec = start >= T0
            # the concentrator locks onto the first 8 preambles: lost only if 8 others were already being
            # demodulated when this one started (exact ties broken by a random per-node rank)
            busy = [x for x in others if x[0] < start or (x[0] == start and rank[x[4]] < rank[i])]
            if received and len(busy) >= DEMODULATORS:
                received = False; stats["demod"] += rec
            if received and same and any(rssi[i] - rssi[x[4]] < CAPTURE_DB for x in same):
                received = False; stats["collided"] += rec
            if received and gw.overlaps_tx(start, end):
                received = False; stats["halfduplex"] += rec
            acked = received and gw.ack(end, sf)
            if start >= T0:                                        # recovery metrics: uplinks after the outage
                stats["noack"] += int(received and not acked)
                stats["attempts"] += 1
                stats["ok"] += int(acked)
                s["energy"] += radio.attempt(True, acked, True, nbytes, 1)
            active[:] = [x for x in active if x[1] > t - 400]      # keep recent ones for overlap checks
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
                    wait = min(2 ** s["n_fail"], K) * slot_s
                    push(t + wait + rng.uniform(0, jitter_s), "probe", i)
            else:                                                  # a bulk frame
                if acked:
                    s["buf"] -= min(per, s["buf"])
                    generated(i, t)
                    if s["buf"] > 0:
                        transmit(i, t, "frame", FRAME_OVERHEAD + READING_BYTES * min(per, s["buf"]), 1)
                    else:
                        if s["cleared"] is None and t >= T0:
                            s["cleared"] = t
                        s["mode"] = "normal"; push(t + live_batch_h * 3600, "batch", i)
                elif att < nbtrans:
                    transmit(i, t + rng.uniform(1, 3), "frame", nbytes, att + 1)
                else:                                              # give up: back to outage mode
                    s["mode"], s["n_fail"] = "outage", 1
                    push(t + min(2, K) * slot_s + rng.uniform(0, jitter_s), "probe", i)
        if all(x["cleared"] is not None for x in st):
            break
    clear = np.array([x["cleared"] if x["cleared"] is not None else np.inf for x in st]) - T0
    span = max(1.0, (min(t, horizon) - T0))
    return {"n_nodes": n_nodes, "sf": sf, "outage_h": outage_h, "jitter_s": jitter_s, "K_h": K_h, "seed": seed,
            "backlog_readings": int(outage_h * 3600 / slot_s),
            "cleared_share": float(np.isfinite(clear).mean()),
            "clear_all_h": float(clear.max() / 3600), "clear_median_h": float(np.median(clear) / 3600),
            "attempts": stats["attempts"], "pdr": stats["ok"] / max(stats["attempts"], 1),
            "collided_share": stats["collided"] / max(stats["attempts"], 1),
            "halfduplex_share": stats["halfduplex"] / max(stats["attempts"], 1),
            "noack_share": stats["noack"] / max(stats["attempts"], 1),
            "demod_share": stats["demod"] / max(stats["attempts"], 1),
            "rx1_duty": gw.rx1_air / span, "rx2_duty": gw.rx2_air / span,
            "energy_per_node_j": float(np.mean([x["energy"] for x in st]))}


def aloha_success(n_nodes, rate_per_s, airtime_s, duration_s, seed=0):
    """Pure-ALOHA check of the collision rule (one channel, one SF, equal power, no ACKs): share of frames
    that overlap no other frame. Theory: exp(-2G), G = n * rate * airtime."""
    rng = np.random.default_rng(seed)
    starts = np.sort(np.concatenate([rng.uniform(0, duration_s, rng.poisson(rate_per_s * duration_s))
                                     for _ in range(n_nodes)]))
    ok = np.ones(len(starts), bool)
    d = np.diff(starts) < airtime_s
    ok[1:] &= ~d; ok[:-1] &= ~d
    return ok.mean()


def main(out):
    rows = []
    for sf in (7, 12):
        for outage_h in (6, 24, 72):
            for n in (1, 10, 50, 100, 250, 500):
                for jitter in (0.0, 900.0, 3600.0):
                    for seed in range(3):
                        rows.append(simulate_recovery(n, sf, outage_h, jitter_s=jitter, seed=seed))
                print(f"SF{sf} outage {outage_h} h, N={n} done", flush=True)
    d = pd.DataFrame(rows)
    base = d[d.n_nodes == 1].groupby(["sf", "outage_h", "jitter_s"]).energy_per_node_j.mean()
    d["energy_vs_alone"] = d.apply(lambda r: r.energy_per_node_j / base[(r.sf, r.outage_h, r.jitter_s)], axis=1)
    d.to_csv(out, index=False, float_format="%.6g")
    g = d.groupby(["sf", "outage_h", "n_nodes", "jitter_s"]).mean(numeric_only=True)
    print(g[["cleared_share", "clear_all_h", "clear_median_h", "pdr", "collided_share", "halfduplex_share",
             "noack_share", "rx1_duty", "rx2_duty", "energy_vs_alone"]].round(3).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
