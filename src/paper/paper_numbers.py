"""Every number quoted in the Paper 2 draft, generated from result files (never typed by hand).

Writes draft/numbers.tex (one \\newcommand per number, each with a % source comment) and the table
bodies draft/tables/*.tex. Ranges, comparisons and orderings used in the text are computed and
ASSERTED here, so a claim like "A is larger than B" cannot drift from the data.
Usage (from Paper2/): python -I src/paper/paper_numbers.py
"""
import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "src/scoping")
from outage_models import FITTERS  # noqa: E402

OUT = Path("draft")
TAB = OUT / "tables"
MACROS = []          # (name, value, source)
OUT.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)


# ------------------------------------------------------------------ formatting helpers
def num(x, d=0):
    """Plain number with thousands separators (IEEE style: 19,090) and d decimals."""
    s = f"{x:,.{d}f}"
    return s


def pct(x, d=1):
    """Fraction -> percent string with d decimals, e.g. 0.4595 -> 46.0\\%."""
    return f"{100 * x:.{d}f}\\%"


def pp(x, d=1):
    """Signed percentage-point difference from a fraction difference, typeset with a true minus.
    A value that rounds to zero is printed as 0 (never as -0)."""
    v = round(100 * x, d)
    if v == 0:
        return f"${0:.{d}f}$"
    return f"${v:+.{d}f}$"


def signed(x, d=2):
    """Signed number with a true minus sign (math mode)."""
    return f"${x:+.{d}f}$"


def times(x, d=2):
    return f"{x:.{d}f}$\\times$"


def M(name, value, source):
    assert re.fullmatch(r"[A-Za-z]+", name), name
    assert name not in [m[0] for m in MACROS], f"duplicate macro {name}"
    MACROS.append((name, str(value), source))


# ============================================================ §IV outages: InWaterSense, Weija
def outages_water():
    io = pd.read_csv("results/scoping/inws_outages.csv")
    allrow = io[io.bin == "ALL"].iloc[0]
    one = io[io.bin.str.startswith("1 slot")].iloc[0]
    day = io[io.bin.str.startswith(">= 142")].iloc[0]
    cyc = pd.read_csv("data/clean/inws_cycles.csv", usecols=["node"])
    delivered = int((cyc.node == 1).sum())
    lost = int(allrow.lost_slots)
    M("inwsDelivered", num(delivered), "data/clean/inws_cycles.csv node 1 rows")
    M("inwsMissing", num(lost), "results/scoping/inws_outages.csv ALL.lost_slots")
    M("inwsLoss", pct(lost / (lost + delivered)), "inws_outages: lost/(lost+delivered)")
    M("inwsOutages", num(int(allrow.events)), "inws_outages ALL.events")
    M("inwsOneSlotEvents", pct(one.event_share), "inws_outages 1-slot event_share")
    M("inwsOneSlotLost", pct(one.lost_share), "inws_outages 1-slot lost_share")
    M("inwsDayEvents", num(int(day.events)), "inws_outages >=1 day events")
    M("inwsDayEventShare", pct(day.event_share), "inws_outages >=1 day event_share")
    ci = pd.read_csv("results/scoping/outage_ci.csv")
    r24 = ci[(ci.record.str.startswith("InWater")) & (ci.L_h == "24")].iloc[0]
    r6 = ci[(ci.record.str.startswith("InWater")) & (ci.L_h == "6")].iloc[0]
    assert abs(r24.share_obs - day.lost_share) < 1e-6, "two scripts disagree on the >=1 day share"
    M("inwsDayLost", pct(r24.share_obs), "outage_ci.csv InWaterSense L=24 share_obs")
    M("inwsDayLostLo", pct(r24.ci_lo), "outage_ci.csv bootstrap 2.5%")
    M("inwsDayLostHi", pct(r24.ci_hi), "outage_ci.csv bootstrap 97.5%")
    M("inwsSixLost", pct(r6.share_obs), "outage_ci.csv InWaterSense L=6 share_obs")
    M("inwsSixLostLo", pct(r6.ci_lo), "outage_ci.csv")
    M("inwsSixLostHi", pct(r6.ci_hi), "outage_ci.csv")
    sp = ci[(ci.record.str.startswith("InWater")) & (ci.L_h == "spearman")].iloc[0]
    M("inwsRhoNextOut", signed(sp.rho_out_next_out), "outage_ci.csv spearman")
    M("inwsRhoNextUp", signed(sp.rho_out_next_up), "outage_ci.csv spearman")
    assert sp.p_out_next_out < 1e-3 and sp.p_out_next_up < 1e-3
    spw = ci[(ci.record.str.startswith("Weija")) & (ci.L_h == "spearman")].iloc[0]
    M("weijaRhoNextOut", signed(spw.rho_out_next_out), "outage_ci.csv spearman")
    M("weijaPNextOut", f"{spw.p_out_next_out:.2f}", "outage_ci.csv spearman")
    M("weijaPNextUp", f"{spw.p_out_next_up:.2f}", "outage_ci.csv spearman")
    max_slots = int(re.search(r"max (\d+)", open("results/rerun_check/inws_outages.log").read()).group(1))
    M("inwsMaxOutageDays", f"{max_slots * 611 / 86400:.1f}", "inws_outages.log max slots x 611 s")

    w = pd.read_csv("results/scoping/weija_outages.csv")
    cond = w[w.probe.str.startswith("Conductivity")].iloc[0]
    wc = ci[(ci.record.str.startswith("Weija")) & (ci.L_h == "24")].iloc[0]
    M("weijaStreams", num(len(w)), "weija_outages.csv rows")
    M("weijaCondLoss", pct(cond.loss), "weija_outages.csv conductivity loss")
    M("weijaCondOutages", num(int(cond.events)), "weija_outages.csv conductivity events")
    M("weijaCondDayLost", pct(cond.lost_share_ge_1d), "weija_outages.csv conductivity")
    assert abs(cond.lost_share_ge_1d - wc.share_obs) < 1e-4
    M("weijaCondDayLostLo", pct(wc.ci_lo), "outage_ci.csv Weija")
    M("weijaCondDayLostHi", pct(wc.ci_hi), "outage_ci.csv Weija")
    M("weijaCondDayN", num(int(wc.n_outages_ge)), "outage_ci.csv Weija n outages >= 1 d")
    M("weijaDayLostMin", pct(w.lost_share_ge_1d.min()), "weija_outages.csv min over streams")
    M("weijaDayLostMax", pct(w.lost_share_ge_1d.max()), "weija_outages.csv max over streams")
    M("weijaMaxOutageDays", f"{w.max_outage_d.max():.1f}", "weija_outages.csv max")
    return io, w


# ============================================================ §IV outages: LoRaWAN (LoED, UVA)
def outages_lorawan():
    log = open("results/scoping/loed_full.log", encoding="utf-8").read()
    g = lambda pat: re.search(pat, log)
    m = g(r"unique uplink frames: ([\d,]+); devices ([\d,]+); gateways (\d+)")
    M("loedFrames", m.group(1), "loed_full.log"); M("loedDevices", m.group(2), "loed_full.log")
    M("loedGateways", m.group(3), "loed_full.log")
    m = g(r"devices with >= 200 frames: (\d+); well-heard \(radio loss < 20%\): (\d+)")
    M("loedDevicesTwoHundred", num(int(m.group(1))), "loed_full.log"); M("loedWellHeard", m.group(2), "loed_full.log")
    m = g(r"pooled radio loss ([\d.]+); median per device ([\d.]+); P\(loss \| previous loss\) ([\d.]+)")
    M("loedRadioLoss", pct(float(m.group(1))), "loed_full.log"); M("loedCondLoss", f"{float(m.group(3)):.2f}", "loed_full.log")
    loedp = float(m.group(1))
    m = g(r"radio-loss bursts: (\d+); length 1: ([\d.]+); 2-5: ([\d.]+); >5: ([\d.]+); max (\d+)")
    M("loedBursts", num(int(m.group(1))), "loed_full.log"); M("loedBurstOne", pct(float(m.group(2)), 0), "loed_full.log")
    M("loedBurstFive", pct(float(m.group(2)) + float(m.group(3)), 0), "loed_full.log (length 1 + 2-5)")
    m = g(r"observed ([\d.]+); independence baseline \(random shifts \+-7 d, 5 draws\) ([\d.]+) \[([\d.]+), ([\d.]+)\]")
    M("loedCoLoss", pct(float(m.group(1))), "loed_full.log"); M("loedCoLossBase", pct(float(m.group(2))), "loed_full.log")
    M("loedCoLossLo", pct(float(m.group(3))), "loed_full.log"); M("loedCoLossHi", pct(float(m.group(4))), "loed_full.log")
    assert float(m.group(3)) <= float(m.group(1)) <= float(m.group(4)), "co-loss outside the baseline range"
    gw = pd.read_csv("results/scoping/loed_full_gateways.csv")
    full = gw[gw.availability >= 0.999]
    M("loedFullGateways", num(len(full)), "loed_full_gateways.csv availability >= 0.999")

    ul = open("results/scoping/uva_loss.log", encoding="utf-8").read()
    u = lambda pat: re.search(pat, ul)
    m = u(r"system availability \(10-min bins\): ([\d.]+); outages (\d+); median ([\d.]+) h; max ([\d.]+) h; down-hours in outages >= 24 h ([\d.]+)")
    M("uvaAvail", pct(float(m.group(1)), 2), "uva_loss.log"); M("uvaSysOutages", m.group(2), "uva_loss.log")
    M("uvaSysMedianH", m.group(3), "uva_loss.log"); M("uvaSysMaxH", m.group(4), "uva_loss.log")
    M("uvaSysDayShare", pct(float(m.group(5)), 0), "uva_loss.log")
    m = u(r"all missing frames ([\d,]+): system ([\d.]+), gateway ([\d.]+), radio ([\d.]+)")
    M("uvaMissing", m.group(1), "uva_loss.log"); M("uvaSysShare", pct(float(m.group(2)), 1), "uva_loss.log")
    M("uvaRadioShare", pct(float(m.group(4)), 1), "uva_loss.log"); M("uvaGwShare", pct(float(m.group(3)), 1), "uva_loss.log")
    m = u(r"pooled loss ([\d.]+)"); M("uvaLoss", pct(float(m.group(1))), "uva_loss.log")
    m = u(r"outage runs (\d+); length 1: ([\d.]+)"); M("uvaRuns", num(int(m.group(1))), "uva_loss.log")
    M("uvaRunsOne", pct(float(m.group(2)), 0), "uva_loss.log")
    m = u(r"gatewayC: up [\d.]+ of system-up time; gateway-only outages \d+, median ([\d.]+) h")
    M("uvaGwCDays", f"{float(m.group(1)) / 24:.1f}", "uva_loss.log gateway C outage hours / 24")
    m = u(r"dry vs rain: median ([\d.]+) vs ([\d.]+); pairs with more loss in rain ([\d.]+) of (\d+); median difference ([-\d.]+); Wilcoxon p = ([\d.]+)")
    M("uvaRainDry", pct(float(m.group(1)), 2), "uva_loss.log"); M("uvaRainWet", pct(float(m.group(2)), 2), "uva_loss.log")
    M("uvaRainPairs", m.group(4), "uva_loss.log"); M("uvaRainP", m.group(6), "uva_loss.log")
    sens = pd.read_csv("results/scoping/uva_loss_sensors.csv")
    M("uvaSensors", num(len(sens)), "uva_loss_sensors.csv")
    s4 = sens[sens.s == "sensor04"].iloc[0]
    M("uvaSensorFourRadio", pct(s4.radio / (s4.rx + s4.missing), 2), "uva_loss_sensors.csv sensor04 radio/(rx+missing)")
    return loedp


# ============================================================ §IV outage models (AIC table)
def outage_models_table():
    om = pd.read_csv("results/scoping/outage_models.csv")
    om = om[om.what == "outage"]
    runs = pd.read_csv("results/scoping/uva_loss_runs.csv").len.to_numpy(float)
    rows = {}
    for rec in ("InWaterSense node 1", "Weija conductivity"):
        x = om[om.record == rec].set_index("model").aic
        rows[rec] = x
    rows["UVA (all runs)"] = pd.Series({k: 2 * f(runs)[2] - 2 * f(runs)[1] for k, f in FITTERS.items()})
    names = {"geom": "Geometric (memoryless)", "geom2": "Two-geometric mixture", "dlnorm": "Discrete lognormal", "zeta": "Discrete power law"}
    lines = []
    for mdl in ("geom", "geom2", "dlnorm", "zeta"):
        cells = []
        for rec, x in rows.items():
            best = x.idxmin()
            v = num(x[mdl], 0)
            cells.append(f"\\textbf{{{v}}}" if mdl == best else v)
        lines.append(f"{names[mdl]} & " + " & ".join(cells) + r" \\")
    (TAB / "tab_outage_models.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for rec, key in (("InWaterSense node 1", "Inws"), ("Weija conductivity", "Weija"), ("UVA (all runs)", "Uva")):
        x = rows[rec]
        M(f"aicBest{key}", names[x.idxmin()].lower(), "outage model AIC table")
        M(f"aicGeomGap{key}", num(x["geom"] - x.min(), 0), "AIC(geometric) - AIC(best)")
    return rows


# ============================================================ §V loss handling under real outages
RADIO_NB, RADIO_7, RADIO_12 = "NB-IoT N211 RAI (search 10 s)", "LoRaWAN SF7", "LoRaWAN SF12"


def strategies():
    d = pd.read_csv("results/scoping/loss_handling.csv")
    d["delivered"] = d.on_time + d.late
    d["label"] = d.strategy + d.probe_cap_h.map(lambda h: "" if h == 0 else f"/bo{int(h)}")

    def get(tr, ra, lab, p=0.0):
        x = d[(d.trace == tr) & (d.radio == ra) & (d.label == lab) & (d.p_radio == p)]
        assert len(x) == 1, (tr, ra, lab, p, len(x))
        return x.iloc[0]

    # ---- table: InWaterSense record, no extra radio loss
    rows = [("Unconfirmed, every reading", "unconf"), ("Unconfirmed + back-off (NB-IoT only)", "unconf_backoff/bo6"),
            ("ARQ (8 attempts LoRaWAN; 3 NB-IoT)", "arq"), ("ARQ, 3 attempts (LoRaWAN)", "arq3"),
            ("Confirmed + buffer + back-off", "arq_buffer/bo6"), ("Hourly batch + buffer + back-off", "batch1h/bo6"),
            ("6-hourly batch + buffer + back-off", "batch6h/bo6")]
    lines = []
    for name, lab in rows:
        cells = []
        for ra in (RADIO_NB, RADIO_7, RADIO_12):
            x = d[(d.trace == "InWaterSense") & (d.radio == ra) & (d.label == lab) & (d.p_radio == 0)]
            cells.append(num(x.iloc[0].energy_j_per_day, 1) if len(x) else "--")
        ref = get("InWaterSense", RADIO_NB if lab == "unconf_backoff/bo6" else RADIO_7, lab)
        cells += [pct(ref.delivered), pct(ref.within_1h)]
        lines.append(f"{name} & " + " & ".join(cells) + r" \\")
    (TAB / "tab_strategies.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- ranges over every configuration (both records, both p_radio, all radios / search times)
    lo = d[d.radio.str.startswith("LoRaWAN")]
    r8, r3, gain = [], [], {0.0: [], 0.096: []}
    for (tr, ra, p), g in lo.groupby(["trace", "radio", "p_radio"]):
        u = g[g.label == "unconf"].iloc[0]
        r8.append(g[g.label == "arq"].iloc[0].energy_j_per_day / u.energy_j_per_day)
        r3.append(g[g.label == "arq3"].iloc[0].energy_j_per_day / u.energy_j_per_day)
        gain[p].append(g[g.label == "arq"].iloc[0].delivered - u.delivered)
    M("arqEightMin", times(min(r8)), "loss_handling.csv LoRaWAN arq/unconf energy, min over records x SF x p")
    M("arqEightMax", times(max(r8)), "same, max")
    M("arqThreeMin", times(min(r3)), "loss_handling.csv LoRaWAN arq3/unconf energy, min")
    M("arqThreeMax", times(max(r3)), "same, max")
    assert max(abs(x) for x in gain[0.0]) < 1e-9, "ARQ must recover nothing without radio loss"
    M("arqGainMin", pp(min(gain[0.096])), "arq - unconf delivered share at p_radio = 0.096, min (pp)")
    M("arqGainMax", pp(max(gain[0.096])), "same, max (pp)")
    bo, buf_nb, buf_lo, bat, w1 = [], [], [], [], []
    for (tr, ra, p), g in d.groupby(["trace", "radio", "p_radio"]):
        u = g[g.label == "unconf"].iloc[0]
        isnb = ra.startswith("NB")
        fair = g[g.label == "unconf_backoff/bo6"].iloc[0] if isnb else u
        if isnb:
            bo.append(u.energy_j_per_day / fair.energy_j_per_day)
        b = g[g.label == "arq_buffer/bo6"].iloc[0]
        (buf_nb if isnb else buf_lo).append(b.energy_j_per_day / fair.energy_j_per_day - 1)
        b1 = g[g.label == "batch1h/bo6"].iloc[0]
        bat.append(fair.energy_j_per_day / b1.energy_j_per_day)
        w1.append(b1.within_1h - u.within_1h)
        assert b.delivered > 0.999 and b1.delivered > 0.999, "buffering must deliver everything"
    M("backoffMin", times(min(bo)), "NB-IoT unconf / unconf_backoff energy, min over records x search time x p")
    M("backoffMax", times(max(bo)), "same, max")
    M("bufNbMin", pp(min(buf_nb)), "NB-IoT arq_buffer vs unconf_backoff energy change, min (percent)")
    M("bufNbMax", pp(max(buf_nb)), "same, max")
    M("bufLoMin", pp(min(buf_lo)), "LoRaWAN arq_buffer vs unconf energy change, min (percent)")
    M("bufLoMax", pp(max(buf_lo)), "same, max")
    M("batchSaveMin", times(min(bat)), "fair baseline / batch1h energy, min over all configurations")
    M("batchSaveMax", times(max(bat)), "same, max")
    M("batchWithinMin", pp(min(w1)), "batch1h - unconf within-1h share, min (pp)")
    M("batchWithinMax", pp(max(w1)), "same, max (pp)")
    M("nConfigs", num(d.groupby(["trace", "radio", "p_radio"]).ngroups), "loss_handling.csv record x radio x p_radio")
    i7 = get("InWaterSense", RADIO_7, "unconf"); a7 = get("InWaterSense", RADIO_7, "arq")
    bb = get("InWaterSense", RADIO_7, "batch1h/bo6")
    M("inwSevenUnconfE", num(i7.energy_j_per_day, 1), "InWaterSense SF7 unconf J/day")
    M("inwSevenUnconfLife", num(i7.lifetime_y, 2), "InWaterSense SF7 unconf lifetime (y)")
    M("inwSevenArqE", num(a7.energy_j_per_day, 1), "InWaterSense SF7 arq J/day")
    M("inwSevenArqLife", num(a7.lifetime_y, 2), "InWaterSense SF7 arq lifetime (y)")
    M("inwSevenBatchE", num(bb.energy_j_per_day, 1), "InWaterSense SF7 batch1h J/day")
    M("inwSevenBatchLife", num(bb.lifetime_y, 2), "InWaterSense SF7 batch1h lifetime (y)")
    M("inwRecordLossSim", pct(1 - i7.delivered), "replayed InWaterSense link: unconf lost share (record grid)")


# ============================================================ §VI river chains (reconstruction)
CHAINS = ["delaware", "illinois", "tualatin", "clackamas", "mckenzie", "monongahela", "youghiogheny", "schuylkill", "klamath"]


def chains():
    # explicit list: the pattern chain_*.csv would also match chain_availability.csv and chain_sites.csv
    d = pd.concat((pd.read_csv(f"results/revision/chains/chain_{c}.csv", dtype={"target": str, "neighbour": str}) for c in CHAINS),
                  ignore_index=True)
    assert d.param.notna().all() and d.target.notna().all()
    d["best_own"] = d[["med_persist", "med_diel"]].min(axis=1)
    d["best_nb"] = d[["med_nb_delta", "med_diel_nb"]].min(axis=1)
    sites = set(d.target) | set(d.neighbour)
    assert len(sites) == 27, len(sites)
    M("chainCount", num(d.chain.nunique()), "results/revision/chains/chain_<9 chains>.csv (D5 rerun)")
    M("chainSites", num(len(sites)), "unique sites in the 9 chain files")
    npairs = d[d.H_h == 24].groupby("param").size()
    M("chainPairsMin", num(npairs.min()), "ordered pairs per parameter, min")
    M("chainPairsMax", num(npairs.max()), "ordered pairs per parameter, max")
    M("chainOutages", num(int(d.n.median())), "median number of simulated gaps per pair x param x length")
    lines = []
    for p in ("T", "DO", "pH", "EC"):
        for H in (1, 24):
            g = d[(d.param == p) & (d.H_h == H)]
            dd = 3 if p == "pH" else 2
            lines.append(f"{p} & {H} & {num(g.med_persist.median(), dd)} & {num(g.med_diel.median(), dd)} & "
                         f"{num(g.best_nb.median(), dd)} & {pct((g.best_nb < g.best_own).mean(), 0)} & "
                         f"{num(g.med_interp.median(), dd)} & {num(g.med_interp_nb.median(), dd)} & "
                         f"{pct((g.med_interp_nb < g.med_interp).mean(), 0)} \\\\")
        if p != "EC":
            lines.append(r"\addlinespace")
    (TAB / "tab_chains.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # relative gains in the text, at 24 h; pairs whose baseline error is exactly 0 (pH recorded in 0.1 steps
    # at a slowly varying site) make a relative gain undefined: they are excluded and counted
    excl = 0
    for p in ("T", "DO", "pH", "EC"):
        g = d[(d.param == p) & (d.H_h == 24)]
        g1, g2 = g[g.best_own > 0], g[g.med_interp > 0]
        assert set(g.index[g.med_interp <= 0]) == set(g.index[g.best_own <= 0]), "same pairs excluded from both gains"
        excl += (len(g) - len(g1))
        if len(g) > len(g1):
            assert p == "pH" and g[g.best_own <= 0].target.nunique() == 1
            M("chainExclSite", g[g.best_own <= 0].target.iloc[0], "the single site whose pairs are excluded")
        key = {"T": "T", "DO": "Do", "pH": "Ph", "EC": "Ec"}[p]
        M(f"chainRtWin{key}", pct((g.best_nb < g.best_own).mean(), 0), f"chains {p} 24 h: share of pairs where a neighbour method beats own data (real time)")
        M(f"chainRtGain{key}", pp((1 - g1.best_nb / g1.best_own).median(), 1), f"chains {p} 24 h: median relative real-time gain, pairs with positive baseline")
        M(f"chainBfWin{key}", pct((g.med_interp_nb < g.med_interp).mean(), 0), f"chains {p} 24 h: share of pairs where the neighbour improves bridging")
        M(f"chainBfGain{key}", pp((1 - g2.med_interp_nb / g2.med_interp).median(), 1), f"chains {p} 24 h: median relative bridging gain, pairs with positive baseline")
        M(f"chainDielBeatsPersist{key}", pct((g.med_diel < g.med_persist).mean(), 0), f"chains {p} 24 h: share of pairs where own diel beats persistence")
    M("chainGainExcluded", num(excl), "24 h pairs excluded from relative gains (zero baseline error)")
    best1 = d[d.H_h == 1][["ok_persist", "ok_diel"]].max(axis=1)
    best24 = d[d.H_h == 24][["ok_persist", "ok_diel", "ok_nb_delta", "ok_diel_nb", "ok_interp", "ok_interp_nb"]].max(axis=1)
    M("chainTolOneH", pct(best1.median(), 0), "chains: median over pairs x params of the best own-data real-time method within tolerance, 1 h")
    M("chainTolDayMed", pct(best24.median(), 0), "chains: median over pairs x params of the best of ALL methods within tolerance, 24 h")
    M("chainTolDayQ", pct(best24.quantile(0.75), 0), "chains: 75th percentile of the same, 24 h")
    return d


# ============================================================ §VIII design evaluation (pre-registered)
LINKS = [("none", "No outage"), ("UVA", "UVA"), ("Weija", "Weija"), ("InWaterSense", "InWaterSense")]
DD = "results/design"


def design():
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = sorted(elig[elig.status == "ok"].site)
    M("designSites", num(len(ok)), "design_site_eligibility.csv status ok")
    M("designSitesExcluded", num(int((elig.status != "ok").sum())), "design_site_eligibility.csv not ok")
    ev = pd.concat((pd.read_csv(f"{DD}/{s}_events.csv", dtype={"site": str}) for s in ok), ignore_index=True)
    one = ev[(ev.trace == "none") & (ev.radio == RADIO_7) & (ev.strategy == "design")]
    M("designEvents", num(len(one)), "events rows for one link x radio x strategy = injected events")
    det = one.groupby(["setting", "site"]).node_detected.mean().groupby("setting").median()
    for st, key in (("step5", "StepFive"), ("step8", "StepEight"), ("ramp5", "RampFive"), ("ramp8", "RampEight")):
        M(f"detect{key}", pct(det[st], 0), f"median over sites of the share of {st} events detected")
    M("detectAll", pct(one.node_detected.mean(), 1), "share of all injected events detected (pooled)")
    en = pd.concat((pd.read_csv(f"{DD}/{s}_energy.csv", dtype={"site": str}) for s in ok), ignore_index=True)
    fa = en.drop_duplicates("site").fa_per30d_param
    M("faMedian", num(fa.median(), 1), "median over sites of false alarms per parameter per 30 days")
    al = en[(en.setting == "clean") & (en.strategy == "design") & (en.trace == "none") & (en.radio == RADIO_7)].alarms_per_day
    M("alarmsPerDay", num(al.median(), 2), "median over sites of node alarms per day (clean series)")

    h1 = pd.read_csv(f"{DD}/summary_H1_latency_up.csv"); h7 = pd.read_csv(f"{DD}/summary_H7_latency_bounded.csv")
    h2 = pd.read_csv(f"{DD}/summary_H2_energy.csv"); h6 = pd.read_csv(f"{DD}/summary_H6_energy_bounded.csv")
    h3 = pd.read_csv(f"{DD}/summary_H3_outage_onset.csv"); h4 = pd.read_csv(f"{DD}/summary_H4_picture.csv")
    h5 = pd.read_csv(f"{DD}/summary_H5_picture_bounded.csv")
    assert h1.H1_pass.all() and h2.H2_pass.all() and h5.H5_pass.all() and h6.H6_pass.all() and h7.H7_pass.all()
    M("hOnePass", f"{int(h1.H1_pass.sum())}/{len(h1)}", "summary_H1"); M("hTwoPass", f"{int(h2.H2_pass.sum())}/{len(h2)}", "summary_H2")
    M("hFourPass", f"{int(h4.H4_pass.sum())}/{len(h4)}", "summary_H4"); M("hFivePass", f"{int(h5.H5_pass.sum())}/{len(h5)}", "summary_H5")
    M("hSixPass", f"{int(h6.H6_pass.sum())}/{len(h6)}", "summary_H6"); M("hSevenPass", f"{int(h7.H7_pass.sum())}/{len(h7)}", "summary_H7")
    fails = h4[~h4.H4_pass]
    assert set(fails.param) == {"DO", "pH"}, set(fails.param)
    M("hFourFailParams", "DO and pH", "summary_H4 failing params")
    M("hFourFailMin", pp(fails.design_minus_arq_pp.min() / 100), "summary_H4 worst failing design - arq (pp)")
    M("hFourFailMax", pp(fails.design_minus_arq_pp.max() / 100), "summary_H4 mildest failing design - arq (pp)")
    M("batchLagH", num(h1.batch_minus_design_h.median(), 2), "summary_H1 median over links x radios of batch1h - design latency (h)")
    assert h1.batch_minus_design_h.min() == h1.batch_minus_design_h.max(), "batch - design latency is not constant"
    M("batchLagPMax", f"{h1.p_batch_vs_design.max():.0e}".replace("e-0", "\\times10^{-").replace("e-", "\\times10^{-") + "}", "summary_H1 max Wilcoxon p")
    M("designOverBatchMin", f"{h2.design_over_batch.min():.3f}", "summary_H2 design / batch1h energy, min")
    M("designOverBatchMax", f"{h2.design_over_batch.max():.3f}", "summary_H2 design / batch1h energy, max")
    M("arqOverDesignMin", times(h2.arq_over_design.min()), "summary_H2 arq_buffer / design energy, min")
    M("arqOverDesignMax", times(h2.arq_over_design.max()), "summary_H2 arq_buffer / design energy, max")
    M("boundedOverBatchMin", times(h6.bounded_over_batch.min()), "summary_H6 bounded / batch1h, min")
    M("boundedOverBatchMax", times(h6.bounded_over_batch.max()), "summary_H6 bounded / batch1h, max")
    M("arqOverBoundedMin", times(h6.arq_over_bounded.min()), "summary_H6 arq_buffer / bounded, min")
    M("arqOverBoundedMax", times(h6.arq_over_bounded.max()), "summary_H6 arq_buffer / bounded, max")
    M("hFiveDiffMin", pp(h5.bounded_minus_arq_pp.min() / 100), "summary_H5 bounded - arq picture, min (pp)")
    M("hFiveDiffMax", pp(h5.bounded_minus_arq_pp.max() / 100), "summary_H5 bounded - arq picture, max (pp)")

    # ---- table: latency (link up) and energy, LoRaWAN SF7
    lines = []
    for tr, name in LINKS:
        a = h1[(h1.trace == tr) & (h1.radio == RADIO_7)].iloc[0]; b = h7[(h7.trace == tr) & (h7.radio == RADIO_7)].iloc[0]
        e2 = h2[(h2.trace == tr) & (h2.radio == RADIO_7)].iloc[0]; e6 = h6[(h6.trace == tr) & (h6.radio == RADIO_7)].iloc[0]
        assert abs(a.lat_design_h - b.lat_design_h) < 1e-9
        lines.append(f"{name} & {num(a.lat_arq_buffer_h, 2)} & {num(a.lat_batch1h_h, 2)} & {num(a.lat_design_h, 2)} & "
                     f"{num(b.lat_design_bounded_h, 2)} & {num(e2.E_arq_buffer, 1)} & {num(e2.E_batch1h, 1)} & "
                     f"{num(e2.E_design_events, 1)} & {num(e6.E_design_bounded, 1)} \\\\")
    (TAB / "tab_design.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- table: real-time picture (share within L2 tolerance), LoRaWAN SF7
    lines = []
    for tr, name in LINKS:
        for k, p in enumerate(("DO", "pH", "T", "EC")):
            a = h4[(h4.trace == tr) & (h4.radio == RADIO_7) & (h4.param == p)].iloc[0]
            b = h5[(h5.trace == tr) & (h5.radio == RADIO_7) & (h5.param == p)].iloc[0]
            assert abs(a.within_arq_buffer - b.within_arq_buffer) < 1e-9
            lead = name if k == 0 else ""
            lines.append(f"{lead} & {p} & {pct(a.within_unconf)} & {pct(a.within_arq_buffer)} & {pct(a.within_batch1h)} & "
                         f"{pct(a.within_design)} & {pct(b.within_design_bounded)} \\\\")
        if tr != "InWaterSense":
            lines.append(r"\addlinespace")
    (TAB / "tab_picture.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- events starting during an outage (pooled, SF7)
    for tr, key in (("InWaterSense", "Inws"), ("Weija", "Weija"), ("UVA", "Uva")):
        g = h3[(h3.trace == tr) & (h3.radio == RADIO_7)].set_index("strategy")
        M(f"outN{key}", num(int(g.loc["design", "n_events"])), f"summary_H3 {tr} SF7 n detected events with onset in an outage")
        M(f"outUnconfKnown{key}", pct(g.loc["unconf", "known_ever"]), f"summary_H3 {tr} unconf known ever")
        M(f"outDesignKnown{key}", pct(g.loc["design", "known_ever"]), f"summary_H3 {tr} design known ever")
        M(f"outDesignLat{key}", num(g.loc["design", "latency_median_h"], 1), f"summary_H3 {tr} design median latency (h)")
        M(f"outArqLat{key}", num(g.loc["arq_buffer", "latency_median_h"], 1), f"summary_H3 {tr} arq_buffer median latency (h)")
    lat = h3[(h3.strategy == "design")].latency_median_h
    M("outLatMin", num(lat.min(), 0), "summary_H3 design median latency, min over links x radios (h)")
    M("outLatMax", num(lat.max(), 0), "summary_H3 design median latency, max (h)")


def sensitivity():
    SD = f"{DD}/sensitivity"
    h8 = pd.read_csv(f"{SD}/summary_H8_newest_first.csv"); h9 = pd.read_csv(f"{SD}/summary_H9_picture_levels.csv")
    h10 = pd.read_csv(f"{SD}/summary_H10_energy_levels.csv")
    assert (h8["min"] >= 1.0 - 1e-12).all()
    M("fifoMinSfTwelve", pct(h8[h8.radio == RADIO_12]["fifo_min"].min(), 2), "summary_H8 FIFO min within-tolerance on SF12 (no outage)")
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = sorted(elig[elig.status == "ok"].site)
    en = pd.concat((pd.read_csv(f"{SD}/{s}_energy.csv", dtype={"site": str}) for s in ok), ignore_index=True)
    e = en[(en.level == "L2") & en.strategy.isin(["design_bounded", "design_bounded_nf"])]
    r = e.pivot_table(index=["trace", "radio", "site"], columns="strategy", values="energy_j_per_day")
    ratio = r.design_bounded_nf / r.design_bounded
    assert (ratio - 1).abs().max() <= 0.01
    M("nfRatioMin", f"{ratio.min():.3f}", "sensitivity energy nf / FIFO, min"); M("nfRatioMax", f"{ratio.max():.3f}", "max")
    for lv in ("L1", "L2", "L3"):
        a = h10[h10.level == lv]; b = h9[h9.level == lv]
        assert a["pass"].all() and b["pass"].all()
        M(f"sensArqOver{lv.replace('1', 'One').replace('2', 'Two').replace('3', 'Three')}Min", times(a.arq_over_bounded.min()), f"H10 {lv} arq / bounded min")
        M(f"sensArqOver{lv.replace('1', 'One').replace('2', 'Two').replace('3', 'Three')}Max", times(a.arq_over_bounded.max()), f"H10 {lv} arq / bounded max")
        M(f"sensBoundedOverDesign{lv.replace('1', 'One').replace('2', 'Two').replace('3', 'Three')}Min", times(a.bounded_over_design.min()), f"H10 {lv} bounded / design min")
        M(f"sensBoundedOverDesign{lv.replace('1', 'One').replace('2', 'Two').replace('3', 'Three')}Max", times(a.bounded_over_design.max()), f"H10 {lv} bounded / design max")
        M(f"sensPicMin{lv.replace('1', 'One').replace('2', 'Two').replace('3', 'Three')}", pp(b.bounded_minus_arq_pp.min() / 100), f"H9 {lv} bounded - arq picture min (pp)")
        M(f"sensPicMax{lv.replace('1', 'One').replace('2', 'Two').replace('3', 'Three')}", pp(b.bounded_minus_arq_pp.max() / 100), f"H9 {lv} bounded - arq picture max (pp)")
    l1 = h9[h9.level == "L1"].assign(d=lambda x: x.within_design - x.within_arq).groupby("param").d.median()
    for p, key in (("DO", "Do"), ("pH", "Ph"), ("T", "T"), ("EC", "Ec")):
        M(f"sensDesignShortOne{key}", pp(l1[p]), f"H9 L1 median over link x radio of plain design - arq picture, {p} (pp)")
    M("hNinePass", f"{int(h9[h9.level != 'L2']['pass'].sum())}/{int((h9.level != 'L2').sum())}", "H9 at L1 and L3")
    M("hTenPass", f"{int(h10[h10.level != 'L2']['pass'].sum())}/{int((h10.level != 'L2').sum())}", "H10 at L1 and L3")
    lines = []
    for lv, lab in (("L1", "L1 (tight)"), ("L2", "L2"), ("L3", "L3 (loose)")):
        for tr, name in (("none", "No outage"), ("InWaterSense", "InWaterSense")):
            a = h10[(h10.level == lv) & (h10.trace == tr) & (h10.radio == RADIO_7)].iloc[0]
            lines.append(f"{lab if tr == 'none' else ''} & {name} & {num(a.E_arq, 1)} & {num(a.E_design, 1)} & "
                         f"{num(a.E_bounded, 1)} & {times(a.arq_over_bounded)} \\\\")
        if lv != "L3":
            lines.append(r"\addlinespace")
    (TAB / "tab_sensitivity.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def design_extra():
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = elig[elig.status == "ok"]
    M("designCandidates", num(len(elig)), "design_site_eligibility.csv rows")
    M("designExclSparse", num(int((elig.status == "complete<50%").sum())), "status complete<50%")
    steps = ok.step_min.value_counts().sort_index()
    assert set(steps.index) <= {5.0, 15.0, 30.0, 60.0}, steps
    for st, key in ((5.0, "Five"), (15.0, "Fifteen"), (30.0, "Thirty"), (60.0, "Sixty")):
        M(f"sitesStep{key}", num(int(steps.get(st, 0))), f"eligible sites with {int(st)}-min step")
    sids = sorted(ok.site)
    en = pd.concat((pd.read_csv(f"{DD}/{s}_energy.csv", dtype={"site": str}) for s in sids), ignore_index=True)
    c = en[en.setting == "clean"].drop_duplicates("site")
    assert len(c) == len(sids)
    M("faMean", num(c.fa_per30d_param.mean(), 1), "mean over sites of false alarms per parameter per 30 days")
    M("alarmsPerDayMean", num(c.alarms_per_day.mean(), 2), "mean over sites of node alarms per day")
    ev = pd.concat((pd.read_csv(f"{DD}/{s}_events.csv", dtype={"site": str}) for s in sids), ignore_index=True)
    per = ev[(ev.trace == "none") & (ev.radio == RADIO_7) & (ev.strategy == "design")].groupby("setting").size()
    assert per.nunique() == 1
    M("eventsPerSetting", num(int(per.iloc[0])), "injected events per setting (all sites)")

    # ---- all injected events: known within 1 h (SF7)
    k = pd.read_csv(f"{DD}/summary_known_within.csv")
    k = k[k.radio == RADIO_7].set_index(["trace", "strategy"])
    for tr, key in (("none", "None"), ("InWaterSense", "Inws")):
        for s, sk in (("unconf", "Unconf"), ("arq_buffer", "Arq"), ("batch1h", "Batch"), ("design", "Design")):
            M(f"knownOne{sk}{key}", pct(k.loc[(tr, s), "known_1h"]), f"summary_known_within {tr} SF7 {s} known within 1 h")
    assert k.loc[("InWaterSense", "design"), "known_1h"] > k.loc[("InWaterSense", "arq_buffer"), "known_1h"] > k.loc[("InWaterSense", "unconf"), "known_1h"]

    # ---- events with onset in an outage: table (SF7) and ordering checks (all radios)
    h3 = pd.read_csv(f"{DD}/summary_H3_outage_onset.csv")
    g = h3.set_index(["trace", "radio", "strategy"])
    lines = []
    for tr in ("InWaterSense", "Weija", "UVA"):
        x = g.loc[(tr, RADIO_7)]
        lines.append(f"{tr} & {num(int(x.loc['design', 'n_events']))} & {pct(x.loc['unconf', 'known_ever'])} & "
                     + " & ".join(pct(x.loc[s, "known_ever"]) for s in ("arq_buffer", "design")) + " & "
                     + " & ".join(num(x.loc[s, "latency_median_h"], 1) for s in ("arq_buffer", "batch1h", "design", "design_bounded"))
                     + r" \\")
    (TAB / "tab_onset.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lat = h3.pivot_table(index=["trace", "radio"], columns="strategy", values="latency_median_h")
    # InWaterSense: design fastest of the buffering strategies on every radio
    i = lat.loc["InWaterSense"]
    assert (i.design < i[["arq_buffer", "batch1h", "design_bounded"]].min(axis=1)).all()
    M("onsetInwsGainMin", num((i.arq_buffer - i.design).min(), 1), "InWaterSense: arq - design median latency, min over radios (h)")
    M("onsetInwsGainMax", num((i.arq_buffer - i.design).max(), 1), "same, max (h)")
    # Weija: design == batch1h, both faster than arq_buffer
    w = lat.loc["Weija"]
    assert ((w.design - w.batch1h).abs() < 1e-9).all() and (w.design < w.arq_buffer).all()
    M("onsetWeijaGainMin", num((w.arq_buffer - w.design).min(), 1), "Weija: arq - design, min over radios (h)")
    M("onsetWeijaGainMax", num((w.arq_buffer - w.design).max(), 1), "Weija: arq - design, max over radios (h)")
    # UVA: arq_buffer slightly faster
    u = lat.loc["UVA"]
    assert (u.arq_buffer < u.design).all()
    M("onsetUvaLossMin", num((u.design - u.arq_buffer).min(), 1), "UVA: design - arq, min over radios (h)")
    M("onsetUvaLossMax", num((u.design - u.arq_buffer).max(), 1), "UVA: design - arq, max over radios (h)")
    # bounded vs arq: never more than this much slower
    d = (lat.design_bounded - lat.arq_buffer).max()
    M("onsetBoundedOverArqMax", num(d, 1), "max over trace x radio of bounded - arq median latency (h)")
    kn = h3[h3.strategy.isin(["arq_buffer", "batch1h", "design", "design_bounded"])].known_ever
    M("onsetBufKnownMin", pct(kn.min()), "buffering strategies known ever, min over trace x radio")
    un = h3[h3.strategy == "unconf"].known_ever
    M("onsetUnconfKnownMax", pct(un.max()), "unconf known ever, max over trace x radio")


# ============================================================ §III energy-model parameters (from the code)
def energy_params():
    sys.path.insert(0, "src")
    from energy import loss_handling as LH, model as EM, params as EP
    nb = EM.radio("NB-IoT N211 RAI")
    M("eNbUnconf", num(nb["e_report"], 2), "params.NBIOT N211 rai200 (J, module)")
    M("eNbConf", num(nb["e_report_ack"], 2), "params.NBIOT N211 rai400 (J, module)")
    M("eNbSearch", num(LH.P_RX_N211 * LH.T_SEARCH_DEFAULT, 2), "P_RX_N211 x 10 s (J, module)")
    M("pRxNb", num(LH.P_RX_N211, 3), "loss_handling.P_RX_N211 (W)")
    for sf in (7, 12):
        u, a = EM.lora_report_energy(sf, 20), EM.lora_report_energy(sf, 20, confirmed=True)
        key = {7: "Seven", 12: "Twelve"}[sf]
        M(f"eSf{key}Unconf", num(u, 3), f"model.lora_report_energy SF{sf} 20 B unconfirmed (J, radio)")
        M(f"eSf{key}Conf", num(a, 3), f"model.lora_report_energy SF{sf} 20 B confirmed success (J, radio)")
        if sf == 7:
            assert a < u, "SF7: a confirmed success (RX1 ACK) must be cheaper than an unconfirmed report"
        else:
            assert a > u, "SF12: a confirmed success (RX2 ACK) must be dearer"
    for name, key in (("NB-IoT N211 RAI", "Nb"), ("LoRaWAN SF7", "SfSeven"), ("LoRaWAN SF12", "SfTwelve")):
        M(f"rpf{key}", num(LH.Radio(name).readings_per_frame()), f"Radio({name}).readings_per_frame()")
    M("batteryKJ", num(EP.BATTERIES["6600 mAh Li-ion (Weija node, paper 22)"] / 1e3, 1), "params.BATTERIES 6600 mAh x 3.7 V (kJ)")
    M("hostOnMW", num(EP.P_HOST_ON * 1e3, 0), "params.P_HOST_ON (mW)")


def records_extra():
    w = pd.read_csv("results/scoping/weija_outages.csv")
    c = w[w.file == "conductivity_cleaned_records.csv"].iloc[0]
    M("weijaCondMaxDays", num(c.max_outage_d, 1), "weija_outages.csv conductivity max_outage_d")
    M("weijaCondStepMin", num(c.step_min, 1), "weija_outages.csv conductivity step_min")
    assert c.max_outage_d < w.max_outage_d.max()


def outages_extra():
    ci = pd.read_csv("results/scoping/outage_ci.csv")
    sp = ci[(ci.record == "InWaterSense node 1") & (ci.L_h == "spearman")].iloc[0]
    assert max(sp.p_out_next_up, sp.p_out_next_out) < 1e-3
    M("inwsRhoP", "$p<0.001$", "outage_ci.csv InWaterSense spearman, both p < 0.001 (asserted)")
    spw = ci[(ci.record == "Weija conductivity") & (ci.L_h == "spearman")].iloc[0]
    M("weijaRhoNextUp", signed(spw.rho_out_next_up), "outage_ci.csv Weija spearman outage vs next up-run")
    w6 = ci[(ci.record == "Weija conductivity") & (ci.L_h == "6")].iloc[0]
    M("weijaCondSixLost", pct(w6.share_obs), "outage_ci.csv Weija L=6 share_obs")
    om = pd.read_csv("results/scoping/outage_models.csv")
    g = om[(om.what == "outage") & (om.model == "geom")].set_index("record")
    gi = g.loc["InWaterSense node 1"]
    assert gi.share24h_model < 1e-5
    M("geomDayInws", r"less than 0.001\%", "outage_models.csv geom share24h_model InWaterSense (asserted < 1e-5)")
    M("geomSixInws", pct(gi.share6h_model), "outage_models.csv geom share6h_model InWaterSense")
    M("geomDayWeija", pct(g.loc["Weija conductivity"].share24h_model), "outage_models.csv geom share24h_model Weija")
    runs = pd.read_csv("results/scoping/uva_loss_runs.csv").len.to_numpy(float)   # 5-min slots
    M("uvaSixLost", pct(runs[runs >= 72].sum() / runs.sum()), "uva_loss_runs.csv share of lost frames in runs >= 6 h")
    M("uvaDayLost", pct(runs[runs >= 288].sum() / runs.sum()), "uva_loss_runs.csv share of lost frames in runs >= 24 h")
    q = 1 - 1 / runs.mean()
    k = np.arange(1, int(runs.sum()) + 1, dtype=float)
    pk = k * (1 - q) * q ** (k - 1)
    assert pk[k >= 72].sum() / pk.sum() < 1e-5


def lorawan_extra():
    lg = open("results/scoping/loed_full.log", encoding="utf-8").read()
    m = re.search(r"well-heard devices: pooled radio loss ([\d.]+); median per device [\d.]+; P\(loss \| previous loss\) ([\d.]+)", lg)
    M("loedCondRatio", num(float(m.group(2)) / float(m.group(1)), 1), "loed_full.log P(loss|loss) / pooled radio loss")
    sens = pd.read_csv("results/scoping/uva_loss_sensors.csv")
    assert sens.gateway.sum() == 0, "UVA: text says no frame was a gateway loss"
    om = pd.read_csv("results/scoping/outage_models.csv")
    w = om[(om.record == "Weija conductivity") & (om.what == "outage")].set_index("model").aic
    assert w.idxmin() == "zeta" and 0 < w["dlnorm"] - w["zeta"] < 2
    M("aicWeijaLnGap", num(w["dlnorm"] - w["zeta"], 1), "outage_models.csv Weija AIC(lognormal) - AIC(power law)")


def handling_extra():
    d = pd.read_csv("results/scoping/loss_handling.csv")
    d["label"] = d.strategy + d.probe_cap_h.map(lambda h: "" if h == 0 else f"/bo{int(h)}")
    out = {}
    for sf in (7, 12):
        r = []
        for (tr, p_), g in d[d.radio == f"LoRaWAN SF{sf}"].groupby(["trace", "p_radio"]):
            u = g[g.label == "unconf"].iloc[0].energy_j_per_day
            b = g[g.label == "arq_buffer/bo6"].iloc[0].energy_j_per_day
            r.append(b / u - 1)
        out[sf] = r
        key = {7: "Seven", 12: "Twelve"}[sf]
        M(f"buf{key}Min", pp(min(r)), f"LoRaWAN SF{sf} arq_buffer vs unconf energy change, min over records x p (percent)")
        M(f"buf{key}Max", pp(max(r)), f"same SF{sf}, max (percent)")
    assert min(out[12]) > 0, "SF12: buffering must be dearer than unconfirmed in every configuration"
    assert min(out[7]) < 0, "SF7: buffering cheaper in at least one configuration"
    nb = d[d.radio.str.startswith("NB")]
    ts = sorted({float(re.search(r"search ([\d.]+) s", r).group(1)) for r in nb.radio.unique()})
    M("nbSearchTimes", ", ".join(f"{t:g}" for t in ts), "loss_handling.csv NB-IoT radio names (search time, s)")
    # text: the back-off saving grows with the outage share (InWaterSense > Weija) and with the search time
    x = nb.pivot_table(index=["trace", "p_radio", "radio"], columns="label", values="energy_j_per_day")
    r = (x["unconf"] / x["unconf_backoff/bo6"]).reset_index(name="r")
    r["ts"] = r.radio.str.extract(r"search ([\d.]+) s").astype(float)
    for (tr, p_), g in r.groupby(["trace", "p_radio"]):
        assert g.sort_values("ts").r.is_monotonic_increasing
    for (p_, ts), g in r.groupby(["p_radio", "ts"]):
        g = g.set_index("trace").r
        assert g["InWaterSense"] > g["Weija"]
    w = d[(d.trace == "InWaterSense") & (d.radio == "LoRaWAN SF7") & (d.p_radio == 0)].set_index("label")
    M("inwSevenBufE", num(w.loc["arq_buffer/bo6"].energy_j_per_day, 1), "InWaterSense SF7 arq_buffer J/day")
    M("inwSevenBufLife", num(w.loc["arq_buffer/bo6"].lifetime_y, 2), "InWaterSense SF7 arq_buffer lifetime (y)")
    M("inwSevenArqThreeE", num(w.loc["arq3"].energy_j_per_day, 1), "InWaterSense SF7 arq3 J/day")


def chains_extra():
    d = pd.concat((pd.read_csv(f"results/revision/chains/chain_{c}.csv", dtype={"target": str, "neighbour": str}) for c in CHAINS),
                  ignore_index=True)
    d["best_own"] = d[["med_persist", "med_diel"]].min(axis=1)
    d["best_nb"] = d[["med_nb_delta", "med_diel_nb"]].min(axis=1)
    for p_, key, dd in (("DO", "Do", 2), ("pH", "Ph", 3)):
        g = d[(d.param == p_) & (d.H_h == 24)]
        M(f"chainNaiveWin{key}", pct((g.best_nb < g.med_persist).mean(), 0), f"chains {p_} 24 h: share of pairs where a neighbour method beats persistence")
        M(f"chainPersist{key}", num(g.med_persist.median(), dd), f"chains {p_} 24 h: median over pairs of persistence error")
        M(f"chainDiel{key}", num(g.med_diel.median(), dd), f"chains {p_} 24 h: median over pairs of own-diel error")
        M(f"chainBestNb{key}", num(g.best_nb.median(), dd), f"chains {p_} 24 h: median over pairs of best neighbour error")
        assert g.med_diel.median() < g.best_nb.median() < g.med_persist.median()
        assert (g.best_nb < g.med_persist).mean() > (g.best_nb < g.best_own).mean()
    M("chainGaps", ", ".join(str(h) for h in sorted(d.H_h.unique())), "chain files H_h values (h)")


def design_checks():
    h4 = pd.read_csv(f"{DD}/summary_H4_picture.csv")
    f = h4[~h4.H4_pass]
    want = set()
    for tr in ("none", "UVA", "Weija"):
        for ra in h4.radio.unique():
            want |= {(tr, ra, "DO"), (tr, ra, "pH")}
    want.add(("InWaterSense", RADIO_12, "DO"))
    assert set(zip(f.trace, f.radio, f.param)) == want, "H4 failure set differs from the text"
    x = f[(f.trace == "InWaterSense")].iloc[0]
    M("hFourInwsTwelve", pp(x.design_minus_arq_pp / 100, 2), "summary_H4 InWaterSense SF12 DO design - arq (pp)")
    # under the water-quality outage records, unconf shows a better picture than arq_buffer (back-off waits)
    for tr in ("InWaterSense", "Weija"):
        g = h4[(h4.trace == tr)]
        assert (g.within_unconf > g.within_arq_buffer).all(), tr
    g = h4[(h4.trace == "InWaterSense") & (h4.radio == RADIO_7) & (h4.param == "DO")].iloc[0]
    M("picInwsDoUnconf", pct(g.within_unconf), "summary_H4 InWaterSense SF7 DO unconf")
    M("picInwsDoArq", pct(g.within_arq_buffer), "summary_H4 InWaterSense SF7 DO arq_buffer")
    # H8 before the D4 fix (archived)
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = sorted(elig[elig.status == "ok"].site)
    pre = pd.concat((pd.read_csv(f"{DD}/sensitivity/pre_D4/{s_}_picture.csv", dtype={"site": str}) for s_ in ok), ignore_index=True)
    nf = pre[(pre.trace == "none") & (pre.strategy == "design_bounded_nf")]
    bad = nf[nf.within_tol < 1 - 1e-12]
    assert bad.site.nunique() == 1 and set(bad.radio) == {RADIO_12}
    M("hEightPreSite", bad.site.iloc[0], "pre_D4: the only site where newest-first fell short")
    M("hEightPreMin", pct(nf.within_tol.min(), 3), "pre_D4: min within-tolerance share of newest-first, no outage")
    post = pd.concat((pd.read_csv(f"{DD}/sensitivity/{s_}_picture.csv", dtype={"site": str}) for s_ in ok), ignore_index=True)
    assert (post[(post.trace == "none") & (post.strategy == "design_bounded_nf")].within_tol >= 1 - 1e-12).all()
    st = elig.set_index("site")
    assert st.loc[bad.site.iloc[0], "step_min"] == 5.0


def design_checks2():
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = elig[elig.status == "ok"]
    hourly = ok[ok.step_min == 60].site.tolist()
    assert len(hourly) == 1
    en = pd.read_csv(f"{DD}/{hourly[0]}_energy.csv", dtype={"site": str})
    arq = en[(en.setting == "clean") & (en.strategy == "arq_buffer")].set_index(["trace", "radio"]).energy_j_per_day
    bnd = en[(en.setting != "clean") & (en.strategy == "design_bounded")].groupby(["trace", "radio"]).energy_j_per_day.mean()
    dearer = (bnd / arq - 1).max()          # bounded dearer than per-reading ARQ by at most this
    cheaper = (arq / bnd - 1).max()         # ... and cheaper by at most this
    assert 0 < dearer < 0.001 and 0.01 < cheaper < 0.06
    M("hourlySite", hourly[0], "the only 60-min site")
    M("hourlyBoundedDearerMax", pct(dearer, 2), "hourly site: max over links x radios of bounded/arq - 1")
    M("hourlyBoundedCheaperMax", pct(cheaper, 0), "hourly site: max over links x radios of arq/bounded - 1")
    # strategies that ignore alarms send the same frames whatever the readings: only design rows have event settings
    full = pd.concat((pd.read_csv(f"{DD}/{s_}_energy.csv", dtype={"site": str}) for s_ in ok.site), ignore_index=True)
    assert set(full[full.setting != "clean"].strategy) == {"design", "design_bounded"}
    h1 = pd.read_csv(f"{DD}/summary_H1_latency_up.csv")
    i = h1[h1.trace == "InWaterSense"]
    assert (i.lat_design_h < i.lat_arq_buffer_h).all(), "InWaterSense: design faster than arq_buffer on every radio"
    h3 = pd.read_csv(f"{DD}/summary_H3_outage_onset.csv")
    lat = h3[h3.strategy.isin(["arq_buffer", "batch1h", "design", "design_bounded"])].latency_median_h
    M("outBufLatMin", num(lat.min(), 0), "H3 median latency, min over buffering strategies x link x radio (h)")
    M("outBufLatMax", num(lat.max(), 0), "H3 median latency, max over buffering strategies x link x radio (h)")


def standalone_extra():
    """Definitions that Paper 2 now states itself (it is a standalone paper)."""
    # Weija: unflagged interpolation shows as values with more decimals than the logger records
    w = pd.read_csv("data/weija_raw/conductivity_cleaned_records.csv", dtype={"Value": str})
    w = w[w.Was_Imputed.astype(str) != "True"]
    dec = w.Value.str.split(".").str[1].fillna("").str.len()
    assert dec.mode().iloc[0] == 3
    M("weijaManyDecimals", pct((dec > 3).mean(), 1), "Weija conductivity, non-imputed: share of values with > 3 decimals")
    M("weijaMaxDecimals", num(int(dec.max())), "Weija conductivity, non-imputed: most decimals in a value")
    # energy floor (sleep + sensing), from the copied energy parameters
    sys.path.insert(0, "src")
    from energy import model as EM, params as EP
    M("hostSleepMW", num(EP.P_HOST_SLEEP * 1e3, 2), "params.P_HOST_SLEEP (mW)")
    M("tSenseS", num(EP.T_SENSE["typical"], 0), "params.T_SENSE typical (s awake per sample)")
    M("nbPsmUW", num(EM.radio("NB-IoT N211 RAI")["p_sleep"] * 1e6, 2), "N211 PSM sleep power (uW)")
    M("loraSleepUW", num(EM.radio("LoRaWAN SF7")["p_sleep"] * 1e6, 0), "LoRa radio sleep power (uW)")
    M("vNode", num(EP.V_NODE, 1), "params.V_NODE (V)")


def write():
    OUT.mkdir(exist_ok=True); TAB.mkdir(exist_ok=True)
    lines = ["% Generated by src/paper/paper_numbers.py -- do not edit by hand."]
    for name, value, source in MACROS:
        lines.append(f"\\newcommand{{\\{name}}}{{{value}}}  % {source}")
    (OUT / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(MACROS)} macros -> draft/numbers.tex")


if __name__ == "__main__":
    outages_water()
    outages_lorawan()
    outage_models_table()
    strategies()
    chains()
    # design(), sensitivity(), design_extra(), design_checks(), design_checks2(): v0.1 development runs, replaced in
    # the revision by revision_numbers.design_years (2023 rerun with D4/D5 fixed, and the held-out 2024 runs)
    energy_params()
    records_extra()
    outages_extra()
    lorawan_extra()
    handling_extra()
    chains_extra()
    standalone_extra()
    sys.path.insert(0, "src/paper")
    import revision_numbers as RN
    RN.all_revision(M, pct, num, times)
    RN.design_years(M, pct, num, times, pp)
    RN.history_v01(M, pct, num)
    RN.netsim_table()
    RN.ack_variant(M, pct, num, times, pp)
    write()
