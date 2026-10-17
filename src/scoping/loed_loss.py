"""Per-device loss from LoRaWAN frame-counter gaps (LoED), using the union of all gateways.
A frame is 'received' if any gateway logged it with a valid CRC. Gaps in fcnt between consecutive
received frames = frames not heard by any LoED gateway (a proxy for loss: devices belong to other
operators, whose own gateways may have heard them). Only uplink data frames (mtype 010/100).
Usage: python -I src/scoping/loed_loss.py <dir with dd_mm_yyyy.csv>
"""
import sys, glob, pandas as pd, numpy as np
fs = sorted(f for f in glob.glob(sys.argv[1] + "/*.csv"))
d = pd.concat((pd.read_csv(f, usecols=["time", "device_address", "gateway", "crc_status", "mtype", "fcnt"], dtype=str) for f in fs))
d = d[(d.crc_status == "1") & d.mtype.isin(["010", "100"]) & (d.device_address != "-1")]
d["fcnt"] = d.fcnt.astype(int); d["time"] = pd.to_datetime(d.time, format="ISO8601", utc=True)
print("files", len(fs), "valid uplinks", len(d), "gateways", d.gateway.nunique(), "devices", d.device_address.nunique())
u = d.drop_duplicates(["device_address", "fcnt"]).sort_values(["device_address", "time"])
rows, bursts = [], []
for dev, g in u.groupby("device_address"):
    f = g.fcnt.values
    if len(f) < 50: continue
    df = np.diff(f)
    if (df <= 0).any(): f = f[np.r_[True, df > 0]]; df = np.diff(f)   # drop counter resets
    df = df[df < 1000]                                               # ignore resets/rejoins
    lost = (df - 1).clip(min=0)
    period = np.median(np.diff(g.time.values).astype("timedelta64[s]").astype(float))
    rows.append((dev, len(f), lost.sum() / (lost.sum() + len(f)), period))
    bursts += list(lost[lost > 0])
r = pd.DataFrame(rows, columns=["dev", "rx", "loss", "period_s"])
b = np.array(bursts)
print(f"devices with >=50 frames: {len(r)}; loss rate median {r.loss.median():.3f}, IQR {r.loss.quantile(.25):.3f}-{r.loss.quantile(.75):.3f}")
print(f"loss bursts: {len(b)}; length 1: {np.mean(b==1):.2f}, 2-5: {np.mean((b>=2)&(b<=5)):.2f}, >5: {np.mean(b>5):.2f}; "
      f"share of lost frames in bursts >5: {b[b>5].sum()/b.sum():.2f}")
# burstiness: P(lost | previous lost) vs P(lost), pooled
pl = b.sum() / (b.sum() + r.rx.sum()); cond = (b - 1).clip(min=0).sum() / b.sum()
print(f"pooled P(loss)={pl:.3f}  P(loss | previous lost)={cond:.3f}  (iid would give equal values)")

# Devices these gateways hear well (loss < 20%) are the closest proxy for a node's own link.
good = set(r.dev[r.loss < 0.2])
gb, grx = [], 0
for dev, g in u[u.device_address.isin(good)].groupby("device_address"):
    f = g.fcnt.values; df = np.diff(f); f = f[np.r_[True, df > 0]] if (df <= 0).any() else f
    df = np.diff(f); df = df[df < 1000]; lost = (df - 1).clip(min=0); gb += list(lost[lost > 0]); grx += len(f)
gb = np.array(gb)
if len(gb):
    p = gb.sum() / (gb.sum() + grx); c = (gb - 1).clip(min=0).sum() / gb.sum()
    print(f"well-heard devices: {len(good)}; pooled loss {p:.3f}; P(loss|prev lost) {c:.3f}; bursts {len(gb)}: "
          f"len1 {np.mean(gb==1):.2f}, 2-5 {np.mean((gb>=2)&(gb<=5)):.2f}, >5 {np.mean(gb>5):.2f}; max {gb.max()}")
