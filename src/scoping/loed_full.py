"""LoED (all days): split LoRaWAN frame loss into radio loss and gateway-down (system) outages.

Reads the daily CSVs straight from the zip (no extraction: the disk is nearly full), in chunks, keeping
only valid uplink data frames (crc_status 1, mtype 010 unconfirmed / 100 confirmed, known DevAddr).

1. Gateway activity: gateway g is 'up' in hour h if it logged any packet (valid or not) in that hour.
   Gateway downtime = runs of inactive hours between its first and last active hour.
   (A gateway whose logger stops looks the same as one whose backhaul fails; both are outages of the
   collection path, i.e. system outages from the device's point of view.)
2. Per device (DevAddr; a frame-counter decrease or a jump > 1000 is treated as a reset), each missing
   frame between two received frames is placed in time by linear interpolation and classified:
     'gateway_down' if none of the device's serving gateways (those that heard >= 20% of its frames)
                    was active in that hour;
     'radio'        otherwise.
3. Radio loss: per-device rate, burst lengths, P(loss | previous loss), for well-heard devices
   (radio loss rate < 20%, >= 200 received frames).
   Caveat: LoED gateways logged only during their own campaign windows (15-573 days, README), so long
   inactive runs are collection gaps, not failures. Runs <= 72 h are reported separately as plausible
   operational outages.
4. Co-loss: for radio losses of well-heard devices, the share that coincide (same minute) with a radio
   loss of another well-heard device served by the same gateway, vs the same statistic with each
   device's loss minutes shifted by a random offset (independence baseline).
5. Gateway silence: for each radio loss, whether the shared serving gateway logged nothing at all in that
   minute (a sub-hour gateway glitch rather than a lost frame), for coinciding vs isolated losses.
Usage: python -I src/scoping/loed_full.py <zip or directory> <out prefix>
"""
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

COLS = ["time", "device_address", "gateway", "crc_status", "mtype", "fcnt"]


def members(src):
    p = Path(src)
    if p.is_dir():
        for f in sorted(p.glob("*.csv")):
            yield f.name, lambda f=f: open(f, "rb")
    else:
        z = zipfile.ZipFile(p)
        for n in sorted(z.namelist()):
            if n.endswith(".csv") and "__MACOSX" not in n and not Path(n).name.startswith("._"):
                yield Path(n).name, lambda n=n: z.open(n)


def load(src):
    frames, gw_hours = [], set()
    dev_codes, gw_codes = {}, {}
    rec = defaultdict(int)                   # (dev, gw) -> receptions
    gw_minutes = defaultdict(list)           # gw -> arrays of active minutes
    for name, opener in members(src):
        with opener() as fh:
            for ch in pd.read_csv(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), usecols=COLS,
                                  dtype=str, chunksize=200_000):
                t = pd.to_datetime(ch.time, format="ISO8601", utc=True, errors="coerce")
                ok_t = t.notna().values
                ch = ch[ok_t]
                sec = (t[ok_t].astype("int64").values // 1_000_000_000).astype(np.int64)
                g = ch.gateway.map(lambda x: gw_codes.setdefault(x, len(gw_codes))).values.astype(np.int16)
                for gg in np.unique(g):
                    m = g == gg
                    gw_minutes[int(gg)].append(np.unique(sec[m] // 60).astype(np.int32))
                    for h in np.unique(sec[m] // 3600):
                        gw_hours.add((int(gg), int(h)))
                v = ((ch.crc_status == "1") & ch.mtype.isin(["010", "100"]) & (ch.device_address != "-1")).values
                fc = pd.to_numeric(ch.fcnt, errors="coerce").values
                v &= ~np.isnan(fc)
                dev = ch.device_address.values[v]
                dcode = np.fromiter((dev_codes.setdefault(d, len(dev_codes)) for d in dev), dtype=np.int32, count=len(dev))
                df = pd.DataFrame({"dev": dcode, "gw": g[v], "fcnt": fc[v].astype(np.int64), "t": sec[v]})
                for (dv, gg), n in df.groupby(["dev", "gw"]).size().items():
                    rec[(int(dv), int(gg))] += int(n)
                df = df.sort_values("t").drop_duplicates(["dev", "fcnt"])[["dev", "fcnt", "t"]]
                frames.append(df)
        print(f"  read {name}: {sum(len(f) for f in frames):,} unique frames so far", flush=True)
    minutes = {gg: np.unique(np.concatenate(a)) for gg, a in gw_minutes.items()}
    f = pd.concat(frames, ignore_index=True)
    return f, gw_hours, gw_codes, rec, minutes


def gateway_downtime(gw_hours, gw_codes):
    by_gw = defaultdict(list)
    for g, h in gw_hours:
        by_gw[g].append(h)
    names = {v: k for k, v in gw_codes.items()}
    rows, downs = [], []
    for g, hs in by_gw.items():
        hs = np.array(sorted(hs))
        gaps = np.diff(hs) - 1
        d = gaps[gaps > 0]
        downs += list(d)
        span = hs[-1] - hs[0] + 1
        rows.append({"gateway": names[g], "active_hours": len(hs), "span_hours": int(span),
                     "availability": len(hs) / span, "n_outages": len(d),
                     "median_outage_h": float(np.median(d)) if len(d) else 0, "max_outage_h": int(d.max()) if len(d) else 0})
    return pd.DataFrame(rows), np.array(downs, dtype=float)


def main(src, out):
    print("loading", src)
    f, gw_hours, gw_codes, rec_counts, gw_min = load(src)
    print(f"unique uplink frames: {len(f):,}; devices {f.dev.nunique():,}; gateways {len(gw_codes)}")
    gw_tab, downs = gateway_downtime(gw_hours, gw_codes)
    gw_tab.to_csv(f"{out}_gateways.csv", index=False)
    print(gw_tab.round(3).to_string(index=False))
    if len(downs):
        print(f"gateway inactive runs: {len(downs)}; median {np.median(downs):.0f} h; max {downs.max():.0f} h "
              f"(long runs are mostly campaign gaps, see docstring)")
        op = downs[downs <= 72]
        if len(op):
            print(f"  runs <= 72 h (plausible operational outages): {len(op)}; median {np.median(op):.0f} h; "
                  f"share >= 6 h {np.mean(op >= 6):.2f}; share of their down-hours in runs >= 24 h "
                  f"{op[op >= 24].sum() / op.sum():.2f}")

    # serving gateways per device
    rec = pd.DataFrame([(d, g, n) for (d, g), n in rec_counts.items()], columns=["dev", "gw", "n"])
    tot = rec.groupby("dev").n.transform("sum")
    serving = rec[rec.n >= 0.2 * tot].groupby("dev").gw.apply(list).to_dict()
    active = set(gw_hours)

    u = f.sort_values("t").drop_duplicates(["dev", "fcnt"]).sort_values(["dev", "t"])
    del f
    rows, radio_bursts, cond_num, cond_den, loss_minutes = [], [], 0, 0, defaultdict(list)
    for dev, g in u.groupby("dev"):
        fc, tt = g.fcnt.values, g.t.values
        if len(fc) < 200:
            continue
        sv = serving.get(dev, [])
        n_radio = n_down = 0
        prev_lost = False
        seq_radio = []
        for i in range(1, len(fc)):
            gap = fc[i] - fc[i - 1]
            if gap <= 0 or gap > 1000:          # counter reset / rejoin
                prev_lost = False
                continue
            for j in range(1, gap):
                tm = tt[i - 1] + (tt[i] - tt[i - 1]) * j / gap
                h = int(tm // 3600)
                up = any((s, h) in active for s in sv)
                if up:
                    n_radio += 1; seq_radio.append(1); loss_minutes[dev].append(int(tm // 60))
                else:
                    n_down += 1
            seq_radio.append(0)                 # the received frame
        n_rx = len(fc)
        rate = n_radio / (n_radio + n_rx)
        rows.append({"dev": dev, "rx": n_rx, "lost_radio": n_radio, "lost_gateway_down": n_down, "radio_loss": rate,
                     "serving_gateways": len(sv)})
        if rate < 0.2:
            s = np.array(seq_radio)
            cond_num += int(np.sum((s[1:] == 1) & (s[:-1] == 1))); cond_den += int(np.sum(s[:-1] == 1))
            b, run = [], 0
            for x in s:
                if x:
                    run += 1
                elif run:
                    b.append(run); run = 0
            radio_bursts += b
    d = pd.DataFrame(rows)
    d.to_csv(f"{out}_devices.csv", index=False)
    good = d[d.radio_loss < 0.2]
    print(f"\ndevices with >= 200 frames: {len(d)}; well-heard (radio loss < 20%): {len(good)}")
    tl = d.lost_radio.sum() + d.lost_gateway_down.sum()
    print(f"all devices: missing frames {tl:,}: radio {d.lost_radio.sum() / tl:.2f}, gateway-down {d.lost_gateway_down.sum() / tl:.2f}")
    p = good.lost_radio.sum() / (good.lost_radio.sum() + good.rx.sum())
    b = np.array(radio_bursts)
    print(f"well-heard devices: pooled radio loss {p:.3f}; median per device {good.radio_loss.median():.3f}; "
          f"P(loss | previous loss) {cond_num / max(cond_den, 1):.3f}")
    if len(b):
        print(f"radio-loss bursts: {len(b)}; length 1: {np.mean(b == 1):.2f}; 2-5: {np.mean((b >= 2) & (b <= 5)):.2f}; "
              f">5: {np.mean(b > 5):.2f}; max {b.max()}")
    gl = good.lost_gateway_down.sum() / (good.lost_gateway_down.sum() + good.lost_radio.sum())
    print(f"well-heard devices: share of missing frames during gateway-down hours {gl:.2f}")

    # co-loss among well-heard devices sharing a serving gateway
    rng = np.random.default_rng(20261011)
    gdev = defaultdict(list)
    for dev in good.dev:
        for s in serving.get(dev, []):
            gdev[s].append(dev)

    def coincidence(shift):
        hit = tot_ = 0
        for s, devs in gdev.items():
            if len(devs) < 2:
                continue
            mins = {dv: np.array(loss_minutes[dv]) + shift.get(dv, 0) for dv in devs}
            for dv in devs:
                others = set().union(*(set(mins[o].tolist()) for o in devs if o != dv))
                m = mins[dv]
                hit += sum(1 for x in m if x in others); tot_ += len(m)
        return hit / max(tot_, 1)

    obs = coincidence({})

    # sub-hour gateway silence at the minute of each radio loss
    co_sil = co_n = iso_sil = iso_n = 0
    for s_, devs in gdev.items():
        if len(devs) < 2 or s_ not in gw_min:
            continue
        mins = {dv: np.array(loss_minutes[dv], dtype=np.int64) for dv in devs}
        for dv in devs:
            m = mins[dv]
            if not len(m):
                continue
            others = np.unique(np.concatenate([mins[o] for o in devs if o != dv] or [np.array([], np.int64)]))
            co = np.isin(m, others)
            silent = ~np.isin(m, gw_min[s_])
            co_sil += int(np.sum(silent & co)); co_n += int(np.sum(co))
            iso_sil += int(np.sum(silent & ~co)); iso_n += int(np.sum(~co))
    print(f"gateway logged nothing in the minute of the loss: coinciding losses {co_sil / max(co_n, 1):.3f} "
          f"(n={co_n}); isolated losses {iso_sil / max(iso_n, 1):.3f} (n={iso_n})")
    shifts = [coincidence({dv: int(rng.integers(-7 * 1440, 7 * 1440)) for dv in good.dev}) for _ in range(5)]
    print(f"co-loss: share of radio losses coinciding (same minute) with another device's loss at a shared gateway: "
          f"observed {obs:.3f}; independence baseline (random shifts +-7 d, 5 draws) {np.mean(shifts):.3f} "
          f"[{min(shifts):.3f}, {max(shifts):.3f}]")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
