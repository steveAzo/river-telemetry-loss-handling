"""Energy parameters for Phase 4, each with its source. Values marked RANGE are uncertain and are
swept in the sensitivity analysis instead of being fixed.

Units: joules (J), watts (W), seconds (s), volts (V).
"""

# ---------------------------------------------------------------- node platform (host MCU + sensors)
# Libelium Waspmote datasheet values (development.libelium.com / cloud.libelium.com docs, retrieved
# 2026-10-04 via web search): ON 17 mA, deep sleep 33 uA, hibernate 7 uA. Smart Water sensor board:
# minimum constant 1.6 mA while powered (DO probe 160 uA, pH 170 uA).
V_NODE = 3.7                                   # Li-ion nominal (Waspmote battery)
P_HOST_ON = (17e-3 + 1.6e-3) * V_NODE          # awake with sensor board powered: ~69 mW
P_HOST_SLEEP = 33e-6 * V_NODE                  # deep sleep, RTC wake-up: ~0.12 mW
T_SENSE = {"fast": 1.0, "typical": 5.0, "slow": 15.0, "very slow": 30.0}   # RANGE: awake s/sample
# (probe settling is not documented in the sources we hold; DO and pH probes typically need seconds)

# ---------------------------------------------------------------- batteries
BATTERIES = {
    "6600 mAh Li-ion (Weija node, paper 22)": 6.6 * 3600 * V_NODE,   # 87.9 kJ
    "5 Wh (3GPP reference, papers 10/11)": 5 * 3600.0,                # 18 kJ
}

# ---------------------------------------------------------------- NB-IoT (Michelinakis 2021, paper 11)
# Energy of the Connected state per report, module only, median, 20-byte UDP, good coverage unless
# stated. RAI-200 = release after uplink (unconfirmed); RAI-400 = release after the reply (we use it
# as the cost of a CONFIRMED uplink: application-level ACK echoed by the server); default = no RAI,
# inactivity timer 10-20 s. Tables IV, V, VI, VIII. Connected duration with RAI ~3.1-3.2 s (Sec. V-B).
# PSM sleep: 10.61 uW (BC95), 9.35 uW (N211), Sec. VI-A. TAU ~ one RAI-200 report (Sec. IX).
NBIOT = {
    "BC95": {"rai200": 0.11, "rai400": 0.12, "default": 0.82, "rai400_bad": 1.331, "psm": 10.61e-6},  # Op2
    "N211": {"rai200": 0.31, "rai400": 0.33, "default": 1.27, "rai400_bad": 0.427, "psm": 9.35e-6},   # Op2
}
NBIOT_T_CONNECTED = 3.2                         # s, RAI (host stays awake while the modem works)
NBIOT_T_CONNECTED_DEFAULT = 3.2 + 15.0          # s, + typical inactivity timer (10-20 s)

# ---------------------------------------------------------------- LoRaWAN (Casals 2017, paper 09)
# MultiConnect mDot (SX1272), EU868, 11 dBm, Tables 5-8 (durations ms, currents mA). Energy = I*V*t
# at V_LORA. ACK received in RX1 or RX2 with p = 0.5 each (their assumption).
V_LORA = 3.3
LORA_STATES_UNACK = [  # (name, duration ms or None if computed, current mA)
    ("wake up", 168.2, 22.1), ("radio prep", 83.8, 13.3), ("tx", None, 83.0),
    ("wait rx1", 983.3, 27.0), ("rx1", None, 38.1), ("wait rx2", None, 27.1), ("rx2", 33.0, 35.0),
    ("radio off", 147.4, 13.2), ("postproc", 268.0, 21.0), ("turn off", 38.6, 13.3)]
LORA_I_SLEEP = 45e-3                            # mA
LORA_TOFF_ACK = 337.8                           # ms, radio off after an ACK is processed
LORA_I_RX_ACK = {1: 31.8, 2: 38.0}              # mA while receiving the ACK in RX1 / RX2
RECEIVE_DELAY_1, RECEIVE_DELAY_2 = 1000.0, 2000.0   # ms (LoRaWAN defaults)
