"""Revision 3 corrections, applied at run time so that the frozen confirmatory code stays byte-identical
(docs/CONFIRMATORY_FREEZE.txt lists its SHA-256 hashes; docs/AUDIT3.md, issue 1 and the integrity rule).

Energy (audit issue 1). The frozen model charges the host at 17 mA + 1.6 mA (Waspmote on + the Smart Water
board's constant minimum) both while sensing and while waiting for radio attempts. The sources say:
  - Waspmote / Plug & Sense v15 technical guides: on 17 mA, sleep 30 uA, deep sleep 33 uA, hibernate 7 uA
    (papers/datasheets/Libelium_PlugSense_Technical_Guide_v15.txt, Libelium_Waspmote_Technical_Guide.txt).
  - Smart Water sensor guide, "Tables of consumption": the mote's total is the Waspmote in active mode plus the
    board's constant minimum (1.6 mA) plus the circuits of the operating sensors: temperature 3.5 mA,
    conductivity 2.5 mA, dissolved oxygen 160 uA, pH 170 uA (papers/datasheets/Libelium_Smart_Water_Sensor_Guide.txt).
  - The board can be switched off completely (Water.OFF()), so it draws nothing while the radio works.
Corrected: radio attempts at 17 mA (board off); sensing at 17 + 1.6 + 3.5 + 2.5 + 0.16 + 0.17 = 24.93 mA.

apply() patches the imported modules in place:
  energy.params.P_HOST_ON   -> host power during radio attempts (used by energy.loss_handling.Radio)
  energy.params.P_SENSE     -> new: host + board + four sensors while sampling
  run_design_eval.floor_j_per_day and run_confirm.floor_j_per_day -> charge sensing at P_SENSE
Nothing is written to disk.
"""
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "src/design")
sys.path.insert(0, "src/confirm")

from energy import params as P  # noqa: E402

I_HOST_ON = 17e-3                          # A, Waspmote on
I_BOARD_MIN = 1.6e-3                       # A, Smart Water board, constant minimum
I_SENSORS = {"T": 3.5e-3, "EC": 2.5e-3, "DO": 0.16e-3, "pH": 0.17e-3}   # A, operating sensor circuits

P_HOST_RADIO = I_HOST_ON * P.V_NODE                                      # W, board off during radio attempts
P_SENSE = (I_HOST_ON + I_BOARD_MIN + sum(I_SENSORS.values())) * P.V_NODE  # W, while sampling four parameters

FROZEN_P_HOST_ON = P.P_HOST_ON             # 18.6 mA x 3.7 V, kept for reporting the change


def floor_j_per_day(r, step_s):
    """Daily sleep + sensing energy (J/day) with the corrected sensing power."""
    return 86400 * (r.prof["p_sleep"] + P.P_HOST_SLEEP) + 86400 / step_s * P_SENSE * P.T_SENSE["typical"]


def apply():
    """Patch the already-importable modules; returns a dict describing the change."""
    import run_confirm
    import run_design_eval
    P.P_HOST_ON = P_HOST_RADIO
    P.P_SENSE = P_SENSE
    run_design_eval.floor_j_per_day = floor_j_per_day
    run_confirm.floor_j_per_day = floor_j_per_day
    return {"P_HOST_ON_frozen_W": FROZEN_P_HOST_ON, "P_HOST_ON_W": P_HOST_RADIO, "P_SENSE_W": P_SENSE}
