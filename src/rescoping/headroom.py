"""Rescoping gate G2 (docs/RESCOPING_2026-10-31.md): how much can ANY outage-probing schedule gain over v0.3?

Replays every real delivery gap as the v0.3 design sees it, and compares v0.3's probe schedule with the best
schedule that exists for that record.

Gap alignment (as simulate(..., 'batch_events') in src/energy/loss_handling.py): the design uploads every M slots
(1 h). A gap of slots [a, a+k) is noticed only at the first upload slot b in it ((b+1) % M == 0); a gap without
an upload slot costs nothing extra. From b the node is in outage mode: probe i at b + p_i, and the gap's remaining
length is r = a + k - b slots (the link is back from slot b + r). A probe at offset p fails if p < r.
  failed probes  = #{i: p_i < r}
  detection delay = (first p_i >= r) - r slots: how long after the link returns the backlog starts to move
  (alarms are excluded: in v0.3 an alarm probes at once, outside the schedule)
Schedules
  v0.3 (cap K): p_1 = 1, p_{i+1} = p_i + min(2^i, K); v0.3 uses K = 6 h. Other caps and fixed intervals are shown.
  optimal: for a cost c per failed probe and 1 per slot of delay, the schedule minimising the expected cost over the
    record's empirical distribution of r (backward dynamic programming over the time of the last failed probe; the
    optimal-checking problem of Barlow, Hunter and Proschan 1963 with an empirical distribution). Sweeping c gives
    the frontier. In-sample = fitted and scored on the same gaps (optimistic bound on any schedule); cross-validated =
    fitted on one half of the gaps, scored on the other (2-fold, 20 random splits).
Energy: failed probes per day x the energy of one failed confirmed 20-B attempt on each radio (Radio.attempt), as
a share of the design's energy per day on the same record (results/confirm/an2024_energy.csv, E_bounded).
Outputs: results/rescoping/headroom_frontier.csv, headroom_summary.csv.
Usage (from Paper2/): python -I src/rescoping/headroom.py
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from design.sitedata import load_records  # noqa: E402
from energy.loss_handling import LIVE_BYTES, Radio  # noqa: E402
from revision.run_loss_revision import traces  # noqa: E402

OUT = "results/rescoping"
RADIOS = {"LoRaWAN SF7": Radio("LoRaWAN SF7"), "LoRaWAN SF12": Radio("LoRaWAN SF12"),
          "NB-IoT N211 RAI (search 10 s)": Radio("NB-IoT N211 RAI", t_search=10.0)}
E_TRACE = {"InWaterSense": "InWaterSense", "Weija (node record)": "Weija", "UVA": "UVA"}


def records():
    for name, up, slot in traces():
        if name != "Weija (v0.1 EC record)":                # the node record is the one the confirmatory run used
            yield name, up, slot
    _, slot, up = load_records()["UVA"]
    yield "UVA", up, slot


def remaining(up, M):
    """Remaining gap length r (slots) at the moment the design notices each gap; noticed gaps only."""
    m = np.r_[False, ~up, False]
    d = np.diff(m.astype(int))
    out = []
    for a, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
        b = a + (-(a + 1)) % M                              # first slot >= a with (b + 1) % M == 0
        if b < e:
            out.append(e - b)
    return np.array(out, int)


def backoff_schedule(K, H):
    p, i, out = 1, 1, []
    while p <= H:
        out.append(p)
        p += min(2 ** i, K)
        i += 1
    out.append(p)
    return np.array(out)


def fixed_schedule(m, H):
    return np.arange(1, H + m + 1, m)


def score(sched, r):
    """(mean failed probes per gap, mean detection delay per gap in slots, readings-weighted delay)."""
    j = np.searchsorted(sched, r)                           # first probe index with p >= r
    fails = j
    delay = sched[j] - r
    return fails.mean(), delay.mean(), (delay * r).sum() / r.sum()


def optimal_schedule(r_fit, c, H, tail):
    """Probe offsets minimising E[c * failed probes + delay] for r ~ empirical(r_fit). Last failed probe at s
    (so r > s); next probe at n > s. cost(s, n) = E[(n - r) 1{r <= n} | r > s] + P(r > n | r > s)(c + V(n)).
    Beyond the longest fitted gap the node probes every `tail` slots (a gap longer than any it has seen)."""
    return schedule_from_weights(np.bincount(r_fit, minlength=H + 2).astype(float), c, H, tail)


def lognormal_weights(r_fit, H):
    """Smoothed alternative to the raw counts: a lognormal fitted to log(r) (moments), discretised on 1..H+1;
    the mass beyond H + 1 is dropped (handled by the tail rule)."""
    from math import erf, log, sqrt
    mu, sd = np.log(r_fit).mean(), max(np.log(r_fit).std(), 1e-3)
    cdf = lambda x: 0.5 * (1 + erf((log(x) - mu) / (sd * sqrt(2))))
    w = np.zeros(H + 2)
    w[1:] = [cdf(n + 0.5) - cdf(max(n - 0.5, 1e-9)) for n in range(1, H + 2)]
    return w


def schedule_from_weights(cnt, c, H, tail):
    """As optimal_schedule, for any non-negative weights cnt[r], r = 0..H+1."""
    F = np.cumsum(cnt)                                      # F[n] = #{r <= n}
    G = np.cumsum(cnt * np.arange(H + 2))                   # G[n] = sum of r over r <= n
    N = F[-1]
    S = N - F                                               # S[n] = #{r > n}
    V = np.zeros(H + 2)
    nxt = np.full(H + 2, H + 1)
    for s in range(H, -1, -1):
        if S[s] <= 1e-12 * N:
            continue
        n = np.arange(s + 1, H + 2)
        delay = n * (F[n] - F[s]) - (G[n] - G[s])
        tot = delay + S[n] * (c + V[n])
        k = int(np.argmin(tot))
        V[s] = tot[k] / S[s]
        nxt[s] = n[k]
    sched, s = [], 0
    while s <= H:
        s = nxt[s]
        sched.append(s)
        if S[s] <= 1e-12 * N:
            break
    return np.r_[sched, np.arange(s + tail, H + 2 * tail, tail)]


def main():
    import os
    os.makedirs(OUT, exist_ok=True)
    e_design = pd.read_csv("results/confirm/an2024_energy.csv").set_index(["trace", "radio"])["E_bounded"]
    rows, summ = [], []
    rng = np.random.default_rng(20261101)
    for name, up, slot in records():
        M = max(1, int(round(3600 / slot))); K6 = max(1, int(round(6 * 3600 / slot)))
        r = remaining(up, M)
        days = len(up) * slot / 86400
        H = int(r.max()) + 1
        h = slot / 3600
        def add(kind, par, sched, rr=r, extra=None):
            f, d, dw = score(sched, rr)
            rows.append({"record": name, "kind": kind, "param": par, "fails_per_day": f * len(rr) / days,
                         "delay_h": d * h, "delay_h_readings": dw * h, **(extra or {})})
        for Kh in (1, 2, 6, 12, 24, 48):
            add("backoff", Kh, backoff_schedule(max(1, int(round(Kh * 3600 / slot))), H))
        for mh in (0.5, 1, 2, 6, 12, 24):
            add("fixed", mh, fixed_schedule(max(1, int(round(mh * 3600 / slot))), H))
        add("every_slot", 0, fixed_schedule(1, H))
        cs = np.geomspace(0.05, 2000, 40)
        for c in cs:
            add("optimal_insample", c, optimal_schedule(r, c, H, K6))
        # cross-validated frontier: fit on a random half, score on the other half, average over splits
        if len(r) >= 10:
            for c in cs:
                fs, ds, dws = [], [], []
                for _ in range(20):
                    idx = rng.permutation(len(r)); A, B = idx[: len(r) // 2], idx[len(r) // 2:]
                    for fit, test in ((A, B), (B, A)):
                        f, d, dw = score(optimal_schedule(r[fit], c, H, K6), r[test])
                        fs.append(f); ds.append(d); dws.append(dw)
                rows.append({"record": name, "kind": "optimal_cv", "param": c, "fails_per_day": np.mean(fs) * len(r) / days,
                             "delay_h": np.mean(ds) * h, "delay_h_readings": np.mean(dws) * h})
            # the same with a lognormal fitted on the training half (what a deployed node could carry)
            for c in cs:
                fs, ds, dws = [], [], []
                for _ in range(20):
                    idx = rng.permutation(len(r)); A, B = idx[: len(r) // 2], idx[len(r) // 2:]
                    for fit, test in ((A, B), (B, A)):
                        f, d, dw = score(schedule_from_weights(lognormal_weights(r[fit], H), c, H, K6), r[test])
                        fs.append(f); ds.append(d); dws.append(dw)
                rows.append({"record": name, "kind": "lognormal_cv", "param": c, "fails_per_day": np.mean(fs) * len(r) / days,
                             "delay_h": np.mean(ds) * h, "delay_h_readings": np.mean(dws) * h})
        fr = pd.DataFrame([x for x in rows if x["record"] == name])
        v03 = fr[(fr.kind == "backoff") & (fr.param == 6)].iloc[0]
        for kind in ("optimal_insample", "optimal_cv", "lognormal_cv"):
            o = fr[fr.kind == kind].sort_values("delay_h")
            if o.empty:
                continue
            # fewest failed probes among optimal schedules that are no slower than v0.3, and vice versa
            same_delay = o[o.delay_h <= v03.delay_h + 1e-9].fails_per_day.min()
            same_fails = o[o.fails_per_day <= v03.fails_per_day + 1e-9].delay_h.min()
            for rl, radio in RADIOS.items():
                e_fail = radio.attempt(True, False, False, LIVE_BYTES, 1)
                E = e_design.get((E_TRACE[name], rl), np.nan)
                summ.append({"record": name, "frontier": kind, "radio": rl, "gaps_noticed": len(r), "days": days,
                             "v03_fails_per_day": v03.fails_per_day, "v03_delay_h": v03.delay_h,
                             "opt_fails_at_v03_delay": same_delay, "opt_delay_h_at_v03_fails": same_fails,
                             "e_fail_j": e_fail, "design_j_per_day": E,
                             "v03_probe_share": v03.fails_per_day * e_fail / E,
                             "max_saving_share": (v03.fails_per_day - same_delay) * e_fail / E})
    pd.DataFrame(rows).to_csv(f"{OUT}/headroom_frontier.csv", index=False)
    s = pd.DataFrame(summ)
    s.to_csv(f"{OUT}/headroom_summary.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(s.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
