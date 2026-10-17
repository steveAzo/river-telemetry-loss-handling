"""Review C1 (node off) and C5 (storage, buffer occupancy, drain limit); C6 hook (run from Paper2/)."""
import sys

import numpy as np

sys.path.insert(0, "src")
from energy.loss_handling import Radio, simulate, summary  # noqa: E402


def test_node_off_slots_generate_nothing_and_cost_nothing():
    link = np.ones(100, bool)
    off = np.zeros(100, bool); off[20:40] = True
    r = Radio("LoRaWAN SF7")
    a = simulate(link, r, "unconf", slot_s=600.0)
    b = simulate(link, r, "unconf", slot_s=600.0, node_off=off)
    assert b.not_generated == 20 and b.lost == 0 and b.delivered_on_time == 80
    assert np.isclose(b.energy_j, a.energy_j * 80 / 100)
    s = summary(b, 100, 600.0)
    assert s["delivered_of_expected"] == 0.8 and s["lost"] == 0.0


def test_node_off_during_an_outage_leaves_nothing_to_backfill():
    link = np.ones(200, bool); link[50:150] = False
    off = np.zeros(200, bool); off[50:150] = True                 # the gap was the node, not the network
    res = simulate(link, Radio("LoRaWAN SF7"), "arq_buffer", slot_s=600.0, probe_cap=36, node_off=off)
    assert res.not_generated == 100 and res.delivered_late == 0 and res.lost == 0


def test_storage_energy_is_charged_per_write_and_per_read():
    link = np.ones(120, bool)
    r = Radio("LoRaWAN SF7")
    a = simulate(link, r, "batch", M_check=6, slot_s=600.0)
    b = simulate(link, r, "batch", M_check=6, slot_s=600.0, storage=(1e-3, 2e-4))
    assert np.isclose(b.storage_j, 120 * 1e-3 + 120 * 2e-4)
    assert np.isclose(b.energy_j - a.energy_j, b.storage_j)


def test_max_buffer_tracks_the_backlog_and_buffer_cap_drops_oldest():
    link = np.ones(300, bool); link[100:200] = False
    r = Radio("LoRaWAN SF7")
    res = simulate(link, r, "arq_buffer", slot_s=600.0, probe_cap=1)       # probe every slot: drained at once
    assert res.max_buffer == 100 and res.lost == 0
    slow = simulate(link, r, "arq_buffer", slot_s=600.0, probe_cap=36)    # back-off: keeps buffering until its probe
    assert 100 < slow.max_buffer <= 100 + 36
    cap = simulate(link, r, "arq_buffer", slot_s=600.0, probe_cap=36, buffer_cap=40)
    assert cap.lost >= 60 and cap.max_buffer == 41                # one over the cap before the oldest is dropped


def test_drain_limit_spreads_a_backlog_over_slots_and_delivers_everything():
    link = np.ones(400, bool); link[100:300] = False
    r = Radio("LoRaWAN SF12")                                      # 4 readings per frame
    free = simulate(link, r, "arq_buffer", slot_s=900.0, probe_cap=24)
    lim = simulate(link, r, "arq_buffer", slot_s=900.0, probe_cap=24, drain_max_frames=2)
    assert free.lost == lim.lost == 0
    assert len(lim.backlogs) == 1
    first, cleared, n = lim.backlogs[0]
    per_slot = 2 * r.readings_per_frame()
    assert n > per_slot and cleared - first == int(np.ceil(n / per_slot)) - 1
    # the oldest reading leaves first either way; the rest of the backlog waits longer under the limit
    assert lim.arrival_delay_s.sum() > free.arrival_delay_s.sum()


def test_trigger_with_ok_times_receives_the_uplink_times():
    link = np.ones(50, bool)
    seen = []

    def trig(t, arr, ok_times):
        seen.append(len(ok_times))
        return False
    trig.wants_ok_times = True
    simulate(link, Radio("LoRaWAN SF7"), "batch_events", M_check=6, slot_s=600.0, urgent=np.zeros(50, bool), trigger=trig)
    assert seen[0] == 0 and seen[-1] == 50 // 6                    # one successful upload per completed hour


# ---------------------------------------------------------------- C6: application-level acknowledgement
from design.sitedata import make_trigger, server_picture  # noqa: E402


def _signal(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return np.round(np.c_[15 + 3 * np.sin(2 * np.pi * t / 96) + rng.normal(0, 0.05, n),
                          100 + 20 * np.sin(2 * np.pi * t / 96 + 1) + np.cumsum(rng.normal(0, 0.3, n))], 2)


def test_application_ack_keeps_the_bound_and_costs_more_uploads():
    X = _signal(); n, spd, slot = len(X), 96, 900.0
    tol = np.array([0.2, 2.0])
    grid = np.arange(n) * slot
    r = Radio("LoRaWAN SF7")
    runs = {}
    for ack in ("network", "application"):
        runs[ack] = simulate(np.ones(n, bool), r, "batch_events", M_check=4, slot_s=slot, urgent=np.zeros(n, bool),
                             trigger=make_trigger(X, tol, spd, slot, ack=ack))
    arr = grid + runs["application"].arrival_delay_s
    scored = np.ones(n, bool); scored[:spd] = False
    for j in range(2):
        est = server_picture(X[:, j], arr, grid, spd, scored)
        assert np.all(np.abs(est - X[scored, j]) <= tol[j] + 1e-9)
    assert runs["application"].attempts >= runs["network"].attempts


def test_application_ack_needs_a_later_uplink():
    """Readings 0-3 all arrive in ONE upload at slot 3 (t = 2700 s). The network server's ACK proves they reached
    it; the application's ACK can only come back with a later uplink."""
    X = np.array([[0.0], [0.0], [0.0], [0.0], [0.5]])
    arr = np.array([2700.0, 1800.0, 900.0, 0.0, np.inf])         # arrival time = slot * 900 + delay = 2700 s
    net = make_trigger(X, np.array([1.0]), spd=10_000, slot_s=900.0, ack="network")
    assert not net(4, arr)                                       # the server shows 0.0, the truth is 0.5: within 1
    app = make_trigger(X, np.array([1.0]), spd=10_000, slot_s=900.0, ack="application")
    assert app(4, arr, [2700.0])              # no later uplink: the application state may be empty -> upload
    app2 = make_trigger(X, np.array([1.0]), spd=10_000, slot_s=900.0, ack="application")
    assert not app2(4, arr, [2700.0, 2760.0])  # a later uplink carried the ACK: both states within tolerance
