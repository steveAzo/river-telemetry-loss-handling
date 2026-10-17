"""Site signals, outage links and the detector harness for the design evaluation
(docs/DESIGN_EVAL_PLAN.md). Detector and event injection are Paper 1's code, copied unchanged
(detector.py, inject.py); this module only prepares their inputs the way Paper 1 did.
"""
import bisect
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .detector import make_detector
from .inject import hours as _hours

PARAMS = ["T", "EC", "pH", "DO"]
SEG_GAP_MIN = 60            # Paper 1: new segment after a gap > 60 min
TRAIN_FRAC = 0.2            # Paper 1: first 20 % of the time span = training
TOL = {"T": 0.2, "DO": 2.0, "pH": 0.1}      # Paper 1 L2 tolerance; EC = 2 % of the site median
# Deviation D5 (2026-10-17): readings are recorded in decimal steps (pH, T: 0.1), so an error of exactly one
# tolerance (7.3 - 7.2 = 0.0999..96, but 7.4 - 7.3 = 0.1000..05) was counted in or out by floating-point
# noise. "Within tolerance" is |error| <= tol, inclusive, with this absolute slack, everywhere (scoring and trigger).
TOL_EPS = 1e-9


def within_tol(err, tol):
    """|error| <= tolerance, inclusive, robust to decimal round-off (D5)."""
    return np.abs(err) <= np.asarray(tol, dtype=float) + TOL_EPS
DETECTOR = dict(mode="lag", lag_min=120, k=3, H=8, c=6)   # Paper 1 frozen choice (detector_choice.json)


@dataclass
class Dataset:                      # Paper 1's Dataset (src/sim/data.py), copied
    name: str
    params: list
    t: pd.Series
    X: np.ndarray
    seg_start: np.ndarray
    test: np.ndarray
    step_min: float
    events: pd.DataFrame = field(default=None)

    def train_segments(self, j):
        seg = np.cumsum(self.seg_start)
        tr = ~self.test
        return [self.X[(seg == s) & tr, j] for s in np.unique(seg[tr])]


@dataclass
class Site:
    name: str
    step_s: float
    grid_t: np.ndarray       # int64 seconds since epoch, regular grid over the record
    Xg: np.ndarray           # (n_grid, 4) readings on the grid; a row with any NaN = sensor gap
    ds: Dataset              # complete cycles only (Paper 1's form), for injection and detection
    cyc2grid: np.ndarray     # grid index of each complete cycle
    test_g: np.ndarray       # grid slots in the test period
    res: np.ndarray          # estimated recording resolution per parameter


def resolution_from_data(x):
    """Most common positive gap between sorted distinct values (rounded to 1e-6)."""
    v = np.unique(np.round(x[np.isfinite(x)], 6))
    d = np.round(np.diff(v), 6)
    d = d[d > 0]
    if len(d) == 0:
        return 0.0
    vals, cnt = np.unique(d, return_counts=True)
    return float(vals[np.argmax(cnt)])


def load_site(site, root="data/clean/usgs"):
    d = pd.read_csv(f"{root}/{site}.csv", parse_dates=["t"])
    d["t"] = d.t.dt.tz_convert("UTC").dt.tz_localize(None) if d.t.dt.tz is not None else d.t
    d = d.sort_values("t").drop_duplicates("t")
    step = float(d.t.diff().dt.total_seconds().median())
    ts = (d.t.astype("int64") // 1_000_000_000).to_numpy()
    t0 = ts[0]
    k = np.rint((ts - t0) / step).astype(int)
    n = k.max() + 1
    Xg = np.full((n, len(PARAMS)), np.nan)
    Xg[k] = d[PARAMS].to_numpy(float)
    grid_t = t0 + np.arange(n) * int(step)
    complete = np.isfinite(Xg).all(axis=1)
    ci = np.flatnonzero(complete)
    tt = pd.Series(pd.to_datetime(grid_t[ci], unit="s"))
    gap = tt.diff().dt.total_seconds().div(60)
    seg_start = (gap.isna() | (gap > SEG_GAP_MIN)).to_numpy()
    tst = (tt >= tt.iloc[0] + TRAIN_FRAC * (tt.iloc[-1] - tt.iloc[0])).to_numpy()
    ds = Dataset(f"USGS {site}", PARAMS, tt, Xg[ci], seg_start, tst, step / 60, None)
    res = np.array([resolution_from_data(ds.X[:, j]) for j in range(len(PARAMS))])
    test_g = np.zeros(n, bool); test_g[ci[tst]] = True
    return Site(site, step, grid_t, Xg, ds, ci, test_g, res)


def train_hours(ds):               # Paper 1 (src/sim/roc_detector.py)
    h = _hours(ds); seg = np.cumsum(ds.seg_start); tr = ~ds.test
    return [h[(seg == s) & tr] for s in np.unique(seg[tr])]


def run_detector(ds, X, res, trh, cfg=DETECTOR):   # Paper 1 (src/sim/roc_detector.py)
    h = _hours(ds); N, P = X.shape
    al = np.zeros((N, P), bool)
    for j in range(P):
        d = make_detector(ds.step_min, ds.train_segments(j), res[j], trh, cfg)
        al[:, j] = d.run(X[:, j], h, ds.seg_start)
    return al


def run_detector_on_subset(site, X, keep, res, trh, cfg=DETECTOR):
    """Server-side detection on the readings that arrived (unconfirmed reporting): the detector is
    trained exactly as on the node (training data is assumed delivered or provisioned), then run
    on the delivered complete cycles only, with a new segment after a gap > 60 min (Paper 1)."""
    ds = site.ds
    idx = np.flatnonzero(keep)
    out = np.zeros((len(ds.X), X.shape[1]), bool)
    if len(idx) == 0:
        return out
    tt = ds.t.iloc[idx].reset_index(drop=True)
    gap = tt.diff().dt.total_seconds().div(60)
    seg_start = (gap.isna() | (gap > SEG_GAP_MIN)).to_numpy()
    h = tt.dt.hour.to_numpy()
    for j in range(X.shape[1]):
        d = make_detector(ds.step_min, ds.train_segments(j), res[j], trh, cfg)
        out[idx, j] = d.run(X[idx, j], h, seg_start)
    return out


# ------------------------------------------------------------------ outage records -> links
def record_up(times_s, slot_s):
    """Delivery record -> (t0, slot, up[]) on the record's own slot grid."""
    t = np.unique(np.asarray(times_s, dtype=np.int64))
    k = np.rint((t - t[0]) / slot_s).astype(int)
    up = np.zeros(k.max() + 1, bool); up[k] = True
    return t[0], slot_s, up


def map_link(rec, grid_t, offset_s):
    """Link state at each site slot: the record's state at the same elapsed time (+ offset),
    wrapped circularly over the record's span; nearest record slot."""
    t0, slot, up = rec
    span = len(up) * slot
    el = (grid_t - grid_t[0] + offset_s) % span
    k = np.minimum(np.rint(el / slot).astype(int), len(up) - 1)
    return up[k]


def load_records():
    """InWaterSense node 1, Weija conductivity (non-imputed): every missing slot = link down (causes not
    separable). UVA: system outages only (see below)."""
    recs = {}
    c = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    t = (c[c.node == 1].t.astype("int64") // 1_000_000_000).to_numpy()
    recs["InWaterSense"] = record_up(t, 611.0)
    w = pd.read_csv("data/weija_raw/conductivity_cleaned_records.csv", parse_dates=["Datetime"])
    w = w[w.Was_Imputed.astype(str) != "True"].Datetime.drop_duplicates().sort_values()
    slot = float(np.median(w.diff().dt.total_seconds().dropna()))
    recs["Weija"] = record_up((w.astype("int64") // 1_000_000_000).to_numpy(), slot)
    # UVA: the causes are separable (src/scoping/uva_loss.py). Link down = SYSTEM outage (no sensor at
    # all reached the database in a 10-min bin); sensor04's radio losses are applied per attempt instead
    # (UVA_P_RADIO), because a retry after a radio loss usually succeeds. (Plan deviation D1.)
    u = pd.read_parquet("data/uva_lorawan/lorawan_combined_dataset.parquet", columns=["Timestamp"])
    ts = (u.Timestamp.astype("int64") // 1_000_000).to_numpy()
    b = np.unique((ts - ts.min()) // 600)
    recs["UVA"] = record_up(ts.min() + b * 600, 600.0)
    return recs


UVA_P_RADIO = 0.0308       # sensor04: radio-class missing frames / all frames (results/scoping/uva_loss_sensors.csv)
P_RADIO = {"none": 0.0, "InWaterSense": 0.0, "Weija": 0.0, "UVA": UVA_P_RADIO}


# ------------------------------------------------------------------ real-time picture
def server_picture(xg, arr_abs, grid_t, spd, scored):
    """Value the server shows at each slot time, from what has ARRIVED by then (plan §4.5).
    xg: true readings on the grid (NaN = no reading); arr_abs: absolute arrival time (s) per slot,
    inf if never; spd: slots per day. Returns the estimate at the scored slots."""
    n = len(xg)
    has = np.isfinite(xg) & np.isfinite(arr_abs)
    a = np.where(has, arr_abs, np.inf)
    order = np.argsort(a, kind="stable")
    a_sorted = a[order]
    cummax_idx = np.maximum.accumulate(order)               # latest slot index among the first k arrivals
    tau = grid_t[scored]
    k = np.searchsorted(a_sorted, tau, side="right") - 1    # number of arrivals by tau, minus one
    est = np.full(len(tau), np.nan)
    ok = k >= 0
    s_star = np.where(ok, cummax_idx[np.maximum(k, 0)], -1)
    sc_idx = np.flatnonzero(scored)
    for q in np.flatnonzero(ok):
        s = s_star[q]; t = sc_idx[q]
        if s == t:
            est[q] = xg[t]; continue
        v = xg[s]
        tl, sl = t - spd, s - spd
        if tl >= 0 and sl >= 0 and has[tl] and has[sl] and a[tl] <= tau[q] and a[sl] <= tau[q]:
            v = xg[s] + (xg[tl] - xg[sl])
        est[q] = v
    return est


# ------------------------------------------------------------------ bounded-error trigger (Part 2)
def make_trigger(Xg, tol, spd, slot_s=None, ack="network"):
    """Node-side copy of the server's estimator (`server_picture`). The node knows which of its readings
    have been delivered (confirmed uploads), so it can compute exactly what the server shows at slot t and
    fire when any parameter is off by more than its tolerance. Order-independent (Part 3): it checks each
    needed reading's own arrival, so it stays exact when uploads are not FIFO (newest-first packing).
    Rows with any missing parameter are not readings (as in the runner).
    slot_s (deviation D4): if given, a reading counts as available only once it has physically ARRIVED
    (slot time + delay <= now); a multi-frame upload under the duty cycle can arrive after later slots.
    ack (review C6): 'network' = the confirmed-uplink ACK is taken as proof that the server holds the reading
    (exact for NB-IoT, whose ACK is the application's reply; for LoRaWAN it proves only network-server
    reception). 'application' = the node does not know whether the application server already holds a
    reading that the network server acknowledged, until an application-level ACK for it reaches the node in
    the downlink of a LATER successful uplink (LoRaWAN Class A: the application server queues the ACK, the
    network server sends it in the receive window of the node's next uplink). The server then shows one of
    two states, so the node fires if EITHER is out of tolerance: the bound holds in both. Needs slot_s; the
    simulator passes the times of successful uplinks (trigger.wants_ok_times)."""
    if ack not in ("network", "application"):
        raise ValueError(ack)
    if ack == "application" and slot_s is None:
        raise ValueError("ack='application' needs slot_s")
    valid = np.isfinite(Xg).all(axis=1)
    tol = np.asarray(tol, dtype=float)
    st = {"net": -1, "app": -1}

    def known(idx, arr, t, cut):
        """mask over idx: reading arrived by now (cut None) or before the application cut-off time"""
        a = np.isfinite(arr[idx])
        if cut is not None:
            return a & (idx * slot_s + np.where(a, arr[idx], 0) < cut)
        if slot_s is not None:
            return a & (idx * slot_s + np.where(a, arr[idx], 0) <= t * slot_s)
        return a

    def estimate(t, arr, key, cut):
        lo = st[key] + 1                         # the latest known index can only grow: rescan above it
        if lo < t:
            idx = np.arange(lo, t)
            hit = np.flatnonzero(known(idx, arr, t, cut) & valid[lo:t])
            if len(hit):
                st[key] = lo + hit[-1]
        s = st[key]
        if s < 0:
            return None
        est = Xg[s].copy()
        tl, sl = t - spd, s - spd
        if tl >= 0 and sl >= 0 and valid[tl] and valid[sl] and known(np.array([tl, sl]), arr, t, cut).all():
            est = est + (Xg[tl] - Xg[sl])
        return est

    def off(t, est):
        return est is None or bool(np.any(~within_tol(Xg[t] - est, tol)))   # fire beyond the tolerance (D5)

    def trig(t, arr, ok_times=None):
        est = estimate(t, arr, "net", None)
        if ack == "application":
            k = bisect.bisect_right(ok_times, t * slot_s)
            cut = ok_times[k - 1] if k else -np.inf          # ACKs can only cover arrivals before this uplink
            est_app = estimate(t, arr, "app", cut)
        if not valid[t]:
            return False
        if ack == "application":
            return off(t, est) or off(t, est_app)
        return off(t, est)
    trig.wants_ok_times = ack == "application"
    return trig
