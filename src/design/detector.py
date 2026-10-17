"""Online event detector run by the NODE on its own true readings (causal: past data only).

Why: a bounded DPS never reports a change smaller than delta, so at loose tolerances it misses
statistically clear events (Phase 2, F6: capture ~0.63 at L4 for every predictor). The detector
flags departures from the node's learned normal behaviour and forces a report.

Deliberately different from the offline Check B labeller (centred 24-h median, monthly MAD):
  baseline b_t  = median of the node's last 24 h of true readings (causal; lags slow drifts)
  profile p[h]  = typical b-relative anomaly at hour-of-day h, EWMA-updated (memory ~ `mem_days`)
                  so the diel shape follows the season (winter training != summer test)
  scale s       = EWMA of |residual| * 1.2533 (= sigma for Gaussian), memory ~ `mem_days`,
                  floored at the sensor's recording resolution
  z_t           = (x_t - b_t - p[h]) / s, clipped to +-c  (one spike adds at most c - k)
  two-sided CUSUM (Page 1954):  S+ = max(0, S+ + z - k),  S- = max(0, S- - z - k)
  alarm when S+ > H or S- > H; then EVENT state until |z| < 2 for `calm_steps`, CUSUM reset.
  Profile and scale are NOT updated in the event state (events must not teach "normal").
Typical-length glitches (< 30 min, Check B) cannot alarm on their own if H > 2(c - k).
"""
from collections import deque

import numpy as np

GAUSS_MAD = 1.2533          # E|z| = 0.798 sigma for a Gaussian


class CusumDetector:
    def __init__(self, step_min, train, res=0.0, k=1.0, H=8.0, c=4.0, mem_days=7.0,
                 calm_min=60.0, hours_train=None, mode="median", lag_min=60.0):
        """train: list of 1-D training segments (true values); hours_train: matching list of
        hour-of-day int arrays (used to initialise the profile). res: recording resolution.
        mode "median": residual = x - median(last 24 h) - profile[h]
        mode "lag"   : residual = x - (x[t-m] + profile[h_t] - profile[h_{t-m}]), m = lag_min
                       (diel-aware m-step forecast; much smaller residual on smooth rivers)"""
        self.mode, self.m = mode, max(1, int(round(lag_min / step_min)))
        self.w = max(3, int(round(24 * 60 / step_min)))
        self.k, self.H, self.c, self.res = k, H, c, res
        spd = 24 * 60 / step_min
        self.b_s = 1.0 / (mem_days * spd)                      # per step
        self.b_p = 1.0 / (mem_days * spd / 24)                 # per visit of an hour bin
        self.calm_steps = max(1, int(round(calm_min / step_min)))
        self.buf = deque(maxlen=self.w)
        self.prof = np.zeros(24)
        self.s = res if res > 0 else 1e-6
        if train is not None:
            self._init(train, hours_train)
        self.reset_history()

    def _init(self, train, hours):
        """profile and scale from the training period, using the same causal baseline"""
        R, Hh, E = [], [], []
        for seg, hr in zip(train, hours):
            for i in range(self.w // 4, len(seg)):
                R.append(seg[i] - np.median(seg[max(0, i - self.w):i])); Hh.append(hr[i])
        if not R:
            return
        R, Hh = np.asarray(R), np.asarray(Hh)
        for h in range(24):
            if (Hh == h).any():
                self.prof[h] = np.median(R[Hh == h])
        if self.mode == "median":
            e = R - self.prof[Hh]
        else:
            for seg, hr in zip(train, hours):
                for i in range(self.m, len(seg)):
                    E.append(seg[i] - seg[i - self.m] - self.prof[hr[i]] + self.prof[hr[i - self.m]])
            e = np.asarray(E) if E else np.zeros(1)
        self.s = max(1.4826 * np.median(np.abs(e - np.median(e))), self.res, 1e-9)

    def reset_history(self):
        """data gap: 24-h baseline must be rebuilt; learned profile and scale persist"""
        self.buf.clear(); self.hbuf = deque(maxlen=self.m + 1); self.Sp = self.Sm = 0.0
        self.event, self.calm = False, 0

    def step(self, x, hour, med=None):
        """advance with true reading x at hour-of-day `hour`; returns True on a NEW alarm.
        med: median of the last 24 h (computed here if None; `run` passes it precomputed)"""
        alarm = False
        ready = len(self.buf) >= self.w // 4
        if ready:
            if med is None:
                med = np.median(self.buf)
            rp = x - med - self.prof[hour]                          # profile-learning residual
            if self.mode == "median":
                r = rp
            elif len(self.hbuf) >= self.m:
                xm, hm = self.hbuf[-self.m]
                r = x - xm - self.prof[hour] + self.prof[hm]
            else:
                ready = False
        if ready:
            z = min(max(r / self.s, -self.c), self.c)
            if self.event:
                self.calm = self.calm + 1 if abs(z) < 2 else 0
                if self.calm >= self.calm_steps:
                    self.event, self.Sp, self.Sm = False, 0.0, 0.0
            else:
                self.Sp = max(0.0, self.Sp + z - self.k)
                self.Sm = max(0.0, self.Sm - z - self.k)
                if self.Sp > self.H or self.Sm > self.H:
                    alarm, self.event, self.calm = True, True, 0
                else:                                          # learn "normal" only when calm
                    cp = (3.0 if self.mode == "median" else 10.0) * self.s
                    self.prof[hour] += self.b_p * min(max(rp, -cp), cp)
                    rc = min(max(r, -3 * self.s), 3 * self.s)
                    self.s = max((1 - self.b_s) * self.s + self.b_s * GAUSS_MAD * abs(rc), self.res, 1e-9)
        self.buf.append(x); self.hbuf.append((x, hour))
        return alarm

    def run(self, x, hours, seg_start):
        """fast offline-equivalent of calling step() over a whole series (used by the ROC study;
        identical alarms, verified in tests): the 24-h medians are precomputed per segment."""
        import pandas as pd
        seg = np.cumsum(seg_start)
        med = pd.Series(x).groupby(seg).transform(
            lambda s: s.shift(1).rolling(self.w, min_periods=self.w // 4).median()).to_numpy()
        al = np.zeros(len(x), bool)
        for t in range(len(x)):
            if seg_start[t]:
                self.reset_history()
            m = med[t]
            al[t] = self.step(x[t], hours[t], None if np.isnan(m) else m)
        return al


class DetectorBank:
    """OR of several detectors (e.g. a fast lag detector for steps + a slow 24-h-median detector
    for drifts). New alarm if any member raises one; in the event state if any member is."""

    def __init__(self, step_min, train, res=0.0, hours_train=None, bank=()):
        self.d = [CusumDetector(step_min, train, res, hours_train=hours_train, **cfg) for cfg in bank]

    @property
    def event(self):
        return any(d.event for d in self.d)

    def reset_history(self):
        for d in self.d:
            d.reset_history()

    def step(self, x, hour, med=None):
        return any([d.step(x, hour, med) for d in self.d])      # list: every member advances

    def run(self, x, hours, seg_start):
        out = np.zeros(len(x), bool)
        for d in self.d:
            out |= d.run(x, hours, seg_start)
        return out


def make_detector(step_min, train, res, hours_train, cfg):
    """cfg: dict for one CusumDetector, or {"bank": [cfg, cfg, ...]}"""
    if "bank" in cfg:
        return DetectorBank(step_min, train, res, hours_train, cfg["bank"])
    return CusumDetector(step_min, train, res, hours_train=hours_train, **cfg)
