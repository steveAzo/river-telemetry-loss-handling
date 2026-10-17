"""Review M3 (frame-counter processing) and M4 (UVA outage-classification sensitivity).

UVA (src/scoping/uva_loss.py is the analysis being checked):
  M3  receptions vs unique (sensor, FCnt) frames (multi-gateway duplicates and retransmissions share an FCnt);
      counter decreases and jumps (resets / rejoins), and how the missing-frame count changes with the jump
      threshold (1,000 / 5,000 / 50,000); reporting cadence per sensor and month (seconds per FCnt step), to find
      periods in which a sensor changed its cadence (a cadence change does not create missing frames, because
      FCnt counts frames, not time, but it changes what one missing frame means in time).
  M4  the 'system down' rule (no sensor reached the database in a bin) for bins of 5, 10, 15 and 30 min:
      number of system outages, median and longest duration, share of system down-time in outages >= 1 day,
      and the share of missing frames classed as system losses.
LoED (src/scoping/loed_full.py): resets and duplicates per device are counted by `loed` below, from the zip.
Usage (from Paper2/): python -I src/revision/lorawan_checks.py results/revision/lorawan [uva|loed]
"""
import sys

import numpy as np
import pandas as pd

SLOT_S = 300
GBIN = 1800


def runs_bool(a):
    m = np.r_[0, (~a).astype(int), 0]
    d = np.diff(m)
    return np.flatnonzero(d == -1) - np.flatnonzero(d == 1)


def uva(out):
    d = pd.read_parquet("data/uva_lorawan/lorawan_combined_dataset.parquet")
    d = d.rename(columns={"Timestamp": "t", "Sensor Alias": "s", "Gateway Alias": "g", "Counter (-)": "fcnt"})
    n_rx_all = len(d)
    d = d.dropna(subset=["fcnt"])
    d["fcnt"] = d.fcnt.astype(np.int64)
    d["ts"] = d.t.astype("int64") // 1_000_000
    t0, t1 = d.ts.min(), d.ts.max()
    u = d.sort_values("ts").drop_duplicates(["s", "fcnt"]).sort_values(["s", "ts"])
    print(f"UVA receptions {n_rx_all:,} (without FCnt {n_rx_all - len(d):,}); unique (sensor, FCnt) frames {len(u):,}; "
          f"receptions per frame {len(d) / len(u):.3f}")
    # same (sensor, FCnt) received at clearly different times = a counter reuse, not a multi-gateway duplicate
    spread = d.groupby(["s", "fcnt"]).ts.agg(lambda x: x.max() - x.min())
    print(f"  (sensor, FCnt) received more than 60 s apart (counter reuse after a reset): {(spread > 60).sum():,} "
          f"of {len(spread):,}")
    rows, cad = [], []
    for s, x in u.groupby("s"):
        fc, ts = x.fcnt.to_numpy(), x.ts.to_numpy()
        dfc, dts = np.diff(fc), np.diff(ts)
        r = {"sensor": s, "frames": len(fc), "decreases": int((dfc <= 0).sum())}
        for thr in (1000, 5000, 50000):
            ok = (dfc > 1) & (dfc <= thr)
            r[f"jumps_gt_{thr}"] = int((dfc > thr).sum())
            r[f"missing_thr_{thr}"] = int((dfc[ok] - 1).sum())
        step = dts[dfc == 1]
        r["cadence_s_median"] = float(np.median(step)) if len(step) else np.nan
        r["cadence_share_4_6min"] = float(np.mean((step >= 240) & (step <= 360))) if len(step) else np.nan
        rows.append(r)
        mo = pd.to_datetime(ts[1:][dfc == 1], unit="s").to_period("M")
        for m, v in pd.Series(step).groupby(mo):
            cad.append({"sensor": s, "month": str(m), "cadence_s_median": float(v.median()), "n": len(v)})
    r = pd.DataFrame(rows); c = pd.DataFrame(cad)
    r.to_csv(f"{out}_uva_counters.csv", index=False); c.to_csv(f"{out}_uva_cadence.csv", index=False)
    print(r.to_string(index=False))
    off = c[(c.cadence_s_median < 240) | (c.cadence_s_median > 360)]
    print(f"  sensor-months whose median cadence is outside 4-6 min: {len(off)} of {len(c)}")
    if len(off):
        print(off.to_string(index=False))
    for thr in (1000, 5000, 50000):
        print(f"  missing frames with jump threshold {thr}: {r[f'missing_thr_{thr}'].sum():,}")

    # ---- M4: system bins
    gw = {}
    ng = (t1 - t0) // GBIN + 1
    for g, x in d.groupby("g"):
        a = np.zeros(ng, bool); a[((x.ts - t0) // GBIN).unique()] = True
        gw[g] = a
    cnt = d.groupby(["s", "g"]).size()
    serving = {s: [g for g, n in cnt[s].items() if n >= 0.2 * cnt[s].sum()] for s in cnt.index.levels[0]}
    rows = []
    for sysbin in (300, 600, 900, 1800):
        nb = (t1 - t0) // sysbin + 1
        up = np.zeros(nb, bool); up[((d.ts - t0) // sysbin).unique()] = True
        dur = runs_bool(up) * sysbin / 3600
        n_cls = {"system": 0, "gateway": 0, "radio": 0}
        for s, x in u.groupby("s"):
            fc, ts = x.fcnt.to_numpy(), x.ts.to_numpy()
            for i in np.flatnonzero((np.diff(fc) > 1) & (np.diff(fc) <= 5000)):
                gap = fc[i + 1] - fc[i]
                tm = ts[i] + (ts[i + 1] - ts[i]) * np.arange(1, gap) / gap
                c_sys = ~up[np.clip(((tm - t0) // sysbin).astype(int), 0, nb - 1)]
                gi = np.clip(((tm - t0) // GBIN).astype(int), 0, ng - 1)
                c_gw = np.all([~gw[g][gi] for g in serving[s]], axis=0) & ~c_sys
                n_cls["system"] += int(c_sys.sum()); n_cls["gateway"] += int(c_gw.sum())
                n_cls["radio"] += int((~c_sys & ~c_gw).sum())
        tot = sum(n_cls.values())
        rows.append({"bin_min": sysbin / 60, "availability": up.mean(), "system_outages": len(dur),
                     "median_h": float(np.median(dur)), "max_h": float(dur.max()),
                     "downtime_share_ge_1d": float(dur[dur >= 24].sum() / dur.sum()),
                     "missing_system_share": n_cls["system"] / tot, "missing_gateway_share": n_cls["gateway"] / tot,
                     "missing_radio_share": n_cls["radio"] / tot})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(f"{out}_uva_bins.csv", index=False)


def loed(out):
    sys.path.insert(0, "src/scoping")
    import loed_full
    f, gw_hours, gw_codes, rec, minutes = loed_full.load("data/loed_full/LoED_full.zip")
    n_frames = len(f)
    u = f.sort_values("t").drop_duplicates(["dev", "fcnt"]).sort_values(["dev", "t"])
    rows = []
    for dev, g in u.groupby("dev"):
        fc = g.fcnt.to_numpy()
        if len(fc) < 200:
            continue
        dfc = np.diff(fc)
        r = {"dev": dev, "frames": len(fc), "decreases": int((dfc <= 0).sum())}
        for thr in (100, 1000, 10000):
            ok = (dfc > 1) & (dfc <= thr)
            r[f"jumps_gt_{thr}"] = int((dfc > thr).sum()); r[f"missing_thr_{thr}"] = int((dfc[ok] - 1).sum())
        rows.append(r)
    r = pd.DataFrame(rows)
    r.to_csv(f"{out}_loed_counters.csv", index=False)
    print(f"LoED frame records after per-chunk dedup {n_frames:,}; unique (device, FCnt) {len(u):,}; "
          f"devices with >= 200 frames {len(r)}")
    print(f"  devices with any counter decrease: {(r.decreases > 0).sum()}; median decreases per such device "
          f"{r.decreases[r.decreases > 0].median() if (r.decreases > 0).any() else 0}")
    for thr in (100, 1000, 10000):
        print(f"  missing frames with jump threshold {thr}: {r[f'missing_thr_{thr}'].sum():,}")


if __name__ == "__main__":
    which = sys.argv[2:] or ["uva"]
    for w in which:
        {"uva": uva, "loed": loed}[w](sys.argv[1])
