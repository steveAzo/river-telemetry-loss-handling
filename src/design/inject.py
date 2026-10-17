"""Injected-event benchmark (ground truth with known onsets) and event/alarm metrics.

Events are added to the REAL test-period series, so background dynamics, noise and data gaps
are real; only the event is synthetic.
  amplitude   a = amp * s_j(month), the series' robust residual scale in the event's month,
              defined as in Check B (amp = 5 equals Check B's event threshold)
  shapes      step : +-a for the whole duration, then back
              ramp : linear 0 -> +-a over the duration, then back (slow onset, harder)
  placement   test period only; >= 1 day after a segment start (detector baseline warm-up)
              and fully inside one segment; >= 3 days apart; >= 1 day from any Check B
              event; parameters take turns (each event touches ONE parameter, the hard case)
Injected values are rounded to the series' recording resolution, as a real logger would.
"""
import numpy as np
import pandas as pd

QUANT = None


def resolution(ds):
    global QUANT
    if ds.name == "Weija":                      # held-out set: measured by src/analysis/weija_phase1.py
        import json
        q = json.load(open("results/weija/phase1.json"))["T+EC+pH"]["quantization"]
        return np.array([float(q[p]["resolution"]) for p in ds.params])
    if QUANT is None:
        QUANT = pd.read_csv("results/phase1/quantization.csv")
        QUANT["code"] = QUANT.site.str.split().str[0]
    code = ds.name.split()[0] if ds.name.startswith("InWater") else ds.name.split()[1]
    q = QUANT[QUANT.site.str.startswith(code) | (QUANT.code == code)].set_index("param").resolution
    return np.array([float(q.get(p, 0.0)) for p in ds.params])


def hours(ds):
    return ds.t.dt.hour.to_numpy()


def noise_scale(ds, res=None):
    """(N, P) robust residual scale of the calendar month each step falls in, defined exactly
    as Check B defines events (centred 24-h median, per-month hour-of-day profile, MAD,
    floored at the resolution). Offline: the benchmark generator may use the whole series.
    An event of amp = 5 is therefore as large as Check B's own event threshold."""
    res = resolution(ds) if res is None else res
    w = max(3, int(round(24 * 60 / ds.step_min)))
    seg = np.cumsum(ds.seg_start); h = hours(ds)
    month = ds.t.dt.to_period("M").astype(str).to_numpy()
    out = np.zeros(ds.X.shape)
    for j in range(len(ds.params)):
        a = np.full(len(ds.X), np.nan)
        for s in np.unique(seg):
            m = seg == s
            x = pd.Series(ds.X[m, j])
            a[m] = (x - x.rolling(w, center=True, min_periods=w // 4).median()).to_numpy()
        df = pd.DataFrame({"a": a, "h": h, "m": month})
        df["r"] = df.a - df.groupby(["m", "h"]).a.transform("median")
        sc = df.groupby("m").r.transform(lambda r: 1.4826 * (r - r.median()).abs().median())
        out[:, j] = np.maximum(sc.fillna(sc.median()).to_numpy(), max(res[j], 1e-9))
    return out


def place(ds, dur_steps, n_max=60, seed=0, gap_days=3.0):
    """onset indices and parameter for each injected event"""
    rng = np.random.default_rng(seed)
    N, P = ds.X.shape
    spd = int(round(24 * 60 / ds.step_min))
    seg = np.cumsum(ds.seg_start)
    starts = np.flatnonzero(ds.seg_start)
    seg_first = starts[seg - 1]
    seg_last = np.r_[starts[1:], N][seg - 1] - 1
    ok = ds.test & (np.arange(N) - seg_first >= spd) & (np.arange(N) + dur_steps <= seg_last)
    if ds.events is not None and len(ds.events):
        t = ds.t.to_numpy()
        for _, e in ds.events.iterrows():
            lo = np.searchsorted(t, np.datetime64(e.start) - np.timedelta64(1, "D"))
            hi = np.searchsorted(t, np.datetime64(e.end) + np.timedelta64(1, "D"))
            ok[max(0, lo - dur_steps):hi] = False
    cand = np.flatnonzero(ok)
    rng.shuffle(cand)
    chosen = []
    for c in cand:
        if all(abs(c - o) >= gap_days * spd for o in chosen):
            chosen.append(c)
        if len(chosen) >= n_max:
            break
    chosen = sorted(chosen)
    return [(o, i % P) for i, o in enumerate(chosen)]


def inject(ds, shape, amp, dur_min, seed=0, n_max=60, scale=None, res=None):
    """returns (X_injected, events) with events = DataFrame(param_idx, s, e, sign, a)"""
    res = resolution(ds) if res is None else res
    scale = noise_scale(ds, res) if scale is None else scale
    d = max(1, int(round(dur_min / ds.step_min)))
    rng = np.random.default_rng(seed + 1000)
    X = ds.X.copy(); rows = []
    for o, j in place(ds, d, n_max, seed):
        sign = rng.choice([-1.0, 1.0]); a = amp * scale[o, j]
        bump = np.full(d, a) if shape == "step" else a * np.arange(1, d + 1) / d
        X[o:o + d, j] += sign * bump
        if res[j] > 0:
            X[o:o + d, j] = np.round(X[o:o + d, j] / res[j]) * res[j]
        rows.append({"j": j, "s": o, "e": o + d, "sign": sign, "a": a})
    return X, pd.DataFrame(rows)


def eval_events(ev, res, step_min):
    """per injected event: informed (a report carrying p while the event lasts), its delay,
    and alarm (the detector flagged p while the event lasts) with its delay"""
    out = []
    for _, e in ev.iterrows():
        s, end, j = int(e.s), int(e.e), int(e.j)
        snt = np.flatnonzero(res.sent[s:end, j])
        al = np.flatnonzero(res.alarm[s:end, j]) if res.alarm is not None else np.array([])
        out.append({"j": j, "informed": len(snt) > 0, "inf_delay": snt[0] * step_min if len(snt) else np.nan,
                    "alarmed": len(al) > 0, "al_delay": al[0] * step_min if len(al) else np.nan})
    return pd.DataFrame(out)
