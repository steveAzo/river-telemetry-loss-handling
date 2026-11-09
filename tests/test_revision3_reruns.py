"""Revision 3: the rerun wrapper's run-time patches (src/revision3/run_reruns.py).
Run: python -m pytest -p no:cacheprovider tests/test_revision3_reruns.py (from Paper2/), in its own process:
setup() patches modules for the whole process, so test_revision3_energy.py must not share it."""
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "src/design")
sys.path.insert(0, "src/confirm")


def test_setup_patches_sensing_and_do_root():
    from revision3 import run_reruns as W
    from energy import model
    from design import sitedata
    prof = model.radio(model.RADIOS[0])
    old = model.daily_energy(96, 24, prof)
    W.setup()
    new = model.daily_energy(96, 24, prof)
    C = W.corrected
    assert abs(new["sense"] - 96 * C.P_SENSE * C.P.T_SENSE["typical"]) < 1e-9     # sensing at 24.93 mA
    assert new["sense"] > old["sense"]
    assert abs(new["report"] - (old["report"] - 24 * prof["t_conn"] * (C.FROZEN_P_HOST_ON - C.P_HOST_RADIO))) < 1e-9
    assert new["sleep"] == old["sleep"]
    assert sitedata.load_site.__defaults__ == ("data/clean/usgs_baro",)
