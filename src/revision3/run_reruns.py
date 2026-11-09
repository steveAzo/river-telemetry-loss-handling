"""Revision 3, Step 5: re-run every energy- or DO-dependent analysis that feeds the paper, with the audit corrections.

Post hoc sensitivity runs (docs/AUDIT3.md, issues 1 and 18). No frozen or earlier script is edited; this wrapper
changes, at run time only:
  * power: corrected.apply() (17 mA host during radio attempts; 24.93 mA while sensing in the design floors);
  * sensing energy computed inline elsewhere:
      energy.model.daily_energy  -> replaced by a copy whose sense term uses P_SENSE (report term unchanged);
      energy/run_loss_handling.py -> its floor column is corrected after the run, in closed form:
          floor_new = floor_run + slots_per_day * (P_SENSE - P_HOST_ON_run) * T_SENSE[typical];
  * DO data: design.sitedata.load_site reads data/clean/usgs_baro (barometric-corrected) by default;
  * outputs: every job writes under results/revision3/rerun/ (the original results are not touched).
Usage (from Paper2/): python -I src/revision3/run_reruns.py JOB [JOB ...]   (JOB from JOBS below, or 'all')
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
from revision3 import corrected  # noqa: E402  (puts src/design and src/confirm on the path)

R = "results/revision3/rerun"
P = corrected.P


def _sense_daily_energy(samples_per_day, reports_per_day, radio_profile, t_sense=P.T_SENSE["typical"],
                        confirmed=False, host=True):
    """energy.model.daily_energy with the sensing term charged at P_SENSE (host, board, four sensors)."""
    r = radio_profile
    e_rep = r["e_report_ack"] if confirmed else r["e_report"]
    sleep = 86400 * (r["p_sleep"] + (P.P_HOST_SLEEP if host else 0.0))
    sense = samples_per_day * corrected.P_SENSE * t_sense if host else 0.0
    report = reports_per_day * (e_rep + (P.P_HOST_ON * r["t_conn"] if host else 0.0))
    return {"sleep": sleep, "sense": sense, "report": report, "total": sleep + sense + report}


def setup():
    change = corrected.apply()
    from energy import model
    model.daily_energy = _sense_daily_energy
    from design import sitedata             # the only importable name (it uses a relative import)
    sitedata.load_site.__defaults__ = ("data/clean/usgs_baro",)
    os.makedirs(R, exist_ok=True)
    return change


def job_loss_handling():
    import pandas as pd
    from energy import run_loss_handling as m
    out = f"{R}/loss_handling.csv"
    m.main(out)
    d = pd.read_csv(out)
    add = 86400 / d.slot_s * (corrected.P_SENSE - P.P_HOST_ON) * P.T_SENSE["typical"]
    d["energy_floor_j_per_day"] = d.energy_floor_j_per_day + add
    d["energy_total_j_per_day"] = d.energy_floor_j_per_day + d.energy_j_per_day
    d["lifetime_y"] = m.BATTERY / d.energy_total_j_per_day / 365
    d.to_csv(out, index=False, float_format="%.6g")


def job_loss_revision():
    from revision import run_loss_revision as m
    m.OUT = R
    m.part_a(); m.part_b(); m.part_c()


def job_ack_variant():
    from revision import run_ack_variant as m
    m.main(f"{R}/ack_variant.csv")


def job_sweep_k_batch():
    from revision import sweep_k_batch as m
    m.main(f"{R}/sweep_k_batch.csv")


def job_netsim():
    from revision import netsim as m
    m.main(f"{R}/netsim.csv")


def job_energy_mc():
    from revision import energy_mc as m
    m.main(f"{R}/energy_mc", "100")


def job_tolerance():
    from revision import tolerance_events as m
    m.main(f"{R}/tolerance")


def job_design_eval():
    import run_design_eval as m
    m.OUT = Path(f"{R}/design"); m.OUT.mkdir(parents=True, exist_ok=True)
    m.main([])


def job_sensitivity():
    import run_sensitivity as m
    m.OUT = Path(f"{R}/design/sensitivity"); m.OUT.mkdir(parents=True, exist_ok=True)
    m.main([])


JOBS = {k[4:]: v for k, v in globals().items() if k.startswith("job_")}
FAST = ["loss_handling", "tolerance", "loss_revision", "sweep_k_batch", "energy_mc", "netsim"]
SLOW = ["ack_variant", "design_eval", "sensitivity"]


def keep_awake():
    """Ask Windows not to sleep while this process runs (the 2026-11-05 overnight run stopped when the PC slept)."""
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # ES_CONTINUOUS | SYSTEM_REQUIRED
    except Exception:
        pass


def main(names):
    keep_awake()
    change = setup()
    with open(f"{R}/corrections_applied.json", "w", encoding="utf-8") as f:
        json.dump({**change, "P_SENSE_W": corrected.P_SENSE, "do_root": "data/clean/usgs_baro"}, f, indent=1)
    for n in (FAST + SLOW if names == ["all"] else names):
        done = Path(f"{R}/{n}.done")
        if done.exists():
            print(f"skip {n}", flush=True); continue
        t0 = time.time()
        print(f"=== {n} start {time.strftime('%H:%M:%S')}", flush=True)
        JOBS[n]()
        done.write_text(f"{time.time() - t0:.0f} s\n")
        print(f"=== {n} done in {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["all"])
