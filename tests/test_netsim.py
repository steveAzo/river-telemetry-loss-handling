"""Review C8: checks of the multi-node recovery model (run from Paper2/)."""
import sys

import numpy as np
import pytest

sys.path.insert(0, "src")
from revision.netsim import Gateway, aloha_success, simulate_recovery  # noqa: E402


@pytest.mark.parametrize("G", [0.05, 0.2, 0.5])
def test_collision_rule_reproduces_pure_aloha(G):
    n, air = 50, 0.1
    rate = G / (n * air)
    ok = aloha_success(n, rate, air, duration_s=200_000, seed=1)
    assert ok == pytest.approx(np.exp(-2 * G), abs=0.01)


def test_gateway_duty_cycle_forces_rx2_then_no_ack():
    gw = Gateway()
    assert gw.ack(10.0, 7)                        # RX1
    assert gw.rx1_free_at > 10.0 + 1.0
    assert gw.ack(10.5, 7) and gw.rx2_air > 0     # RX1 sub-band resting: RX2
    assert not gw.ack(10.6, 7)                    # RX2 busy / resting: no ACK


def test_single_node_recovers_its_whole_backlog():
    r = simulate_recovery(1, 7, outage_h=24, seed=0)
    assert r["cleared_share"] == 1.0 and r["pdr"] == 1.0 and r["collided_share"] == 0.0
    assert r["clear_all_h"] < 6.5                 # the next back-off probe (<= 6 h) plus a short drain


def test_many_synchronised_nodes_contend_and_jitter_helps():
    a = simulate_recovery(200, 7, outage_h=24, jitter_s=0.0, seed=0)
    b = simulate_recovery(200, 7, outage_h=24, jitter_s=3600.0, seed=0)
    assert a["pdr"] < b["pdr"] and a["clear_all_h"] > b["clear_all_h"]


def test_truncated_lognormal_sampler_matches_the_discrete_pmf():
    sys.path.insert(0, "src/scoping")
    from outage_models import pmf
    from revision.outage_gof import sample
    par = {"mu": -3.7, "sigma": 2.8}                 # the InWaterSense fit: most mass below 0.5
    k = sample("dlnorm", par, 200_000, np.random.default_rng(0))
    for kk in (1, 2, 5):
        assert np.mean(k == kk) == pytest.approx(pmf("dlnorm", par, np.array([float(kk)]))[0], abs=0.005)
