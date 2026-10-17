"""Tests for the design-evaluation helpers (run from Paper2/: python -m pytest tests -q)."""
import sys

import numpy as np
import pytest

sys.path.insert(0, "src")
from design.sitedata import map_link, record_up, resolution_from_data, server_picture  # noqa: E402


def test_resolution_from_data():
    rng = np.random.default_rng(0)
    assert resolution_from_data(np.round(rng.normal(15, 3, 5000), 1)) == pytest.approx(0.1)
    assert resolution_from_data(np.round(rng.normal(300, 40, 5000))) == pytest.approx(1.0)


def test_map_link_wraps_and_offsets():
    rec = record_up(np.array([0, 600, 1200, 2400]), 600.0)      # slots 0,1,2 up; 3 down; 4 up -> wait
    t0, slot, up = rec
    assert list(up) == [True, True, True, False, True]
    grid = np.arange(0, 6000, 600)
    lk = map_link(rec, grid, 0)
    assert list(lk[:5]) == [True, True, True, False, True]
    assert list(lk[5:10]) == [True, True, True, False, True]    # wrapped
    assert map_link(rec, grid, 1800)[0] == False                # offset by 3 slots


def test_picture_exact_when_everything_arrives_on_time():
    n, spd = 200, 24
    x = np.sin(np.arange(n) / 4)
    grid = np.arange(n) * 3600
    est = server_picture(x, grid.astype(float), grid, spd, np.ones(n, bool))
    assert np.allclose(est, x)


def test_picture_uses_diel_change_when_available_else_persist():
    n, spd = 100, 24
    x = np.arange(n, dtype=float) % spd            # perfectly periodic "diel" signal
    grid = np.arange(n) * 3600
    arr = grid.astype(float).copy()
    arr[60:66] = grid[66]                          # readings 60..65 arrive at slot 66
    scored = np.zeros(n, bool); scored[60:66] = True
    est = server_picture(x, arr, grid, spd, scored)
    # last arrived = 59; diel: x[59] + (x[t-24] - x[59-24]) = x[t] for a periodic signal
    assert np.allclose(est, x[60:66])
    # without yesterday's data at the server: persistence of x[59]
    arr2 = arr.copy(); arr2[:59] = np.inf
    est2 = server_picture(x, arr2, grid, spd, scored)
    assert np.allclose(est2, x[59])


def test_picture_ignores_sensor_gaps_and_lost_readings():
    n, spd = 60, 24
    x = np.arange(n, dtype=float); x[30] = np.nan
    grid = np.arange(n) * 600
    arr = grid.astype(float); arr[31] = np.inf                  # 31 lost
    scored = np.zeros(n, bool); scored[32] = True; scored[31] = True
    est = server_picture(x, arr, grid, spd, scored)
    assert est[0] == x[29] + (x[31 - 24] - x[29 - 24]) == 31.0   # slot 31 shown from slot 29 + diel change
    assert est[1] == x[32]


# ---------------------------------------------------------------- bounded-error trigger (Part 2)
import sys as _sys  # noqa: E402
from design.sitedata import make_trigger  # noqa: E402
from energy.loss_handling import Radio, simulate  # noqa: E402


def _signal(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    X = np.c_[15 + 3 * np.sin(2 * np.pi * t / 96) + rng.normal(0, 0.05, n),
              100 + 20 * np.sin(2 * np.pi * t / 96 + 1) + np.cumsum(rng.normal(0, 0.3, n))]
    X = np.round(X, 2)
    X[500:510, 1] = np.nan                                     # a sensor gap
    return X


@pytest.mark.parametrize("rname", ["LoRaWAN SF7", "NB-IoT N211 RAI"])
def test_bounded_trigger_keeps_the_server_picture_within_tolerance_when_link_is_up(rname):
    X = _signal(); n, spd = len(X), 96
    tol = np.array([0.2, 2.0])
    grid = np.arange(n) * 900
    trig = make_trigger(X, tol, spd)
    res = simulate(np.ones(n, bool), Radio(rname), "batch_events", M_check=4, slot_s=900, probe_cap=24,
                   urgent=np.zeros(n, bool), trigger=trig)
    has = np.isfinite(X).all(axis=1)
    arr = np.where(has, grid + res.arrival_delay_s, np.inf)
    scored = has.copy(); scored[:spd] = False
    for j in range(2):
        est = server_picture(X[:, j], arr, grid, spd, scored)
        assert np.all(np.abs(est - X[scored, j]) <= tol[j] + 1e-9)     # bounded, by construction
    plain = simulate(np.ones(n, bool), Radio(rname), "batch_events", M_check=4, slot_s=900, probe_cap=24,
                     urgent=np.zeros(n, bool))
    assert res.attempts > plain.attempts                                # the bound costs extra uploads


def test_bounded_trigger_with_zero_tolerance_sends_every_changed_reading():
    X = _signal(800); spd = 96
    trig = make_trigger(X, np.array([0.0, 0.0]), spd)
    res = simulate(np.ones(800, bool), Radio("LoRaWAN SF7"), "batch_events", M_check=4, slot_s=900,
                   urgent=np.zeros(800, bool), trigger=trig)
    has = np.isfinite(X).all(axis=1)
    assert np.all(res.arrival_delay_s[has] == 0)               # every reading arrives in its own slot


def test_bounded_trigger_is_not_consulted_during_an_outage():
    """The node enters outage mode at the first failed upload (slot 300 here, or the next scheduled
    upload) and stays there until the link returns (slot 700, beyond this record). The trigger must not
    be consulted in that time, so it can never cause extra probes."""
    X = _signal(700); spd = 96
    link = np.ones(700, bool); link[300:] = False
    inner = make_trigger(X, np.array([0.0, 0.0]), spd)          # would fire at every slot
    calls = []

    def spy(t, arr):
        calls.append(t)
        return inner(t, arr)
    simulate(link, Radio("NB-IoT N211 RAI"), "batch_events", M_check=4, slot_s=900, probe_cap=24,
             urgent=np.zeros(700, bool), trigger=spy)
    assert max(calls) == 300                                     # consulted up to the failing slot, never after
    # at scheduled upload slots ((t + 1) % 4 == 0) the upload happens anyway and the trigger is not asked
    assert calls == [t for t in range(301) if (t + 1) % 4 != 0]


# ---------------------------------------------------------------- Part 3: newest-first packing
def test_newest_first_puts_the_newest_reading_in_the_first_frame():
    r = Radio("LoRaWAN SF12")                                  # 3 readings per frame
    n = 40
    fifo = simulate(np.ones(n, bool), r, "batch", M_check=4, slot_s=900)
    nf = simulate(np.ones(n, bool), r, "batch", M_check=4, slot_s=900, newest_first=True)
    # batch of slots 0..3 uploaded at slot 3: FIFO puts 3 in frame 2 (late); newest-first puts it in frame 1
    assert fifo.arrival_delay_s[3] > 0 and nf.arrival_delay_s[3] == 0
    assert nf.arrival_delay_s[0] == 3 * 900 and nf.arrival_delay_s[1] == 2 * 900   # oldest ride with it
    assert nf.arrival_delay_s[2] > 0                                                 # second frame waits
    assert nf.energy_j == pytest.approx(fifo.energy_j) and nf.attempts == fifo.attempts


def test_newest_first_failed_upload_keeps_the_rest_in_time_order():
    r = Radio("LoRaWAN SF12")
    link = np.ones(60, bool); link[3] = False                  # upload at slot 3 fails
    nf = simulate(link, r, "batch", M_check=4, slot_s=900, probe_cap=4, newest_first=True)
    assert nf.lost == 0 and np.all(np.isfinite(nf.arrival_delay_s))


@pytest.mark.parametrize("nf,exact", [(False, False), (True, True)])
def test_bounded_trigger_at_sf12_needs_newest_first(nf, exact):
    """SF12 frames hold 3 readings: a 4-reading hourly batch needs 2 frames. With FIFO packing the
    newest reading waits for the duty cycle and the picture can leave tolerance at that slot;
    newest-first packing makes the bound exact (DESIGN_EVAL_PLAN Part 3)."""
    X = _signal(3000, seed=3); n, spd = len(X), 96
    tol = np.array([0.2, 2.0])
    grid = np.arange(n) * 900
    res = simulate(np.ones(n, bool), Radio("LoRaWAN SF12"), "batch_events", M_check=4, slot_s=900,
                   urgent=np.zeros(n, bool), trigger=make_trigger(X, tol, spd), newest_first=nf)
    has = np.isfinite(X).all(axis=1)
    arr = np.where(has, grid + res.arrival_delay_s, np.inf)
    scored = has.copy(); scored[:spd] = False
    worst = max(np.max(np.abs(server_picture(X[:, j], arr, grid, spd, scored) - X[scored, j]) - tol[j])
                for j in range(2))
    assert (worst <= 1e-9) == exact


# ---------------------------------------------------------------- D4 fixes
def test_newest_first_promotes_the_newest_VALID_reading_past_a_sensor_gap():
    r = Radio("LoRaWAN SF12")                                  # 3 per frame
    valid = np.ones(40, bool); valid[3] = False                # slot 3 (newest of the first batch) is a gap
    nf = simulate(np.ones(40, bool), r, "batch", M_check=4, slot_s=900, newest_first=True, valid=valid)
    assert nf.arrival_delay_s[2] == 900                         # slot 2 rode in the first frame
    old = simulate(np.ones(40, bool), r, "batch", M_check=4, slot_s=900, newest_first=True)
    assert old.arrival_delay_s[2] > 900                         # without the mask the gap was promoted


def test_trigger_waits_for_physical_arrival_of_multi_slot_uploads():
    """A long outage followed by a backlog upload at SF12 spans many slots under the duty cycle. With
    slot_s, the node's copy of the server only counts readings that have physically arrived, so the
    server picture stays within tolerance at every slot where the link is up and the node is not in
    outage mode; without it the node can be over-optimistic."""
    X = _signal(3000, seed=5); n, spd = len(X), 96
    tol = np.array([0.2, 2.0]); grid = np.arange(n) * 900
    link = np.ones(n, bool); link[1000:1300] = False            # 3-day outage -> ~100-frame backlog
    has = np.isfinite(X).all(axis=1)
    worst = {}
    for slot in (None, 900):
        res = simulate(link, Radio("LoRaWAN SF12"), "batch_events", M_check=4, slot_s=900, probe_cap=8,
                       urgent=np.zeros(n, bool), trigger=make_trigger(X, tol, spd, slot), newest_first=True, valid=has)
        arr = np.where(has, grid + res.arrival_delay_s, np.inf)
        scored = has.copy(); scored[:spd] = False; scored[1000:1400] = False   # outage + backlog drain window
        worst[slot] = max(np.max(np.abs(server_picture(X[:, j], arr, grid, spd, scored) - X[scored, j]) - tol[j])
                          for j in range(2))
    assert worst[900] <= 1e-9
