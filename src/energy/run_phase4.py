"""Phase 4: battery lifetime of every scheme, from the measured report rates of Phases 2-3.

Inputs: results/phase2/results.csv (periodic, ADAPTIVEML), results/phase3/phase3.csv (bounded DPS,
detector variants), both on the same test periods. Samples/day = the dataset's every-cycle rate.
Uplink: CONFIRMED (Phase 3 recommendation): NB-IoT RAI-400 energy per report, LoRaWAN confirmed;
retries at 1 % loss add 1.04 % reports (Phase 3 loss study). Unconfirmed is reported for contrast.
Output: results/phase4/lifetime.csv (long format, one row per combination).
"""
import itertools
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from energy import params as P  # noqa: E402
from energy.model import RADIOS, daily_energy, lifetime_years, radio  # noqa: E402

OUT = Path("results/phase4"); OUT.mkdir(parents=True, exist_ok=True)
RETRY_OVERHEAD = {True: 1.0104, False: 1.0}        # confirmed uplink, 1 % loss (Phase 3, Sec. 5)

p2 = pd.read_csv("results/phase2/results.csv")
p3 = pd.read_csv("results/phase3/phase3.csv")
spd = p2[(p2.kind == "PERIODIC") & p2.setting.isna()].set_index("dataset").reports_per_day   # samples/day

rows = []
for _, r in p2[(p2.kind == "PERIODIC")].iterrows():
    lab = "PERIODIC every cycle" if pd.isna(r.setting) else f"PERIODIC {int(r.setting)} min"
    rows.append({"dataset": r.dataset, "method": lab, "level": None, "reports_per_day": r.reports_per_day})
for _, r in p2[(p2.kind == "ADAPTIVEML") & (p2["mode"] == "report")].iterrows():
    rows.append({"dataset": r.dataset, "method": f"ADAPTIVEML a={r.alpha:g}", "level": None,
                 "reports_per_day": r.reports_per_day})
for _, r in p2[(p2.kind.isin(["SOD", "RLS-T"])) & (p2["mode"] == "report") & (p2.level == 0)].iterrows():
    rows.append({"dataset": r.dataset, "method": r.kind, "level": 0, "reports_per_day": r.reports_per_day})
for _, r in p3.iterrows():
    m = r.kind + (f"+DET{int(r.det)}" if r.det else "") + ("+TIGHT" if r.tight else "")
    rows.append({"dataset": r.dataset, "method": m, "level": int(r.level), "reports_per_day": r.reports_per_day})
rates = pd.DataFrame(rows)
rates["samples_per_day"] = rates.dataset.map(spd)

out = []
for (rad, (ts_lab, ts), (bat_lab, bat), conf) in itertools.product(
        RADIOS, P.T_SENSE.items(), P.BATTERIES.items(), (True, False)):
    prof = radio(rad)
    for _, r in rates.iterrows():
        d = daily_energy(r.samples_per_day, r.reports_per_day * RETRY_OVERHEAD[conf], prof, t_sense=ts,
                         confirmed=conf)
        out.append({**r.to_dict(), "radio": rad, "t_sense": ts_lab, "battery": bat_lab, "confirmed": conf,
                    "E_sleep": d["sleep"], "E_sense": d["sense"], "E_report": d["report"], "E_day": d["total"],
                    "P_avg_mW": d["total"] / 86.4, "lifetime_y": lifetime_years(d["total"], bat)})
df = pd.DataFrame(out)
df.to_csv(OUT / "lifetime.csv", index=False)
print(len(df), "rows ->", OUT / "lifetime.csv")
