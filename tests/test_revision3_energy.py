"""Revision 3, audit issue 1: corrected host and sensing power, applied at run time.
Run: python -I -m pytest tests/test_revision3_energy.py (from Paper2/)."""
import hashlib
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "src/design")
sys.path.insert(0, "src/confirm")


def test_currents_match_libelium_guides():
    from revision3 import corrected as C
    assert abs(C.P_HOST_RADIO / C.P.V_NODE - 17e-3) < 1e-12
    assert abs(C.P_SENSE / C.P.V_NODE - 24.93e-3) < 1e-9          # 17 + 1.6 + 3.5 + 2.5 + 0.16 + 0.17 mA
    assert abs(C.FROZEN_P_HOST_ON / C.P.V_NODE - 18.6e-3) < 1e-9   # the frozen model's value


def test_apply_patches_radio_and_floor():
    from revision3 import corrected as C
    from energy.loss_handling import Radio
    import run_confirm
    import run_design_eval
    r = Radio("LoRaWAN SF7")
    e_frozen = r.attempt(True, True, True, 20, 1)
    f_frozen = run_design_eval.floor_j_per_day(r, 900.0)
    C.apply()
    e_new = r.attempt(True, True, True, 20, 1)
    f_new = run_confirm.floor_j_per_day(r, 900.0)
    assert e_new < e_frozen                                          # board no longer charged during attempts
    assert f_new > f_frozen                                          # T and EC circuits now charged while sensing
    sense_old = 96 * C.FROZEN_P_HOST_ON * C.P.T_SENSE["typical"]
    sense_new = 96 * C.P_SENSE * C.P.T_SENSE["typical"]
    assert abs((f_new - f_frozen) - (sense_new - sense_old)) < 1e-9  # only the sensing term changed


def test_frozen_files_untouched():
    """The corrections must never edit a frozen file (docs/CONFIRMATORY_FREEZE.txt)."""
    lines = open("docs/CONFIRMATORY_FREEZE.txt", encoding="utf-8").read().splitlines()[1:]
    for line in lines:
        h, path = line.split()
        assert hashlib.sha256(open(path, "rb").read()).hexdigest() == h, path
