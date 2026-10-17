"""Phase 4 energy model reproduces its sources (run: python -m pytest tests -q)."""
import sys

import pytest

sys.path.insert(0, "src")
from energy.model import daily_energy, lifetime_years, lora_frame_ms, lora_report_energy  # noqa: E402

# Michelinakis 2021 Table X (5 Wh battery, radio only, no TAU, PSM between reports).
# Four entries are omitted because they contradict the paper's own equation (e.g. N211/Op2 default:
# 5.7 y at 24 h < 5.9 y at 4 h): BC95 RAI-400 1 h (both operators) and default 24 h (BC95/N211 Op1+Op2).
MICH = [  # (E_connected J, P_psm W, interval h, paper years)
    (2.39, 10.61e-6, 1, 0.8), (2.39, 10.61e-6, 4, 3.2), (0.17, 10.61e-6, 4, 25.5), (0.17, 10.61e-6, 24, 45.4),
    (0.82, 10.61e-6, 1, 2.4), (0.82, 10.61e-6, 4, 8.5), (0.12, 10.61e-6, 4, 30.1), (0.12, 10.61e-6, 24, 47.6),
    (4.17, 9.35e-6, 1, 0.5), (4.17, 9.35e-6, 4, 1.9), (0.31, 9.35e-6, 1, 6.0), (0.31, 9.35e-6, 4, 18.5),
    (0.31, 9.35e-6, 24, 44.1), (1.27, 9.35e-6, 1, 1.6), (1.27, 9.35e-6, 4, 5.9), (0.33, 9.35e-6, 1, 5.9),
    (0.33, 9.35e-6, 4, 17.7), (0.33, 9.35e-6, 24, 43.3)]


@pytest.mark.parametrize("e,p,h,years", MICH)
def test_reproduces_michelinakis_table_x(e, p, h, years):
    prof = {"e_report": e, "e_report_ack": e, "p_sleep": p, "t_conn": 0.0}
    d = daily_energy(0, 24 / h, prof, host=False)
    assert lifetime_years(d["total"], 18000.0) == pytest.approx(years, rel=0.05, abs=0.1)


@pytest.mark.parametrize("sf,pl,uplink,ms", [(7, 242, True, 399.6), (7, 0, False, 41.2),
                                             (12, 51, True, 2793.5), (10, 51, True, 698.4)])
def test_lora_airtime_casals_table6(sf, pl, uplink, ms):
    assert lora_frame_ms(sf, pl, uplink) == pytest.approx(ms, abs=1.0)


@pytest.mark.parametrize("sf,pl,tmin,years", [(12, 51, 5, 0.26), (12, 51, 60, 2.13), (7, 242, 60, 3.76),
                                              (7, 242, 360, 5.52), (12, 51, 360, 4.55)])
def test_lora_lifetime_casals_sec52(sf, pl, tmin, years):
    q = lora_report_energy(sf, frm_payload=pl) / 3.3
    i_sleep = 2.4 / 6.19 / 8760                       # their asymptote
    assert 2.4 / (q / (tmin * 60) + i_sleep) / 8760 == pytest.approx(years, rel=0.04)


def test_confirmed_vs_unconfirmed_casals_sec51():
    """Casals: acknowledged is CHEAPER at DR5 (ACK in RX1 skips the RX2 wait; lifetime up to ~16 %
    higher). At DR0 they report ~3 %; from their own Tables 6-8 an RX2 ACK at SF12 (991 ms at 38 mA)
    adds 12-18 %, which we keep (conservative: overstates the cost of confirmation)."""
    u7, c7 = lora_report_energy(7), lora_report_energy(7, confirmed=True)
    u12, c12 = lora_report_energy(12), lora_report_energy(12, confirmed=True)
    assert c7 < u7
    assert 1.0 < c12 / u12 < 1.2
