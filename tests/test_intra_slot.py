"""Review C2: intra-slot link timing for ARQ (run from Paper2/: python -m pytest tests -q)."""
import sys

import numpy as np
import pytest

sys.path.insert(0, "src")
from energy import model as M  # noqa: E402
from energy.loss_handling import Radio, intra_slot_model, simulate  # noqa: E402


def _link(seed=1, n=3000):
    rng = np.random.default_rng(seed)
    up = rng.random(n) > 0.2
    up[1000:1200] = False                     # one long gap
    return up


@pytest.mark.parametrize("strategy", ["unconf", "arq", "arq_buffer", "batch", "checkpoint"])
@pytest.mark.parametrize("rname", ["LoRaWAN SF7", "LoRaWAN SF12", "NB-IoT N211 RAI"])
def test_full_slot_model_is_exactly_the_v01_replay(strategy, rname):
    link, r = _link(), Radio(rname)
    restore, fail = intra_slot_model(link, 600.0, "full")
    assert restore is None and fail is None
    a = simulate(link, r, strategy, p_radio=0.1, seed=3, slot_s=600.0, probe_cap=36)
    b = simulate(link, r, strategy, p_radio=0.1, seed=3, slot_s=600.0, probe_cap=36, restore=restore, down_retry_fail=fail)
    assert a.energy_j == b.energy_j and a.lost == b.lost and a.attempts == b.attempts


def test_retry_gap_respects_receive_windows_and_duty_cycle():
    r7, r12 = Radio("LoRaWAN SF7"), Radio("LoRaWAN SF12")
    g7 = r7.retry_gap_s(20, 1)
    assert g7 >= M.lora_active_s(7, 20) + 2.0                       # busy until RX2 closes, plus ACK time-out
    assert g7 >= 100 * M.lora_frame_ms(7, 20) / 1e3                 # 1% duty cycle
    assert r12.retry_gap_s(20, 1) == pytest.approx(100 * M.lora_frame_ms(12, 20) / 1e3)   # duty cycle dominates
    assert r7.retry_gap_s(20, 3) > g7                               # attempt 3 runs at SF8 (DR stepping)


def test_restoration_inside_the_slot_lets_a_retry_through():
    link = np.array([True, False, True])
    r = Radio("LoRaWAN SF7")
    early = simulate(link, r, "arq", slot_s=600.0, restore=np.array([np.inf, 1.0, np.inf]))
    late = simulate(link, r, "arq", slot_s=600.0, restore=np.array([np.inf, 1e9, np.inf]))
    assert early.lost == 0 and early.attempts == 1 + 2 + 1          # the second attempt succeeds
    assert late.lost == 1 and late.attempts == 1 + 8 + 1


def test_burst_model_retries_succeed_with_one_minus_q():
    link = np.array([True, False, True])
    r = Radio("LoRaWAN SF7")
    res = simulate(link, r, "arq", slot_s=600.0, restore=np.full(3, np.inf), down_retry_fail=np.array([1.0, 0.0, 1.0]))
    assert res.lost == 0 and res.attempts == 4                      # first attempt fails (the record), retry succeeds


def test_nb_iot_gives_up_without_network_in_every_model():
    link = np.array([True, False, True])
    r = Radio("NB-IoT N211 RAI")
    res = simulate(link, r, "arq", slot_s=600.0, restore=np.array([np.inf, 1.0, np.inf]))
    assert res.lost == 1 and res.attempts == 3                      # one search, then 'no network'


def test_intra_slot_model_shapes():
    link = np.array([True, False, False, True, False, True] + [False] * 10 + [True] + [False] * 3)
    restore, fail = intra_slot_model(link, 600.0, "burst", seed=0, short_h=1.0)
    last = [2, 4, 15]                                               # last slot of each gap followed by an up slot
    assert np.all(np.isfinite(restore[last])) and np.all((restore[last] >= 0) & (restore[last] < 600))
    assert np.isinf(np.delete(restore, last)).all()                 # the trailing gap never comes back in the record
    assert np.all(fail[[1, 2, 4]] == 0.248)                         # gaps <= 1 h (6 slots): bursts
    assert np.all(fail[6:16] == 1.0) and np.all(fail[17:] == 0.248)  # 10-slot gap is an outage; trailing 3-slot gap short
    r2, f2 = intra_slot_model(link, 600.0, "uniform", seed=0)
    assert f2 is None and np.array_equal(np.isfinite(r2), np.isfinite(restore))


def test_energy_multipliers_default_to_the_v01_values_and_scale_their_component():
    for name in ("LoRaWAN SF7", "LoRaWAN SF12", "NB-IoT N211 RAI"):
        a, b = Radio(name), Radio(name, scale={})
        for args in ((False, True, True, 20, 1), (True, True, True, 52, 1), (True, False, True, 20, 3), (True, False, False, 20, 1)):
            assert a.attempt(*args) == b.attempt(*args)
    r, h = Radio("LoRaWAN SF7"), Radio("LoRaWAN SF7", scale={"host": 2.0})
    t_act = M.lora_active_s(7, 20)
    from energy import params as P
    assert np.isclose(h.attempt(False, True, True) - r.attempt(False, True, True), P.P_HOST_ON * t_act)


def test_without_dr_stepping_retries_keep_the_spreading_factor():
    step, flat = Radio("LoRaWAN SF7"), Radio("LoRaWAN SF7", dr_step=False)
    assert step.airtime_s(20, 5) > step.airtime_s(20, 1)
    assert flat.airtime_s(20, 5) == flat.airtime_s(20, 1)
    assert flat.attempt(True, False, True, 20, 7) < step.attempt(True, False, True, 20, 7)
