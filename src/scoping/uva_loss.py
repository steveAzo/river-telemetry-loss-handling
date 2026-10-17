"""UVA LoRaWAN deployment (Nikseresht et al., BuildSys 2025; LibraData doi:10.18130/V3/RFTICK, CC BY 4.0):
decompose missing frames into system outages, gateway outages and radio loss; fit outage models; test rain.

Deployment: 10 sensors sending every 5 min, 3 gateways (A, B outdoor; C indoor), TTN sandbox, US915,
9 Feb 2024 - 11 Jun 2025. The operators ran the network continuously, so gaps are real outages of the
path to the database (unlike LoED, whose gateways logged only in campaign windows).

1. A frame of sensor s is 'received' if any gateway logged it. Missing frames = frame-counter gaps
   (a decrease, or a jump > 5000, is a reset/rejoin and is not counted).
2. System down in a 10-min bin: no frame from any sensor reached the database (with ~20 frames expected
   per bin, this does not happen by chance). This includes TTN, internet and the operators' MQTT/
   database pipeline: everything between the gateways and the stored record.
3. Gateway g down in a 30-min bin: g logged nothing while the system was up.
4. Each missing frame (time interpolated between its neighbours) is classed 'system' if the system was
   down, 'gateway' if all of the sensor's serving gateways (>= 20% of its frames) were down, else 'radio'.
   Outage runs (consecutive missing frames of one sensor) take the class of the majority of their frames.
5. Rain: per sensor-gateway pair, link loss = share of the sensor's received frames that this gateway
   missed while it was up. Compared between 5-min intervals with and without rain (rain = increase of the
   accumulated-rain counter), with a per-pair paired comparison.
Usage: python -I src/scoping/uva_loss.py results/scoping/uva_loss
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src/scoping")
from outage_models import FITTERS, long_share  # noqa: E402

SLOT_S = 300


def main(out):
    d = pd.read_parquet("data/uva_lorawan/lorawan_combined_dataset.parquet")
    d = d.rename(columns={"Timestamp": "t", "Sensor Alias": "s", "Gateway Alias": "g", "Counter (-)": "fcnt"})
    d = d.dropna(subset=["fcnt"])
    d["fcnt"] = d.fcnt.astype(np.int64)
    d["ts"] = d.t.astype("int64") // 1_000_000                       # seconds
    t0, t1 = d.ts.min(), d.ts.max()
    print(f"receptions {len(d):,}; sensors {d.s.nunique()}; gateways {d.g.nunique()}; "
          f"{pd.to_datetime(t0, unit='s')} .. {pd.to_datetime(t1, unit='s')}")

    # ---- system and gateway availability
    sysbin = 600
    nb = (t1 - t0) // sysbin + 1
    sys_up = np.zeros(nb, bool); sys_up[((d.ts - t0) // sysbin).unique()] = True
    gbin = 1800
    ng = (t1 - t0) // gbin + 1
    sys_up_g = np.zeros(ng, bool); sys_up_g[((d.ts - t0) // gbin).unique()] = True
    gw_up = {}
    for g, x in d.groupby("g"):
        a = np.zeros(ng, bool); a[((x.ts - t0) // gbin).unique()] = True
        gw_up[g] = a
    runs = lambda a: np.diff(np.flatnonzero(np.diff(np.r_[0, (~a).astype(int), 0])))[::2]
    sd = runs(sys_up) * sysbin / 3600
    print(f"\nsystem availability (10-min bins): {sys_up.mean():.4f}; outages {len(sd)}; "
          f"median {np.median(sd):.2f} h; max {sd.max():.1f} h; down-hours in outages >= 24 h {sd[sd >= 24].sum() / sd.sum():.2f}")
    for g, a in sorted(gw_up.items()):
        dn = (~a) & sys_up_g
        r = runs(np.where(sys_up_g, a, True)) * gbin / 3600   # gateway-only downtime while the system was up
        print(f"  {g}: up {a[sys_up_g].mean():.4f} of system-up time; gateway-only outages {len(r)}, "
              f"median {np.median(r) if len(r) else 0:.1f} h, max {r.max() if len(r) else 0:.1f} h")

    # ---- serving gateways per sensor
    cnt = d.groupby(["s", "g"]).size()
    serving = {s: [g for g, n in cnt[s].items() if n >= 0.2 * cnt[s].sum()] for s in cnt.index.levels[0]}

    # ---- per-sensor missing frames and outage runs
    u = d.sort_values("ts").drop_duplicates(["s", "fcnt"]).sort_values(["s", "ts"])
    rows, run_rows = [], []
    for s, x in u.groupby("s"):
        fc, ts = x.fcnt.values, x.ts.values
        n_cls = {"system": 0, "gateway": 0, "radio": 0}
        for i in range(1, len(fc)):
            gap = fc[i] - fc[i - 1]
            if gap <= 1 or gap > 5000:
                continue
            k = gap - 1
            tm = ts[i - 1] + (ts[i] - ts[i - 1]) * np.arange(1, gap) / gap
            c_sys = ~sys_up[np.clip(((tm - t0) // sysbin).astype(int), 0, nb - 1)]
            gi = np.clip(((tm - t0) // gbin).astype(int), 0, ng - 1)
            c_gw = np.all([~gw_up[g][gi] for g in serving[s]], axis=0) & ~c_sys
            cls = np.where(c_sys, "system", np.where(c_gw, "gateway", "radio"))
            for c in n_cls:
                n_cls[c] += int(np.sum(cls == c))
            vals, cts = np.unique(cls, return_counts=True)
            run_rows.append({"s": s, "len": k, "cls": vals[np.argmax(cts)]})
        rows.append({"s": s, "rx": len(fc), **n_cls, "serving": ",".join(serving[s])})
    r = pd.DataFrame(rows); r["missing"] = r[["system", "gateway", "radio"]].sum(axis=1)
    r["loss"] = r.missing / (r.missing + r.rx)
    runs_df = pd.DataFrame(run_rows)
    r.to_csv(f"{out}_sensors.csv", index=False); runs_df.to_csv(f"{out}_runs.csv", index=False)
    print("\nper sensor (frames):"); print(r.round(4).to_string(index=False))
    tot = r[["system", "gateway", "radio"]].sum()
    print(f"\nall missing frames {int(tot.sum()):,}: " + ", ".join(f"{c} {tot[c] / tot.sum():.3f}" for c in tot.index))
    print(f"pooled loss {r.missing.sum() / (r.missing.sum() + r.rx.sum()):.4f}")

    # ---- outage-length statistics and models (5-min slots), by class
    L = runs_df.len.values.astype(float)
    print(f"\noutage runs {len(L)}; length 1: {np.mean(L == 1):.2f}; median {np.median(L):.0f} slots; max {L.max():.0f} "
          f"({L.max() * SLOT_S / 86400:.1f} d)")
    for lab, LL in [("all", L)] + [(c, runs_df[runs_df.cls == c].len.values.astype(float)) for c in ("radio", "gateway", "system")]:
        if len(LL) == 0:
            continue
        h = 3600 / SLOT_S
        print(f"  {lab:8s} runs {len(LL):6d}  lost slots {int(LL.sum()):7d}  median {np.median(LL):5.0f}  "
              f"share of lost slots in runs >= 1 h {LL[LL >= h].sum() / LL.sum():.2f}, >= 6 h {LL[LL >= 6 * h].sum() / LL.sum():.2f}, "
              f">= 24 h {LL[LL >= 24 * h].sum() / LL.sum():.2f}")
    n_slots = int((r.rx.sum() + r.missing.sum()))
    print("  model fits on all runs (AIC; share >= 6 h / >= 24 h):")
    for name, fit in FITTERS.items():
        par, ll, k = fit(L)
        print(f"    {name:7s} AIC {2 * k - 2 * ll:10.1f}  {long_share(name, par, 72, n_slots):.2f} / {long_share(name, par, 288, n_slots):.2f}")

    # ---- rain vs link loss per sensor-gateway pair
    w = pd.read_parquet("data/uva_lorawan/deployment_weather.parquet")
    w["ts"] = w.Timestamp.astype("int64") // 1_000_000
    acc = w["Accumulated Rain ( IN )"].values
    inc = np.diff(acc, prepend=acc[0])
    w["rain"] = np.where(inc > 0, inc, 0.0)        # a decrease = counter reset
    print(f"\nweather rows {len(w):,}; intervals with rain {np.mean(w.rain > 0):.3f}; accumulated-rain decreases (resets) {int(np.sum(inc < 0))}")
    rain_bin = dict(zip(w.ts // SLOT_S, w.rain > 0))
    u2 = u.copy(); u2["b"] = u2.ts // SLOT_S
    u2["rain"] = u2.b.map(rain_bin)
    heard = d.groupby(["s", "fcnt"]).g.apply(set)
    out_rows = []
    for s in u2.s.unique():
        xs = u2[(u2.s == s) & u2.rain.notna()]
        hs = heard.loc[s].reindex(xs.fcnt.values).values
        gi = np.clip(((xs.ts.values - t0) // gbin).astype(int), 0, ng - 1)
        for g in serving[s]:
            up = gw_up[g][gi]
            miss = np.array([g not in h for h in hs])
            for rain in (False, True):
                m = up & (xs.rain.values == rain)
                if m.sum() >= 200:
                    out_rows.append({"s": s, "g": g, "rain": rain, "n": int(m.sum()), "link_loss": miss[m].mean()})
    rl = pd.DataFrame(out_rows)
    rl.to_csv(f"{out}_rain.csv", index=False)
    pv = rl.pivot_table(index=["s", "g"], columns="rain", values="link_loss").dropna()
    if len(pv):
        diff = pv[True] - pv[False]
        from scipy import stats
        wt = stats.wilcoxon(pv[True], pv[False]) if len(pv) >= 6 else None
        print(f"link loss per pair, dry vs rain: median {pv[False].median():.4f} vs {pv[True].median():.4f}; "
              f"pairs with more loss in rain {np.mean(diff > 0):.2f} of {len(pv)}; median difference {diff.median():+.4f}"
              + (f"; Wilcoxon p = {wt.pvalue:.3g}" if wt else ""))


if __name__ == "__main__":
    main(sys.argv[1])
