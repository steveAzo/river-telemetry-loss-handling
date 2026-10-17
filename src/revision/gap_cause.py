"""Review C1/E1: what can the water-quality records say about the CAUSE of a missing reading?

Neither record has a node status log, so the cause cannot be observed directly. Two partial checks are possible:

Weija (one node, several sensor streams on one logger and one uplink). A conductivity slot in which ANOTHER
stream delivered a genuine reading had a live node and a working uplink: the conductivity gap is a sensor or
processing gap, not a delivery gap. Only genuine rows count as deliveries: not flagged as imputed, at most 3
decimals for T/EC/pH (the logger's precision; more decimals = unflagged interpolation), and not inside a run
of >= 6 points on one straight line (interpolation), as in src/data/clean_weija.py.
  -> 'node-silent' slots: no genuine reading from any stream (node off, logger down, or uplink down: these
     cannot be told apart);
  -> 'EC-only' slots: conductivity missing while another stream delivered (link up: not a delivery gap).

InWaterSense (two nodes, one shared gateway with one GPRS link, in node 2's manhole). While node 2 was
operating (May-Aug 2015), a node-1 gap during which node 2 kept delivering cannot be a gateway, GPRS or
server outage: it is node-1-specific (node power, sensor, or the node-gateway radio link). A gap in which
both nodes were silent is consistent with a shared-path outage (or a shared power failure, or coincidence).

Outputs: results/revision/gap_cause_*.csv and a log. Usage (from Paper2/):
  python -I src/revision/gap_cause.py results/revision/gap_cause
"""
import glob
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, "src/data")
from clean_weija import MAX_DECIMALS, ramp_mask  # noqa: E402
from design.sitedata import record_up  # noqa: E402

WEIJA = "data/weija_raw"
DECIMAL_PARAMS = {"conductivity", "ph", "temperature"}        # logger precision <= 3 decimals


def runs(mask):
    """Lengths and start indices of runs of True."""
    m = np.r_[False, np.asarray(mask, bool), False]
    d = np.diff(m.astype(int))
    st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return en - st, st


def share_in_long(lengths, slot_s, L_h):
    lengths = np.asarray(lengths, float)
    return lengths[lengths * slot_s >= L_h * 3600].sum() / lengths.sum() if lengths.sum() else np.nan


def genuine_rows(f):
    d = pd.read_csv(f, parse_dates=["Datetime"], dtype={"Value": str})
    param = d.Parameter.iloc[0]
    d["dec"] = d.Value.str.split(".").str[1].fillna("").str.len()
    d["v"] = d.Value.astype(float)
    d = d[d.Was_Imputed.astype(str) != "True"]
    if param in DECIMAL_PARAMS:
        d = d[d.dec <= MAX_DECIMALS]
    keep = []
    for _, g in d.groupby("Probe Name"):
        g = g.sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)
        if len(g) > 2:
            g = g[~ramp_mask(g.Datetime, g.v)]
        keep.append(g)
    g = pd.concat(keep)
    return param, g.Datetime.sort_values().reset_index(drop=True)


def weija_links():
    """(slot_s, v0.1 conductivity link, genuine-EC link, node link = any stream genuine, per-stream masks)."""
    raw = pd.read_csv(f"{WEIJA}/conductivity_cleaned_records.csv", parse_dates=["Datetime"])
    t_v01 = raw[raw.Was_Imputed.astype(str) != "True"].Datetime.drop_duplicates().sort_values()
    slot = float(np.median(t_v01.diff().dt.total_seconds().dropna()))
    t0, _, up_v01 = record_up((t_v01.astype("int64") // 1_000_000_000).to_numpy(), slot)
    n = len(up_v01)
    idx = lambda t: np.rint(((t.astype("int64") // 1_000_000_000).to_numpy() - t0) / slot).astype(int)
    alive = np.zeros(n, bool); per = {}
    for f in sorted(glob.glob(f"{WEIJA}/*_cleaned_records.csv")):
        p, t = genuine_rows(f)
        k = idx(t); k = k[(k >= 0) & (k < n)]
        m = np.zeros(n, bool); m[k] = True
        per[p] = m; alive |= m
    return slot, up_v01, per["conductivity"], alive, per


def weija(out):
    slot, up_v01, ec, alive, per = weija_links()
    n = len(up_v01)
    rows = []
    for lab, up in (("EC stream, v0.1 record (non-imputed rows)", up_v01), ("EC stream, genuine rows only", ec),
                    ("node: any stream, genuine rows (node-silent)", alive)):
        L, _ = runs(~up)
        rows.append({"record": lab, "slot_min": slot / 60, "slots": n, "loss": (~up).mean(), "gaps": len(L),
                     "S_6h": share_in_long(L, slot, 6), "S_1d": share_in_long(L, slot, 24),
                     "longest_d": L.max() * slot / 86400 if len(L) else 0})
    miss = ~up_v01
    rows_cls = {"EC missing (v0.1 record)": int(miss.sum()),
                "  of which node-silent": int((miss & ~alive).sum()),
                "  of which another stream delivered (link up)": int((miss & alive).sum())}
    # per v0.1 gap: share of its slots in which another stream delivered
    L, S = runs(miss)
    g = pd.DataFrame({"start_slot": S, "len": L, "h": L * slot / 3600,
                      "alive_share": [alive[s:s + l].mean() for s, l in zip(S, L)]})
    g.to_csv(f"{out}_weija_gaps.csv", index=False)
    long = g[g.h >= 6]
    print("\n== Weija (conductivity grid, %.1f-min slots)" % (slot / 60))
    print(pd.DataFrame(rows).round(4).to_string(index=False))
    for k, v in rows_cls.items():
        print(f"  {k}: {v} ({v / max(rows_cls['EC missing (v0.1 record)'], 1):.3f})")
    rows_cls["long_gaps_alive_share"] = float(np.average(long.alive_share, weights=long.len))
    rows_cls["long_gaps_n"] = int(len(long))
    print(f"  v0.1 gaps >= 6 h: {len(long)}; lost slots in them {int(long.len.sum())}; "
          f"share of those slots with another stream delivering {np.average(long.alive_share, weights=long.len):.3f}")
    print("  per-stream genuine coverage of the grid: " + ", ".join(f"{p} {m.mean():.3f}" for p, m in per.items()))
    pd.DataFrame(rows).to_csv(f"{out}_weija_records.csv", index=False)
    return pd.DataFrame(rows), rows_cls


def inws(out):
    d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    sec = lambda s: (s.astype("int64") // 1_000_000_000).to_numpy()
    t0, slot, up1 = record_up(sec(d[d.node == 1].t), 611.0)
    n = len(up1)
    t2 = sec(d[d.node == 2].t)
    k2 = np.rint((t2 - t0) / slot).astype(int); k2 = k2[(k2 >= 0) & (k2 < n)]
    up2 = np.zeros(n, bool); up2[k2] = True
    # node 2's operating window: its first to its last delivery before September 2015 (2 stray cycles in Dec)
    last2 = sec(d[(d.node == 2) & (d.t < "2015-09-01")].t).max()
    w = np.zeros(n, bool); w[: int(np.rint((last2 - t0) / slot)) + 1] = True
    # node 2 'alive near this slot': delivered within +-1 slot (its own cadence jitters by a slot)
    near2 = up2 | np.r_[False, up2[:-1]] | np.r_[up2[1:], False]
    m1 = ~up1 & w
    print("\n== InWaterSense (node-1 grid, 611-s slots), node 2's window %s .. %s (%.1f d)"
          % (pd.to_datetime(t0, unit="s"), pd.to_datetime(last2, unit="s"), w.sum() * slot / 86400))
    print(f"  node 1 loss in window {m1.sum() / w.sum():.3f}; node 2 present near a slot: "
          f"when node 1 delivered {near2[up1 & w].mean():.3f}, when node 1 missed {near2[m1].mean():.3f}")
    L, S = runs(m1)
    g = pd.DataFrame({"start": pd.to_datetime(t0 + S * slot, unit="s"), "len": L, "h": L * slot / 3600,
                      "node2_share": [near2[s:s + l].mean() for s, l in zip(S, L)]})
    g.to_csv(f"{out}_inws_gaps.csv", index=False)
    cls = {"node-1 missing slots in window": int(m1.sum()),
           "  node 2 delivering (node-1-specific)": int((m1 & near2).sum()),
           "  node 2 silent too (shared path, shared power, or coincidence)": int((m1 & ~near2).sum())}
    for k, v in cls.items():
        print(f"  {k}: {v} ({v / max(cls['node-1 missing slots in window'], 1):.3f})")
    for lo, hi in ((0, 1), (1, 6), (6, 24), (24, 1e9)):
        gg = g[(g.h > lo) & (g.h <= hi)] if lo else g[g.h <= hi]
        if len(gg):
            print(f"  node-1 gaps {lo}-{hi if hi < 1e9 else 'inf'} h: {len(gg):4d}, lost slots {int(gg.len.sum()):6d}, "
                  f"share of their slots with node 2 delivering {np.average(gg.node2_share, weights=gg.len):.3f}")
    # Attribution. Node 2 is also silent for its own reasons, so "both silent" includes coincidences. Model: a
    # share pi of node-1 missing slots have a shared cause (node 2 surely silent); the rest are node-1-specific,
    # and node 2 is silent in them at its background rate b, measured LOCALLY (+-24 h around each gap, at
    # slots where node 1 delivered). Then P(node 2 silent | node-1 missing) = pi + (1 - pi) b.
    day = int(round(86400 / slot))
    for lo, hi, lab in ((0, 1e9, "all gaps"), (0, 6, "gaps < 6 h"), (6, 1e9, "gaps >= 6 h"), (24, 1e9, "gaps >= 1 d")):
        num = den = 0.0; obs = []; base = []
        for s_, l_ in zip(S, L):
            h = l_ * slot / 3600
            if not (lo <= h < hi):
                continue
            a, b_ = max(0, s_ - day), min(n, s_ + l_ + day)
            ref = up1[a:b_] & w[a:b_]
            if ref.sum() < 10:
                continue
            obs.append((1 - near2[s_:s_ + l_].mean(), l_)); base.append(((~near2[a:b_])[ref].mean(), l_))
        if not obs:
            continue
        o = np.average([x for x, _ in obs], weights=[l for _, l in obs])
        bb = np.average([x for x, _ in base], weights=[l for _, l in base])
        pi = (o - bb) / (1 - bb) if bb < 1 else np.nan
        print(f"  attribution, {lab}: node 2 silent {o:.3f} during node-1 gaps vs {bb:.3f} locally -> "
              f"shared-cause share pi = {pi:.2f}, node-1-specific {1 - pi:.2f}")
        cls[f"pi_shared {lab}"] = round(float(pi), 3)
    # whole record: share of node 1's lost slots that fall inside node 2's window
    L_all, _ = runs(~up1)
    cls["window_share_of_all_lost"] = float(m1.sum() / (~up1).sum())
    cls["node2_silent_when_n1_missing"] = float(1 - near2[m1].mean())
    print(f"  share of ALL node-1 lost slots inside node 2's window: {m1.sum() / (~up1).sum():.3f} "
          f"(the rest, Sep 2015 - Jan 2016, has no second node to compare with)")
    return g, cls


def main(out):
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import json
    _, w_cls = weija(out)
    _, i_cls = inws(out)
    with open(f"{out}_summary.json", "w") as f:
        json.dump({"weija": w_cls, "inws": i_cls}, f, indent=2)


if __name__ == "__main__":
    main(sys.argv[1])
