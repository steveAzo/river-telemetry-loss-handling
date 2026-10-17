"""Phase 4 energy model: per-report radio energy (NB-IoT, LoRaWAN) and node lifetime.

Daily energy of a node that samples every cycle and transmits N_r reports per day:
    E_day = 86400 * (P_host_sleep + P_radio_sleep)              sleep floor
          + N_s * P_host_on * t_sense                            sensing (identical for every scheme)
          + N_r * (E_radio_report + P_host_on * t_connected)     reporting (what DPS reduces)
lifetime = E_battery / E_day. Ideal battery (no self-discharge), as in papers 09, 10, 11.
"""
import math

from . import params as P


# ------------------------------------------------------------------ LoRaWAN (Casals 2017, Eqs 5-11)
def lora_airtime_ms(sf, phy_payload, bw=125e3, cr=1, n_pre=8, crc=1):
    """time on air of a LoRa frame (explicit header); phy_payload in bytes"""
    tsym = (2 ** sf) / bw * 1e3
    de = 1 if sf >= 11 else 0
    n_phy = 8 + max(math.ceil((28 + 8 * phy_payload + 16 * crc - 4 * sf) / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (n_pre + 4.25) * tsym + n_phy * tsym


def lora_frame_ms(sf, frm_payload, uplink=True):
    """data frame: MHDR 1 + FHDR 7 + FPort 1 + payload + MIC 4; ACK (no payload): 12 bytes, no CRC"""
    if frm_payload == 0:
        return lora_airtime_ms(sf, 12, crc=1 if uplink else 0)
    return lora_airtime_ms(sf, 13 + frm_payload, crc=1 if uplink else 0)


def lora_report_energy(sf, frm_payload=20, confirmed=False, p_rx1=None, rx2_sf=12):
    """energy (J) of one report incl. receive windows, from Casals Tables 5-8.
    p_rx1: probability the ACK arrives in RX1. Default = Casals' OBSERVED behaviour (Sec. 4.2): all
    ACKs in RX1 for DR4-DR5 (SF7-8), all in RX2 for DR0-DR3 (SF9-12); RX2 uses DR0 (SF12, EU868).
    (Their p = 0.5 is only a modelling assumption; with it confirmed would look slightly dearer.)"""
    if p_rx1 is None:
        p_rx1 = 1.0 if sf <= 8 else 0.0
    tsym = (2 ** sf) / 125e3 * 1e3
    trx1 = (8 if sf >= 11 else 12) * tsym
    ttx = lora_frame_ms(sf, frm_payload)
    dur = {"tx": ttx, "rx1": trx1, "wait rx2": P.RECEIVE_DELAY_2 - P.RECEIVE_DELAY_1 - trx1}
    q_unack = sum((dur.get(n) if d is None else d) * i for n, d, i in P.LORA_STATES_UNACK)   # uC
    if not confirmed:
        return q_unack * 1e-6 * P.V_LORA
    # ACK in RX1 (Table 7): no second window; ACK received at the uplink SF; longer radio-off
    q1 = (169.2 * 22.1 + 80.4 * 13.7 + ttx * 82.8 + 988.4 * 27.1
          + lora_frame_ms(sf, 0, uplink=False) * P.LORA_I_RX_ACK[1]
          + P.LORA_TOFF_ACK * 13.4 + 272.5 * 20.9 + 37.5 * 13.4)
    # ACK in RX2 (Table 8): as unacknowledged but RX2 lasts the ACK airtime at the RX2 data rate
    q2 = (q_unack - 33.0 * 35.0 + lora_frame_ms(rx2_sf, 0, uplink=False) * P.LORA_I_RX_ACK[2]
          - 147.4 * 13.2 + P.LORA_TOFF_ACK * 13.4)
    return (p_rx1 * q1 + (1 - p_rx1) * q2) * 1e-6 * P.V_LORA


def lora_active_s(sf, frm_payload=20):
    return (sum(d for _, d, _ in P.LORA_STATES_UNACK if d is not None)
            + lora_frame_ms(sf, frm_payload) + P.RECEIVE_DELAY_2 - P.RECEIVE_DELAY_1) / 1e3


# ------------------------------------------------------------------ radio profiles
def radio(name):
    """dict: e_report (J, unconfirmed), e_report_ack (J, confirmed), p_sleep (W), t_conn (s)"""
    if name.startswith("NB-IoT"):
        _, mod, mode = name.split()                 # e.g. "NB-IoT BC95 RAI"
        m = P.NBIOT[mod]
        if mode == "RAI":
            return {"e_report": m["rai200"], "e_report_ack": m["rai400"], "p_sleep": m["psm"],
                    "t_conn": P.NBIOT_T_CONNECTED}
        if mode == "default":
            return {"e_report": m["default"], "e_report_ack": m["default"], "p_sleep": m["psm"],
                    "t_conn": P.NBIOT_T_CONNECTED_DEFAULT}
        if mode == "bad":                            # RAI-400 under poor coverage
            return {"e_report": m["rai400_bad"], "e_report_ack": m["rai400_bad"], "p_sleep": m["psm"],
                    "t_conn": P.NBIOT_T_CONNECTED + 1.0}
    if name.startswith("LoRaWAN"):
        sf = int(name.split("SF")[1])
        return {"e_report": lora_report_energy(sf), "e_report_ack": lora_report_energy(sf, confirmed=True),
                "p_sleep": P.LORA_I_SLEEP * 1e-3 * P.V_LORA, "t_conn": lora_active_s(sf)}
    raise ValueError(name)


RADIOS = ["NB-IoT BC95 RAI", "NB-IoT N211 RAI", "NB-IoT N211 default", "NB-IoT N211 bad",
          "LoRaWAN SF7", "LoRaWAN SF12"]


# ------------------------------------------------------------------ node energy and lifetime
def daily_energy(samples_per_day, reports_per_day, radio_profile, t_sense=P.T_SENSE["typical"],
                 confirmed=False, host=True):
    """J/day, split into components. host=False reproduces radio-only models (papers 10, 11)."""
    r = radio_profile
    e_rep = r["e_report_ack"] if confirmed else r["e_report"]
    sleep = 86400 * (r["p_sleep"] + (P.P_HOST_SLEEP if host else 0.0))
    sense = samples_per_day * P.P_HOST_ON * t_sense if host else 0.0
    report = reports_per_day * (e_rep + (P.P_HOST_ON * r["t_conn"] if host else 0.0))
    return {"sleep": sleep, "sense": sense, "report": report, "total": sleep + sense + report}


def lifetime_years(e_day_total, battery_j):
    return battery_j / e_day_total / 365.0
