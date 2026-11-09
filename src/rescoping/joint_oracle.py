"""Rescoping screen S8 (docs/RESCOPING_2026-10-31.md): JOINT oracle bound for OARS.

Question (user, 2026-11-03): OARS decides sensing, reporting, retrying, probing and backfill jointly and
adaptively, while the earlier screens tested components one at a time. How much TOTAL node energy could a
clairvoyant joint policy save over v0.3 at the same delivery and fidelity? No causal policy, however
sophisticated, can save more.

Total node energy per day = sleep floor + sensing + radio.
  v0.3   sleep floor + 96 probe wake-ups/day (15-min slots) + v0.3's simulated radio energy on the real outage
         traces (results/confirm/an2023_energy.csv, E_bounded: radio attempts with the host awake during each,
         median over the 2023 development sites; traces InWaterSense, Weija, UVA, none).
  oracle same sleep floor + only the wake-ups a clairvoyant node needs to keep the server's held DO and pH
         within the v0.3 tolerance (sample exactly when the hold would break) + one frame in every hour that
         contains a needed reading, at the CHEAPER of the unconfirmed and confirmed frame energies, never lost,
         no failed probes, no outage cost (backlog frames free). Its radio energy is capped at v0.3's radio energy with NO outages
         (the 'none' trace), so the oracle also escapes every outage cost v0.3 pays. Every choice favours the oracle, so a FAIL is conclusive.
Probe warm-up per wake-up is uncertain (src/energy/params.py T_SENSE): 1, 5, 15, 30 s.
PASS RULE (fixed before running; service A = v0.3 service: every reading delivered within the hour plus the real-time bound; the first run wrongly let the oracle deliver only the needed readings, kept as service B for contrast): the oracle saves >= 30% of total node energy over v0.3 (median site) at the
typical warm-up (5 s) on at least two of the three radios. The saving is also split into sensing and radio parts.
Data: USGS 2023 development sites only.
Usage (from Paper2/): python -I src/rescoping/joint_oracle.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from energy import params as P  # noqa: E402
from energy.loss_handling import FRAME_OVERHEAD, LIVE_BYTES, READING_BYTES, Radio  # noqa: E402

OUT = "results/rescoping"
TOL_DO, TOL_PH = 2.0, 0.1
RADIOS = {"LoRaWAN SF7": Radio("LoRaWAN SF7"), "LoRaWAN SF12": Radio("LoRaWAN SF12"),
          "NB-IoT N211 RAI (search 10 s)": Radio("NB-IoT N211 RAI", t_search=10.0)}


def oracle_need(path):
    """samples/day and needed hours/day for a clairvoyant zero-order-hold node (scored slots only)"""
    d = pd.read_csv(path, parse_dates=["t"])
    if not {"DO", "pH"} <= set(d.columns):
        return None
    do, ph = d.DO.to_numpy(float), d.pH.to_numpy(float)
    ok = np.isfinite(do) & np.isfinite(ph)
    if ok.sum() < 5000:
        return None
    take = np.zeros(len(d), bool); last = -1
    for i in np.flatnonzero(ok):
        if last < 0 or abs(do[i] - do[last]) > TOL_DO + 1e-9 or abs(ph[i] - ph[last]) > TOL_PH + 1e-9:
            take[i] = True; last = i
    days = ok.sum() / 96.0
    hours = d.t[take].dt.floor("h").nunique()
    # service A (v0.3's own): every reading reaches the server in the hourly batch; between batches the held
    # value (the latest delivered reading) must stay within tolerance, else an immediate frame is sent
    hour = d.t.dt.floor("h").to_numpy()
    idx = np.flatnonzero(ok)
    hv = hour[idx]
    is_last_in_hour = np.r_[hv[1:] != hv[:-1], True]      # the batch closing each hour carries this reading
    batch_hours = int(is_last_in_hour.sum())
    breaks = 0; last = -1
    for i, closes in zip(idx, is_last_in_hour):
        if last < 0:
            last = i
        elif abs(do[i] - do[last]) > TOL_DO + 1e-9 or abs(ph[i] - ph[last]) > TOL_PH + 1e-9:
            breaks += 1; last = i                 # immediate frame: the held value would break
        if closes:
            last = i
    per_hour = np.bincount(pd.Series(hv).value_counts().to_numpy())    # hours with n readings, n = 0..
    return {"samples_per_day": take.sum() / days, "hours_per_day": hours / days,
            "A_frames_per_day": (batch_hours + breaks) / days, "A_breaks_per_day": breaks / days,
            "A_hours_with_n": per_hour / days}


def frame_energy(radio, nbytes):
    """cheaper of an unconfirmed and a confirmed successful attempt (generous to the oracle)"""
    return min(radio.attempt(False, True, True, nbytes, 1), radio.attempt(True, True, True, nbytes, 1))


def batch_energy(radio, hours_with_n):
    """energy/day of the hourly batches: an hour with n readings needs ceil(n / per) frames of real size"""
    per = radio.readings_per_frame()
    e = 0.0
    for n, h in enumerate(hours_with_n):
        if n == 0 or h == 0:
            continue
        full, rest = divmod(n, per)
        e += h * (full * frame_energy(radio, FRAME_OVERHEAD + READING_BYTES * per)
                  + (frame_energy(radio, FRAME_OVERHEAD + READING_BYTES * rest) if rest else 0.0))
    return e


def sleep_floor(radio_name):
    if radio_name.startswith("NB-IoT"):
        p_radio = P.NBIOT["N211"]["psm"]
    else:
        p_radio = P.LORA_I_SLEEP * 1e-3 * P.V_LORA
    return 86400 * (p_radio + P.P_HOST_SLEEP)


def main():
    os.makedirs(OUT, exist_ok=True)
    need = {}
    for p in sorted(glob.glob("data/clean/usgs/*.csv")):
        r = oracle_need(p)
        if r:
            need[os.path.basename(p)[:-4]] = r
    nd = pd.DataFrame(need).T
    print(f"sites {len(nd)}; oracle samples/day median {nd.samples_per_day.median():.1f} "
          f"(IQR {nd.samples_per_day.quantile(.25):.1f}-{nd.samples_per_day.quantile(.75):.1f}); "
          f"needed hours/day median {nd.hours_per_day.median():.1f}")
    v03 = pd.read_csv("results/confirm/an2023_energy.csv").set_index(["trace", "radio"])["E_bounded"]
    rows = []
    for rl, radio in RADIOS.items():
        e_frame = min(radio.attempt(False, True, True, LIVE_BYTES, 1), radio.attempt(True, True, True, LIVE_BYTES, 1))
        floor = sleep_floor(rl)
        for trace in ("none", "UVA", "Weija", "InWaterSense"):
            e_v03_radio = v03[(trace, rl)]
            e_cap = v03[("none", rl)]          # the oracle never pays outage costs: at most v0.3 with NO outages
            for ts in (1.0, 5.0, 15.0, 30.0):
                e_wake = P.P_HOST_ON * ts
                v_total = floor + 96 * e_wake + e_v03_radio
                for site, r in nd.iterrows():
                    for service in ("A", "B"):
                        if service == "A":                 # v0.3's service: the full record, hourly
                            o_radio = min(batch_energy(radio, r.A_hours_with_n) + r.A_breaks_per_day * e_frame,
                                          e_cap)
                            o_sense = 96 * e_wake
                        else:                              # weaker: only the real-time value within tolerance
                            o_radio = min(r.hours_per_day * e_frame, e_cap)
                            o_sense = r.samples_per_day * e_wake
                        o_total = floor + o_sense + o_radio
                        rows.append({"service": service, "radio": rl, "trace": trace, "t_sense": ts, "site": site,
                                     "v03_total": v_total, "oracle_total": o_total,
                                     "saving": 1 - o_total / v_total,
                                     "saving_sensing": (96 * e_wake - o_sense) / v_total,
                                     "saving_radio": (e_v03_radio - o_radio) / v_total,
                                     "v03_sense_share": 96 * e_wake / v_total})
    d = pd.DataFrame(rows)
    d.to_csv(f"{OUT}/joint_oracle.csv", index=False)
    print(f"service A oracle frames/day median {nd.A_frames_per_day.median():.1f} "
          f"(IQR {nd.A_frames_per_day.quantile(.25):.1f}-{nd.A_frames_per_day.quantile(.75):.1f})")
    g = d.groupby(["service", "radio", "trace", "t_sense"])[["v03_total", "oracle_total", "saving", "saving_sensing",
                                                  "saving_radio", "v03_sense_share"]].median()
    with pd.option_context("display.width", 220, "display.max_rows", 200):
        txt = g.round(3).to_string()
    print(txt)
    summary = ""
    for service in ("A", "B"):
        typ = d[(d.t_sense == 5.0) & (d.service == service)].groupby("radio").saving.median()
        verdict = "PASS" if (typ >= 0.30).sum() >= 2 else "FAIL"
        summary += (f"\nService {service}, 5 s warm-up, median saving by radio (traces pooled): "
                    f"{typ.round(3).to_dict()} -> rule {verdict}")
    summary += "\nThe PASS RULE applies to service A (v0.3's own service); B is a weaker service, shown for contrast."
    print(summary)
    open(f"{OUT}/joint_oracle.log", "w", encoding="utf-8").write(txt + summary + "\n")


if __name__ == "__main__":
    main()
