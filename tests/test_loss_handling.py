"""Correctness of the loss-handling model (run from Paper2/: python -m pytest tests -q)."""
import sys

import numpy as np
import pytest

sys.path.insert(0, "src")
from energy.loss_handling import (FRAME_OVERHEAD, READING_BYTES, Radio, simulate,  # noqa: E402
                                  summary)
from energy import model as M  # noqa: E402
from energy import params as P  # noqa: E402

STRATS = ["unconf", "arq", "arq_buffer", "checkpoint"]
RADIOS = ["NB-IoT N211 RAI", "LoRaWAN SF7", "LoRaWAN SF12"]


def outage(n, lo, hi):
    link = np.ones(n, bool); link[lo:hi] = False
    return link


@pytest.mark.parametrize("rname", RADIOS)
@pytest.mark.parametrize("strategy", STRATS + ["modem_buffer", "unconf_backoff"])
def test_perfect_link_delivers_everything_on_time(rname, strategy):
    r = Radio(rname)
    if strategy in ("modem_buffer", "unconf_backoff") and not r.nb:
        pytest.skip("NB-IoT only")
    res = simulate(np.ones(50, bool), r, strategy)
    assert (res.delivered_on_time, res.delivered_late, res.lost, res.duplicates) == (50, 0, 0, 0)


def test_unconf_energy_is_one_attempt_per_reading():
    r = Radio("LoRaWAN SF7")
    res = simulate(np.ones(10, bool), r, "unconf")
    assert res.attempts == 10
    assert res.energy_j == pytest.approx(10 * r.attempt(False, True, True))


def test_lora_arq_burns_all_attempts_during_outage_with_sf_escalation():
    r = Radio("LoRaWAN SF7")
    res = simulate(outage(5, 0, 5), r, "arq")
    assert res.lost == 5 and res.attempts == 5 * 8
    per_reading = sum(r.attempt(True, False, False, attempt_no=a) for a in range(1, 9))
    assert res.energy_j == pytest.approx(5 * per_reading)
    # escalation: attempts 7-8 use SF10, dearer than attempts 1-2 at SF7
    assert r.attempt(True, False, False, attempt_no=7) > r.attempt(True, False, False, attempt_no=1)


def test_nbiot_stops_retrying_when_modem_reports_no_network():
    r = Radio("NB-IoT N211 RAI", t_search=10.0)
    res = simulate(outage(4, 0, 4), r, "arq")
    assert res.attempts == 4                                   # one search per reading, not R = 3
    assert res.energy_j == pytest.approx(4 * (0.222134 * 10 + P.P_HOST_ON * 10))


@pytest.mark.parametrize("rname,strategy", [("NB-IoT N211 RAI", "arq_buffer"),
                                            ("NB-IoT N211 RAI", "modem_buffer"),
                                            ("LoRaWAN SF7", "arq_buffer")])
def test_buffer_backfills_an_outage_with_exact_delays(rname, strategy):
    r = Radio(rname)
    res = simulate(outage(100, 10, 20), r, strategy, slot_s=600)
    assert (res.delivered_on_time, res.delivered_late, res.lost) == (90, 10, 0)
    # readings 10..19 are delivered in slot 20; one frame holds all 10 (SF7: 18 per frame, NB: 42)
    assert sorted(res.delays_s) == pytest.approx(sorted((20 - s) * 600 for s in range(10, 20)))


def test_lora_sf12_backfill_delay_includes_duty_cycle():
    r = Radio("LoRaWAN SF12")
    per = r.readings_per_frame()
    assert per == (51 - FRAME_OVERHEAD) // READING_BYTES == 3
    res = simulate(outage(30, 5, 12), r, "arq_buffer", slot_s=600)   # 7 buffered readings -> 3 frames
    assert res.delivered_late == 7 and res.lost == 0
    d = sorted(res.delays_s)
    air3 = M.lora_frame_ms(12, FRAME_OVERHEAD + READING_BYTES * 3) / 1e3
    # the second frame waits 99x the first frame's airtime (+ the first frame's airtime itself)
    late_second = [(12 - s) * 600 + 100 * air3 for s in (8, 9, 10)]
    assert all(any(abs(x - y) < 1e-6 for x in d) for y in late_second)


def test_checkpoint_hand_worked_case():
    """M=5, link down in slots 7..12 (n=20). Checkpoint at t=4 succeeds; at t=9 it fails, so readings
    5..8 (5, 6 arrived; 7, 8 lost) are buffered with 9; probes at 10..12 fail; the probe at 13 succeeds
    and drains: 7, 8, 9, 10, 11, 12 late; 5, 6 duplicates."""
    r = Radio("LoRaWAN SF7")
    res = simulate(outage(20, 7, 13), r, "checkpoint", M_check=5)
    assert (res.delivered_on_time, res.delivered_late, res.lost, res.duplicates) == (14, 6, 0, 2)


def test_checkpoint_counts_undetected_radio_losses_as_lost():
    r = Radio("LoRaWAN SF7")
    res = simulate(np.ones(400, bool), r, "checkpoint", p_radio=0.3, M_check=5, seed=1)
    assert res.lost > 0 and res.delivered_late == 0             # no outage mode is ever entered
    assert res.delivered_on_time + res.lost == 400


@pytest.mark.parametrize("rname", RADIOS)
@pytest.mark.parametrize("strategy", STRATS + ["modem_buffer", "unconf_backoff"])
def test_every_reading_is_accounted_exactly_once(rname, strategy):
    r = Radio(rname)
    if strategy in ("modem_buffer", "unconf_backoff") and not r.nb:
        pytest.skip("NB-IoT only")
    rng = np.random.default_rng(7)
    link = rng.random(2000) > 0.05
    link[300:450] = False; link[1200:1210] = False
    res = simulate(link, r, strategy, p_radio=0.1, seed=3, slot_s=600)
    assert res.delivered_on_time + res.delivered_late + res.lost == 2000
    s = summary(res, 2000, 600)
    assert s["on_time"] + s["late"] + s["lost"] == pytest.approx(1.0)


def test_buffer_cap_drops_oldest():
    r = Radio("NB-IoT N211 RAI")
    res = simulate(outage(50, 0, 30), r, "arq_buffer", buffer_cap=10)
    assert res.lost == 20 and res.delivered_late == 10


def test_nbiot_bulk_frame_cost_scaling():
    r = Radio("NB-IoT N211 RAI")
    host = P.P_HOST_ON * r.prof["t_conn"]
    e20 = r.attempt(True, True, True, nbytes=20) - host
    e512 = r.attempt(True, True, True, nbytes=512) - host
    assert e512 / e20 == pytest.approx(1.6)                     # Michelinakis: ~ +60% for 512 B


def test_modem_buffer_rejects_lorawan():
    with pytest.raises(ValueError):
        simulate(np.ones(5, bool), Radio("LoRaWAN SF7"), "modem_buffer")


def test_probe_backoff_saves_energy_and_bounds_extra_delay():
    r = Radio("NB-IoT N211 RAI", t_search=10.0)
    link = outage(400, 10, 300)
    a = simulate(link, r, "modem_buffer", probe_cap=1, slot_s=600)
    b = simulate(link, r, "modem_buffer", probe_cap=32, slot_s=600)
    assert b.energy_j < a.energy_j / 5                         # far fewer cell searches
    assert (a.delivered_late, a.lost) == (290, 0) and b.lost == 0
    # with back-off the node learns that the link is back only at its next probe (< probe_cap slots
    # later), so readings taken in between are delivered late instead of on time
    assert 290 <= b.delivered_late < 290 + 32
    assert b.delivered_on_time + b.delivered_late == 400
    # the back-off can delay the end of the outage by fewer than probe_cap slots
    assert max(b.delays_s) - max(a.delays_s) < 32 * 600
    assert max(b.delays_s) >= max(a.delays_s)


def test_probe_schedule_is_exponential():
    """Outage from slot 0: the first failure at t=0 enters outage mode; probes at t=1 (fail -> wait 2),
    t=3 (fail -> wait 4), t=7 (fail -> wait 8 capped at 8), t=15, 23, ... until the link returns."""
    r = Radio("NB-IoT N211 RAI", t_search=10.0)
    res = simulate(outage(40, 0, 40), r, "modem_buffer", probe_cap=8)
    # attempts: t=0, 1, 3, 7, 15, 23, 31, 39  -> 8 searches
    assert res.attempts == 8


def test_unconf_backoff_saves_search_energy_but_loses_outage_readings():
    r = Radio("NB-IoT N211 RAI", t_search=10.0)
    link = outage(400, 10, 300)
    plain = simulate(link, r, "unconf")
    bo = simulate(link, r, "unconf_backoff", probe_cap=32)
    buf = simulate(link, r, "modem_buffer", probe_cap=32)
    assert bo.energy_j < plain.energy_j / 5                    # same back-off saving as buffering...
    assert bo.lost > plain.lost - 1 and bo.delivered_late == 0  # ...but the outage readings are gone
    assert buf.lost == 0 and buf.delivered_late > 0
    assert buf.energy_j > bo.energy_j                          # buffering's extra cost = the backfill frames
    assert bo.delivered_on_time + bo.lost == 400


def test_unconf_backoff_rejects_lorawan():
    with pytest.raises(ValueError):
        simulate(np.ones(5, bool), Radio("LoRaWAN SF7"), "unconf_backoff")


def test_batch_delivers_everything_late_with_bounded_delay_on_a_perfect_link():
    r = Radio("NB-IoT N211 RAI")
    res = simulate(np.ones(60, bool), r, "batch", M_check=6, slot_s=600)
    assert res.delivered_on_time == 0 and res.delivered_late == 60 and res.lost == 0
    assert max(res.delays_s) == 5 * 600 and min(res.delays_s) == 0   # first reading of a batch waits 5 slots
    single = simulate(np.ones(60, bool), r, "arq")
    assert res.energy_j < single.energy_j / 3                           # 10 bulk frames vs 60 messages


def test_batch_survives_an_outage():
    r = Radio("LoRaWAN SF7")
    # 204 slots: the record ends on a batch boundary ((203 + 1) % 6 == 0); readings still waiting for the
    # next upload at the very end of a record are counted lost by design (end-of-record rule)
    res = simulate(outage(204, 20, 80), r, "batch", M_check=6, probe_cap=8, slot_s=600)
    assert res.lost == 0 and res.delivered_late + res.delivered_on_time == 204
    cut = simulate(outage(200, 20, 80), r, "batch", M_check=6, probe_cap=8, slot_s=600)
    assert cut.lost == 0                                   # slots 198-199 are flushed after the record ends
    nofl = simulate(outage(200, 20, 80), r, "batch", M_check=6, probe_cap=8, slot_s=600, flush=0)
    assert nofl.lost == 2                                  # without the flush they would be stranded


def test_flush_delivers_readings_stranded_by_the_end_of_the_record():
    """Outage ends 3 slots before the record ends; with back-off cap 32 the node has not probed yet.
    The flush lets it probe and upload, with delays measured from each reading's own slot."""
    r = Radio("NB-IoT N211 RAI")
    link = outage(500, 100, 497)
    res = simulate(link, r, "modem_buffer", probe_cap=32, slot_s=600)
    assert res.lost == 0 and res.delivered_on_time + res.delivered_late == 500
    stranded = simulate(link, r, "modem_buffer", probe_cap=32, slot_s=600, flush=0)
    assert stranded.lost > 0
    assert max(res.delays_s) > max(stranded.delays_s or [0])          # stranded readings arrive late, not never
    # no flush when the record ends during an outage: those readings really are undelivered
    still_down = simulate(outage(500, 100, 500), r, "modem_buffer", probe_cap=32, slot_s=600)
    assert still_down.lost == 400


@pytest.mark.parametrize("strategy", ["arq_buffer", "batch", "checkpoint", "modem_buffer", "unconf_backoff"])
def test_backoff_really_backs_off_in_every_buffering_strategy(strategy):
    """An outage that lasts to the end of the record (no drain afterwards): with cap K = 32, the attempts
    made during 1000 down slots must be ~1000/32 probes plus the attempts that detected the outage, not
    one per slot. Regression test: batch's back-off used to be reset by every failed probe."""
    r = Radio("LoRaWAN SF7") if strategy in ("arq_buffer", "batch", "checkpoint") else Radio("NB-IoT N211 RAI")
    up = simulate(np.ones(100, bool), r, strategy, probe_cap=32, M_check=6)
    res = simulate(outage(1100, 100, 1100), r, strategy, probe_cap=32, M_check=6)
    during = res.attempts - up.attempts
    # <= 8 attempts detect the outage (LoRaWAN R = 8), then probes at 1, 3, 7, 15, 31, then every 32 slots
    assert during <= 8 + 5 + 1000 // 32 + 1
    assert during >= 1000 // 32


def test_within_x_hours_metric():
    r = Radio("NB-IoT N211 RAI")
    res = simulate(np.ones(60, bool), r, "batch", M_check=6, slot_s=600)   # delays 0..50 min
    s = summary(res, 60, 600)
    assert s["within_1h"] == 1.0 and s["within_6h"] == 1.0
    res2 = simulate(outage(400, 10, 300), r, "modem_buffer", slot_s=600)  # outage of 290 slots = 48 h
    s2 = summary(res2, 400, 600)
    assert s2["within_1h"] < s2["within_24h"] < 1.0 and s2["within_24h"] == pytest.approx((110 + 144) / 400, abs=0.01)


# ---------------------------------------------------------------- per-reading arrival + batch_events
@pytest.mark.parametrize("rname", RADIOS)
@pytest.mark.parametrize("strategy", STRATS + ["batch", "modem_buffer", "unconf_backoff"])
def test_arrival_array_is_consistent_with_counts(rname, strategy):
    r = Radio(rname)
    if strategy in ("modem_buffer", "unconf_backoff") and not r.nb:
        pytest.skip("NB-IoT only")
    rng = np.random.default_rng(11)
    link = rng.random(1500) > 0.05; link[200:400] = False
    res = simulate(link, r, strategy, p_radio=0.1, seed=4, slot_s=600, probe_cap=16)
    fin = np.isfinite(res.arrival_delay_s)
    assert fin.sum() == res.delivered_on_time + res.delivered_late
    # on-time readings have delay 0; a batched reading uploaded in its own slot also has delay 0 but
    # is counted late (it went out in a batch), so the zero-delay count can only be larger
    assert np.sum(res.arrival_delay_s == 0) >= res.delivered_on_time
    if strategy not in ("batch",):
        assert np.sum(res.arrival_delay_s == 0) == res.delivered_on_time
    assert np.all(res.arrival_delay_s[fin] >= 0)


def test_batch_events_sends_alarm_immediately_when_link_up():
    r = Radio("LoRaWAN SF7")
    urgent = np.zeros(60, bool); urgent[14] = True
    res = simulate(np.ones(60, bool), r, "batch_events", M_check=6, slot_s=600, urgent=urgent)
    assert res.arrival_delay_s[14] == 0.0                  # the alarming reading arrives in its own slot
    assert res.arrival_delay_s[12] == 2 * 600              # and takes the open batch (12, 13) with it
    base = simulate(np.ones(60, bool), r, "batch", M_check=6, slot_s=600)
    assert base.arrival_delay_s[14] == 3 * 600             # plain batching: waits for the slot-17 upload
    assert res.lost == 0 and res.delivered_late + res.delivered_on_time == 60


def test_batch_events_probes_at_once_during_an_outage_and_reaches_server_when_link_returns():
    r = Radio("NB-IoT N211 RAI")
    # (a) record ends during the outage: the alarm at 100 adds exactly one (failed) probe
    link_a = outage(300, 50, 300)
    urg_a = np.zeros(300, bool); urg_a[100] = True
    ra = simulate(link_a, r, "batch_events", M_check=6, probe_cap=36, slot_s=600, urgent=urg_a)
    pa = simulate(link_a, r, "batch", M_check=6, probe_cap=36, slot_s=600)
    assert ra.attempts == pa.attempts + 1
    # (b) an alarm just after the link returns ends outage mode at once: the alarming reading arrives in
    #     its own slot, earlier than with plain batching, and nothing is lost
    link = outage(400, 50, 300)
    urgent = np.zeros(400, bool); urgent[100] = True; urgent[301] = True
    res = simulate(link, r, "batch_events", M_check=6, probe_cap=36, slot_s=600, urgent=urgent)
    plain = simulate(link, r, "batch", M_check=6, probe_cap=36, slot_s=600)
    assert res.arrival_delay_s[301] == 0.0 and plain.arrival_delay_s[301] > 0
    assert res.lost == 0 and np.all(np.isfinite(res.arrival_delay_s))
    assert np.all(res.arrival_delay_s[50:302] <= plain.arrival_delay_s[50:302])


def test_batch_events_without_alarms_equals_batch():
    r = Radio("LoRaWAN SF12")
    rng = np.random.default_rng(5); link = rng.random(2000) > 0.1; link[500:900] = False
    a = simulate(link, r, "batch_events", M_check=6, probe_cap=16, slot_s=600, urgent=np.zeros(2000, bool), seed=2)
    b = simulate(link, r, "batch", M_check=6, probe_cap=16, slot_s=600, seed=2)
    assert a.energy_j == b.energy_j and np.array_equal(a.arrival_delay_s, b.arrival_delay_s)


def test_batch_events_requires_mask():
    with pytest.raises(ValueError):
        simulate(np.ones(5, bool), Radio("LoRaWAN SF7"), "batch_events")
