"""Numbers for the revision (review of 2026-10-16), generated from results/revision/ and results/confirm/.

Called by paper_numbers.py, which owns the macro list and the formatting helpers; every macro carries its
source, and every comparison the text makes is asserted here.
"""
import json
import re

import numpy as np
import pandas as pd

R = "results/revision"


def gap_cause(M, pct, num):
    s = json.load(open(f"{R}/gap_cause_summary.json"))
    w, i = s["weija"], s["inws"]
    rec = pd.read_csv(f"{R}/gap_cause_weija_records.csv").set_index("record")
    node = rec.loc["node: any stream, genuine rows (node-silent)"]
    miss = w["EC missing (v0.1 record)"]
    M("weijaEcMissing", num(miss), "gap_cause_summary.json weija")
    M("weijaNodeSilentShare", pct(w["  of which node-silent"] / miss, 0), "gap_cause_summary.json weija")
    M("weijaOtherStreamShare", pct(w["  of which another stream delivered (link up)"] / miss, 0), "gap_cause_summary.json")
    M("weijaLongAliveShare", pct(w["long_gaps_alive_share"], 0), "gap_cause_summary.json: slots of v0.1 gaps >= 6 h with another stream")
    M("weijaNodeLoss", pct(node.loss), "gap_cause_weija_records.csv node record loss")
    M("weijaNodeGaps", num(int(node.gaps)), "gap_cause_weija_records.csv node record gaps")
    M("weijaNodeDayLost", pct(node.S_1d, 0), "gap_cause_weija_records.csv node record S(1 d)")
    M("inwsWindowShare", pct(i["window_share_of_all_lost"], 0), "gap_cause_summary.json inws: lost slots inside node 2's window")
    M("inwsNodeTwoSilent", pct(i["node2_silent_when_n1_missing"], 0), "gap_cause_summary.json inws")
    M("inwsSharedLong", pct(i["pi_shared gaps >= 6 h"], 0), "gap_cause_summary.json inws pi, gaps >= 6 h")
    M("inwsSpecificLong", pct(1 - i["pi_shared gaps >= 6 h"], 0), "1 - pi, gaps >= 6 h")
    M("inwsSpecificShort", pct(1 - i["pi_shared gaps < 6 h"], 0), "1 - pi, gaps < 6 h")
    assert i["pi_shared gaps >= 6 h"] > 0.5 > i["pi_shared gaps < 6 h"], "long gaps mostly shared, short mostly node-specific"
    assert w["long_gaps_alive_share"] < 0.1


def node_off(M, pct, num):
    d = pd.read_csv(f"{R}/loss_B.csv")
    g = d.groupby(["trace", "radio", "f", "strategy"]).mean(numeric_only=True)
    for tr, key in (("InWaterSense", "Inws"), ("Weija (node record)", "Weija")):
        x = g.loc[(tr, "LoRaWAN SF7", 0.5, "arq_buffer")]
        M(f"offExpected{key}", pct(x.delivered_of_expected, 0), f"loss_B.csv {tr} SF7 f=0.5 buffer: delivered/expected")
        assert (d[(d.trace == tr) & d.strategy.isin(["arq_buffer", "batch1h"])].delivered > 0.999).all(), "buffering delivers all generated"
    fair = lambda f: g.loc[("InWaterSense", "LoRaWAN SF7", f, "arq_buffer")].energy_j_per_day / g.loc[("InWaterSense", "LoRaWAN SF7", f, "unconf")].energy_j_per_day
    M("offBufFairZero", num(fair(0.0), 2), "loss_B.csv InWaterSense SF7 buffer/unconf energy, f=0")
    M("offBufFairHalf", num(fair(0.5), 2), "loss_B.csv InWaterSense SF7 buffer/unconf energy, f=0.5")
    M("offRealisedWeija", num(g.loc[("Weija (node record)", "LoRaWAN SF7", 0.1, "unconf")].f_realised, 2),
      "loss_B.csv: realised node-off share for nominal f = 0.1 (Weija has few long gaps)")


def arq_timing(M, pct, num, times):
    d = pd.read_csv(f"{R}/loss_A.csv")
    d = d[d.p_radio == 0]
    g = d.groupby(["trace", "radio", "model", "strategy"])[["delivered", "energy_j_per_day"]].mean().reset_index()
    u = g[g.strategy == "unconf"].set_index(["trace", "radio", "model"])
    g = g.join(u[["delivered", "energy_j_per_day"]], on=["trace", "radio", "model"], rsuffix="_u")
    g["gain_pp"] = 100 * (g.delivered - g.delivered_u); g["e_ratio"] = g.energy_j_per_day / g.energy_j_per_day_u
    arq = g[g.strategy.str.startswith("arq") & (g.strategy != "arq_buffer")]
    # LoRaWAN only: NB-IoT ARQ gives up when the modem reports no network, so it recovers nothing in any timing
    # model by construction (asserted); and NB-IoT's fair baseline is unconfirmed + back-off, not in this run
    assert (arq[arq.radio == "NB-IoT"].gain_pp.abs() < 1e-9).all()
    inws = arq[(arq.trace == "InWaterSense") & (arq.radio != "NB-IoT")]
    for model, key in (("full", "Full"), ("uniform", "Uniform"), ("burst", "Burst")):
        x = inws[inws.model == model].gain_pp
        M(f"arqGain{key}Min", num(x.min(), 1), f"loss_A.csv InWaterSense LoRaWAN ARQ gain (pp), {model}, p_radio 0, SF7/SF12, all variants")
        M(f"arqGain{key}Max", num(x.max(), 1), f"loss_A.csv same, max")
    lost = 100 * (1 - g[(g.trace == "InWaterSense") & (g.strategy == "unconf")].delivered.iloc[0])
    M("arqLostPp", num(lost, 0), "loss_A.csv InWaterSense unconfirmed: lost share (pp)")
    assert inws.gain_pp.max() < 0.2 * lost, "ARQ recovers under a fifth of the lost readings in every model"
    w = arq[arq.trace.str.startswith("Weija")].gain_pp.max()
    M("arqGainWeijaMax", num(w, 1), "loss_A.csv Weija records: largest ARQ gain (pp) over models")
    assert w < 1.0
    buf = g[(g.strategy == "arq_buffer")]
    assert (buf.delivered > 0.999).all()
    bi = buf[(buf.trace == "InWaterSense") & (buf.radio != "NB-IoT")].e_ratio
    M("arqBufRatioMin", num(bi.min(), 2), "loss_A.csv InWaterSense LoRaWAN buffer/unconf energy over models")
    M("arqBufRatioMax", num(bi.max(), 2), "same, max")
    lo = inws[inws.radio != "NB-IoT"].e_ratio
    M("arqRatioMin", times(lo.min(), 1), "loss_A.csv InWaterSense LoRaWAN ARQ/unconf energy over models, variants")
    M("arqRatioMax", times(lo.max(), 1), "same, max")
    f7 = inws[(inws.model == "full") & (inws.radio == "LoRaWAN SF7")].set_index("strategy").e_ratio
    M("arqVOneZeroTwo", times(f7["arq8_v102"], 1), "loss_A.csv InWaterSense SF7 full: 8 tx, LoRaWAN 1.0.2 DR stepping")
    M("arqVOneZeroFour", times(f7["arq8_v104"], 1), "loss_A.csv InWaterSense SF7 full: NbTrans 8, LoRaWAN 1.0.4")
    assert f7["arq8_v104"] < f7["arq8_v102"]


def storage(M, pct, num):
    d = pd.read_csv(f"{R}/loss_C.csv")
    i = d[(d.trace == "InWaterSense") & (d.drain_limit == "none")]
    for kb in (2, 8):
        x = i[i.storage == f"RAM {kb} KB"]
        M(f"ramLoss{'Two' if kb == 2 else 'Eight'}", pct(x.lost.max(), 0), f"loss_C.csv InWaterSense RAM {kb} KB: readings lost (max over radios/strategies)")
    M("maxBufferKB", num(i[i.storage == "unlimited, no energy"].max_buffer_kb.max(), 0), "loss_C.csv InWaterSense largest buffer (KB)")
    assert (i[i.storage == "RAM 64 KB"].lost == 0).all()
    fl = d[d.storage.str.startswith("flash")]
    M("flashJDayMax", num(fl.storage_j_per_day.max(), 2), "loss_C.csv: largest flash energy (J/day), worst case")
    M("radioJDayMin", num(d[d.storage == "unlimited, no energy"].energy_j_per_day.min(), 0), "loss_C.csv: smallest radio energy (J/day)")
    lim = d[d.drain_limit != "none"]
    assert (lim.delivered > 0.999).all(), "drain-limited: everything delivered"
    s12 = lim[(lim.trace == "InWaterSense") & (lim.radio == "LoRaWAN SF12") & (lim.strategy == "arq_buffer")].iloc[0]
    M("drainTwelveMedH", num(s12.clear_h_median, 1), "loss_C.csv InWaterSense SF12 buffer, duty-cycle drain: median clearance (h)")
    M("drainTwelveMaxD", num(s12.clear_h_max / 24, 0), "same, longest clearance (days)")
    M("drainTwelveLiveP", num(s12.live_delay_h_p95 / 24, 0), "same, p95 delay of live readings during backlogs (days)")
    s7 = lim[(lim.trace == "InWaterSense") & (lim.radio == "LoRaWAN SF7") & lim.drain_limit.str.startswith("duty")]
    M("drainSevenMaxH", num(s7.clear_h_max.max(), 0), "loss_C.csv InWaterSense SF7 duty-cycle drain: longest clearance (h)")


def k_sweep(M, pct, num, times):
    d = pd.read_csv(f"{R}/sweep_k_batch.csv")
    a = d[(d.trace == "InWaterSense") & (d.strategy == "arq_buffer")]
    s7 = a[a.radio == "LoRaWAN SF7"].set_index("K_h"); nb = a[a.radio == "NB-IoT"].set_index("K_h")
    M("kEverySlotSeven", times(s7.energy_j_per_day[0] / s7.energy_j_per_day[6], 1), "sweep_k_batch.csv InWaterSense SF7: probe every slot / K=6 h")
    M("kEverySlotNb", times(nb.energy_j_per_day[0] / nb.energy_j_per_day[6], 1), "sweep_k_batch.csv InWaterSense NB-IoT: same")
    M("kSixToDaySave", pct(1 - s7.energy_j_per_day[24] / s7.energy_j_per_day[6], 0), "sweep: SF7 energy saving K 6 -> 24 h")
    M("kPninetySix", num(s7.recovery_h_p90[6], 0), "sweep: SF7 p90 recovery latency at K = 6 h (h)")
    M("kPninetyDay", num(s7.recovery_h_p90[24], 0), "sweep: SF7 p90 recovery latency at K = 24 h (h)")
    assert s7.recovery_h_p90[24] > 2.5 * s7.recovery_h_p90[6] and s7.energy_j_per_day[24] > 0.8 * s7.energy_j_per_day[6]


def lorawan_checks(M, pct, num):
    c = pd.read_csv(f"{R}/lorawan_uva_counters.csv")
    M("uvaMissThouVsFive", pct(1 - c.missing_thr_1000.sum() / c.missing_thr_5000.sum(), 0), "lorawan_uva_counters.csv: missing frames, threshold 1,000 vs 5,000")
    M("uvaDecreases", num(int(c.decreases.sum())), "lorawan_uva_counters.csv: frame-counter decreases")
    cad = pd.read_csv(f"{R}/lorawan_uva_cadence.csv")
    assert ((cad.cadence_s_median >= 240) & (cad.cadence_s_median <= 360)).all()
    b = pd.read_csv(f"{R}/lorawan_uva_bins.csv")
    M("uvaBinOutMax", num(int(b.system_outages.max())), "lorawan_uva_bins.csv: system outages at 5-min bins")
    M("uvaBinOutMin", num(int(b.system_outages.min())), "lorawan_uva_bins.csv: system outages at 30-min bins")
    M("uvaBinDayMin", pct(b.downtime_share_ge_1d.min(), 0), "lorawan_uva_bins.csv: down-time share in >= 1 d outages, min over bins")
    M("uvaBinDayMax", pct(b.downtime_share_ge_1d.max(), 0), "same, max")
    M("uvaBinSysMin", pct(b.missing_system_share.min(), 1), "lorawan_uva_bins.csv: system share of missing frames, min")
    M("uvaBinSysMax", pct(b.missing_system_share.max(), 1), "same, max")
    lc = pd.read_csv(f"{R}/lorawan_loed_counters.csv"); dv = pd.read_csv("results/scoping/loed_full_devices.csv")
    x = lc[lc.dev.isin(dv[dv.radio_loss < 0.2].dev)]
    loss = lambda t: x[f"missing_thr_{t}"].sum() / (x[f"missing_thr_{t}"].sum() + x.frames.sum())
    M("loedLossHundred", pct(loss(100)), "lorawan_loed_counters.csv well-heard devices, reset threshold 100")
    M("loedLossThousand", pct(loss(1000)), "same, threshold 1,000 (the analysis)")
    M("loedResetDevices", num(int((x.decreases > 0).sum())), "well-heard devices with a frame-counter reset")
    M("loedWellHeardN", num(len(x)), "well-heard devices")


def tolerance_events(M, pct, num):
    t = pd.read_csv(f"{R}/tolerance_summary.csv").set_index("param")
    fmt = {"T": 2, "DO": 1, "EC": 1, "pH": 2}
    for p in ("T", "DO", "EC", "pH"):
        k = {"T": "T", "DO": "DO", "EC": "EC", "pH": "Ph"}[p]
        M(f"usgsExc{k}", num(t.usgs_exc_med[p], fmt[p]), f"tolerance_summary.csv {p}: USGS excellent (median over sites)")
        M(f"tolTwo{k}", num(t.tol_L2_med[p], fmt[p]), f"tolerance_summary.csv {p}: L2 (median over sites)")
        M(f"dayRange{k}", num(t.daily_range_med[p], fmt[p]), f"tolerance_summary.csv {p}: median daily range")
        M(f"ampFive{k}", num(t.amp5_med[p], fmt[p]), f"tolerance_summary.csv {p}: median 5 sigma")
        M(f"ampEight{k}", num(t.amp8_med[p], fmt[p]), f"tolerance_summary.csv {p}: median 8 sigma")
        M(f"realFive{k}", pct(t.sites_with_real_ge5[p], 0), f"tolerance_summary.csv {p}: sites with a real 3-h change >= 5 sigma")
        M(f"realEight{k}", pct(t.sites_with_real_ge8[p], 0), f"tolerance_summary.csv {p}: sites with a real 3-h change >= 8 sigma")
        assert t.tol_L2_med[p] <= t.usgs_exc_med[p] + 1e-9, "L2 is at or inside USGS excellent"


def netsim(M, pct, num, times):
    d = pd.read_csv(f"{R}/netsim.csv")
    g = d.groupby(["sf", "outage_h", "n_nodes", "jitter_s"]).mean(numeric_only=True)
    z = g.xs(0.0, level="jitter_s")
    M("netZeroJitterN", num(int(min(n for (sf, o, n), r in z.iterrows() if sf == 7 and r.cleared_share < 0.05))),
      "netsim.csv: smallest cell (SF7) in which, without jitter, under 5% of nodes recover within 72 h")
    j = g.xs(3600.0, level="jitter_s")
    s7 = j.xs(7, level="sf")
    assert (s7.cleared_share > 0.999).all(), "SF7 with jitter: every node recovers"
    M("netSevenMedMin", num(s7.clear_median_h.min(), 0), "netsim SF7, 1-h jitter: median node clearance, min (h)")
    M("netSevenMedMax", num(s7.clear_median_h.max(), 0), "same, max")
    M("netSevenAllMax", num(s7.clear_all_h.max(), 0), "netsim SF7: last node clears (h), max over settings")
    big = s7.xs(500, level="n_nodes")
    M("netSevenEnergyMax", times(big.energy_vs_alone.max(), 1), "netsim SF7, 500 nodes: energy per node vs alone, max")
    s12 = j.xs(12, level="sf")
    M("netTwelveNoAck", pct(s12.noack_share.max(), 0), "netsim SF12: received but unacknowledged, max")
    M("netTwelveRxOne", pct(s12.rx1_duty.max(), 1), "netsim SF12: gateway RX1 duty use, max (limit 1%)")
    day = s12.xs(24, level="outage_h")             # index: n_nodes
    M("netTwelveCleared", pct(day.loc[100].cleared_share, 0), "netsim SF12, 1-d outage, 100 nodes: share recovered in 72 h")
    assert day.loc[50].cleared_share > 0.99 and day.loc[100].cleared_share < 0.99


def netsim_table():
    """draft/tables/tab_netsim.tex: 1-day shared outage, 1-h probe jitter, mean over 3 seeds."""
    d = pd.read_csv(f"{R}/netsim.csv")
    d = d[(d.outage_h == 24) & (d.jitter_s == 3600)]
    g = d.groupby(["sf", "n_nodes"]).mean(numeric_only=True)
    rows = []
    for sf in (7, 12):
        for n in (10, 50, 100, 250, 500):
            r = g.loc[(sf, n)]
            fin = lambda v: f"{v:.0f}" if np.isfinite(v) else "$>$72"
            rows.append(f"SF{sf} & {n} & {100 * r.cleared_share:.0f}\\% & {fin(r.clear_median_h)} & {fin(r.clear_all_h)} & "
                        f"{100 * r.pdr:.0f}\\% & {100 * r.collided_share:.0f}\\% & {100 * r.noack_share:.0f}\\% & "
                        f"{r.energy_vs_alone:.1f}$\\times$ \\\\")
        if sf == 7:
            rows.append("\\addlinespace")
    open("draft/tables/tab_netsim.tex", "w", encoding="utf-8").write("\n".join(rows) + "\n")


def reconstruct(M, pct, num):
    b = pd.read_csv(f"{R}/reconstruct_bootstrap.csv")
    a = b[(b.param == "all") & (b.H_h == 24)].iloc[0]
    M("recDayAll", pct(a.value, 0), "reconstruct_bootstrap.csv: best-of-all within tolerance, 24 h, pooled")
    M("recDayAllLo", pct(a.ci_lo, 0), "chain-blocked 95% CI low"); M("recDayAllHi", pct(a.ci_hi, 0), "CI high")
    for p, k in (("T", "T"), ("pH", "Ph"), ("DO", "DO"), ("EC", "EC")):
        r = b[(b.param == p) & (b.H_h == 24) & (b.stat == "ok_best_all")].iloc[0]
        M(f"recDay{k}", pct(r.value, 0), f"reconstruct_bootstrap.csv {p} 24 h best-of-all")
    sp = pd.read_csv(f"{R}/reconstruct_pairs_spatial.csv")
    do = sp[sp.param == "DO"]
    M("lagPosDown", pct((do[do.neighbour_is == "downstream"].lag_h > 0).mean(), 0), "pairs_spatial DO: downstream neighbours with lag > 0")
    M("lagPosUp", pct((do[do.neighbour_is == "upstream"].lag_h > 0).mean(), 0), "pairs_spatial DO: upstream neighbours with lag > 0")
    M("pairKmMin", num(sp.distance_km.min(), 1), "pairs_spatial distance min (km)")
    M("pairKmMax", num(sp.distance_km.max(), 0), "max (km)")
    M("pairKmMed", num(sp.distance_km.median(), 0), "median (km)")


def independent_energy(M, pct, num, times):
    """Ugwuanyi et al. 2021, Table 5 (FiPy board): 100 uAh per 44-B LoRaWAN SF7 uplink, 1.8 mAh per 44-B NB-IoT
    uplink, at 3.3 V; against this model's per-report energy at 44 B, host included."""
    import sys
    sys.path.insert(0, "src")
    from energy.loss_handling import Radio
    lora = Radio("LoRaWAN SF7").attempt(False, True, True, 44)
    nb = Radio("NB-IoT N211 RAI").attempt(False, True, True, 44)
    r_l, r_n = 100e-6 * 3600 * 3.3 / lora, 1.8e-3 * 3600 * 3.3 / nb
    M("ugwLoraRatio", times(r_l, 0), f"Ugwuanyi 2021 Tab. 5 LoRaWAN 1.19 J vs model {lora:.3f} J (44 B, SF7, host incl.)")
    M("ugwNbRatio", times(r_n, 0), f"Ugwuanyi 2021 Tab. 5 NB-IoT 21.4 J vs model {nb:.3f} J (44 B, RAI, host incl.)")
    assert r_l > 2 and r_n > 2


C = "results/confirm"
R7, R12 = "LoRaWAN SF7", "LoRaWAN SF12"
LINKS = [("none", "No outage"), ("UVA", "UVA"), ("Weija", "Weija"), ("InWaterSense", "InWaterSense")]
YEARS = {"Dev": ("an2023", "2023_dev", "results/scoping/design_site_eligibility.csv"),
         "Conf": ("an2024", "2024", "results/confirm/eligibility_2024.csv")}


def _ci(s):
    return tuple(float(x) for x in re.findall(r"[-+]?\d*\.\d+(?:e[-+]?\d+)?|[-+]?\d+(?:e[-+]?\d+)?", s.replace("np.float64", "")))


def design_years(M, pct, num, times, pp):
    """Sec. VII: development (2023, D5-corrected rerun) and confirmatory (2024) results, same frozen analysis."""
    import glob
    for y, (an, run, elig_f) in YEARS.items():
        v = json.load(open(f"{C}/{an}_verdicts.json"))
        vd = v["verdicts"]
        for k in ("CH1", "CH2", "CH5", "CH6", "CH7", "CH9_L1", "CH9_L3", "CH10_L1", "CH10_L3"):
            n, d = vd[k].split("/"); assert n == d, f"{y} {k} {vd[k]}"
        assert vd["CH8"] == "pass"
        key = lambda k: k.replace("CH", "ch").replace("_L1", "LOne").replace("_L3", "LThree").replace("10", "Ten") \
            .replace("1", "One").replace("2", "Two").replace("4", "Four").replace("5", "Five").replace("6", "Six") \
            .replace("7", "Seven").replace("9", "Nine")
        for k in ("CH1", "CH2", "CH4", "CH5", "CH6", "CH7", "CH9_L1", "CH9_L3", "CH10_L1", "CH10_L3"):
            M(f"{key(k)}{y}", vd[k], f"{an}_verdicts.json {k}")
        M(f"plausible{y}", pct(v["plausible_event_share"], 1), f"{an}_verdicts.json: injected events within plausible ranges")
        elig = pd.read_csv(elig_f, dtype={"site": str}); ok = sorted(elig[elig.status == "ok"].site)
        assert v["sites"] == len(ok)
        if y == "Conf":
            M("confSites", num(len(ok)), "eligibility_2024.csv status ok")
        else:
            M("designSites", num(len(ok)), "design_site_eligibility.csv status ok")
            M("designCandidates", num(len(elig)), "design_site_eligibility.csv rows")
        # ---- picture: H4 failures, H5 differences
        p = pd.read_csv(f"{C}/{an}_picture.csv"); L2 = p[p.level == "L2"]
        f = L2[~L2.CH4]
        assert set(f.param) == {"DO"}, f"{y}: CH4 failures not DO only"
        assert set(f.trace) >= {"none", "UVA", "Weija"}
        M(f"hFourFailMin{y}", pp(f.event_minus_arq_pp.min() / 100), f"{an}_picture L2 worst failing event - arq (pp)")
        M(f"hFourFailMax{y}", pp(f.event_minus_arq_pp.max() / 100), f"{an}_picture L2 mildest failing event - arq (pp)")
        M(f"hFiveDiffMin{y}", pp(L2.bounded_minus_arq_pp.min() / 100, 2), f"{an}_picture L2 bounded - arq, min (pp)")
        M(f"hFiveDiffMax{y}", pp(L2.bounded_minus_arq_pp.max() / 100, 2), f"{an}_picture L2 bounded - arq, max (pp)")
        # ---- energy
        e = pd.read_csv(f"{C}/{an}_energy.csv")
        M(f"eventOverBatchMin{y}", times(e.event_over_batch.min()), f"{an}_energy event / batch, min")
        M(f"eventOverBatchMax{y}", times(e.event_over_batch.max()), f"{an}_energy event / batch, max")
        M(f"arqOverEventMin{y}", times(e.arq_over_event.min()), f"{an}_energy arq / event, min")
        M(f"arqOverEventMax{y}", times(e.arq_over_event.max()), f"{an}_energy arq / event, max")
        M(f"boundedOverBatchMin{y}", times(e.bounded_over_batch.min()), f"{an}_energy bounded / batch, min")
        M(f"boundedOverBatchMax{y}", times(e.bounded_over_batch.max()), f"{an}_energy bounded / batch, max")
        M(f"arqOverBoundedMin{y}", times(e.arq_over_bounded.min()), f"{an}_energy arq / bounded, min")
        M(f"arqOverBoundedMax{y}", times(e.arq_over_bounded.max()), f"{an}_energy arq / bounded, max")
        lo = min(_ci(c)[0] for c in e.arq_over_bounded_ci)
        M(f"arqOverBoundedCiLow{y}", times(lo), f"{an}_energy: lowest lower 95% CI bound of arq / bounded over link x radio")
        assert lo > 1.0
        lev = pd.read_csv(f"{C}/{an}_energy_levels.csv")
        for lv, k in (("L1", "One"), ("L2", "Two"), ("L3", "Three")):
            x = lev[lev.level == lv]
            M(f"lev{k}ArqOverMin{y}", times(x.arq_over_bounded.min()), f"{an}_energy_levels {lv} arq / bounded, min")
            M(f"lev{k}ArqOverMax{y}", times(x.arq_over_bounded.max()), f"{an}_energy_levels {lv} arq / bounded, max")
        # ---- latency (link up)
        lat = pd.read_csv(f"{C}/{an}_latency.csv"); la = lat[lat.set == "all"]
        M(f"batchLagMin{y}", num(la.batch_minus_event_h.min(), 2), f"{an}_latency: batch - event (h), min over link x radio")
        M(f"batchLagMax{y}", num(la.batch_minus_event_h.max(), 2), f"{an}_latency: batch - event (h), max")
        assert la.batch_minus_event_h.min() > 0
        iw = la[la.trace == "InWaterSense"]
        assert (iw.lat_event_h <= iw.lat_arq_h + 1e-9).all(), f"{y}: InWaterSense, event-driven never slower (link up)"
        assert (iw[iw.radio == R12].lat_event_h < iw[iw.radio == R12].lat_arq_h).all(), f"{y}: faster at SF12"
        if y == "Dev":
            assert (iw.lat_event_h < iw.lat_arq_h).all(), "2023: faster on every radio"
        # ---- all events known within 1/6/24 h (M11), SF7
        k = pd.read_csv(f"{C}/{an}_known_within.csv"); k = k[k.radio == R7].set_index(["trace", "strategy"])
        for tr, tk in (("none", "None"), ("InWaterSense", "Inws")):
            for s_, sk in (("unconf", "Unconf"), ("arq_buffer", "Arq"), ("batch1h", "Batch"), ("design", "Event"),
                           ("design_bounded_nf", "Bounded")):
                for h, hk in ((1, "One"), (6, "Six"), (24, "Day")):
                    M(f"known{hk}{sk}{tk}{y}", pct(k.loc[(tr, s_), f"known_{h}h"], 0), f"{an}_known_within {tr} SF7 {s_} {h} h")
        # ---- detection, false alarms, alarms per day (from the per-site files)
        if y == "Conf":
            ev = pd.concat((pd.read_csv(f, dtype={"site": str}) for f in sorted(glob.glob(f"{C}/{run}/*_events.csv"))), ignore_index=True)
            ev = ev[ev.site.isin(ok)]
            one = ev[(ev.trace == "none") & (ev.radio == R7) & (ev.strategy == "design")]
            M("designEventsConf", num(len(one)), "2024 injected events (all settings)")
            det = one.groupby(["setting", "site"]).node_detected.mean().groupby("setting").median()
            for st, kk in (("step5", "StepFive"), ("step8", "StepEight"), ("ramp5", "RampFive"), ("ramp8", "RampEight")):
                M(f"detect{kk}", pct(det[st], 0), f"2024: median over sites of the share of {st} events detected")
            M("detectAll", pct(one.node_detected.mean(), 1), "2024: share of injected events detected (pooled)")
            en = pd.concat((pd.read_csv(f, dtype={"site": str}) for f in sorted(glob.glob(f"{C}/{run}/*_energy.csv"))), ignore_index=True)
            en = en[en.site.isin(ok)]
            c = en[(en.setting == "clean")].drop_duplicates("site")
            M("faMedian", num(c.fa_per30d_param.median(), 1), "2024: median over sites of false alarms per parameter per 30 days")
            M("faMean", num(c.fa_per30d_param.mean(), 1), "2024: mean")
            M("alarmsPerDay", num(c.alarms_per_day.median(), 2), "2024: median node alarms per day (clean series)")
            M("alarmsPerDayMean", num(c.alarms_per_day.mean(), 2), "2024: mean")
            # onset in an outage (descriptive H3), SF7 pooled, and the table
            out = ev[~ev.link_up_at_onset & ev.node_detected]
            rows = []
            for tr in ("InWaterSense", "Weija", "UVA"):
                g = out[(out.trace == tr) & (out.radio == R7)]
                n_ = int((g.strategy == "design").sum())
                ke = lambda s_: np.isfinite(g[g.strategy == s_].latency_h).mean()
                md = lambda s_: np.median(g[g.strategy == s_].latency_h[np.isfinite(g[g.strategy == s_].latency_h)])
                rows.append(f"{tr} & {num(n_)} & {pct(ke('unconf'))} & {pct(ke('arq_buffer'))} & {pct(ke('design'))} & "
                            + " & ".join(num(md(s_), 1) for s_ in ("arq_buffer", "batch1h", "design", "design_bounded_nf")) + r" \\")
            open("draft/tables/tab_onset.tex", "w", encoding="utf-8").write("\n".join(rows) + "\n")
            for tr in ("InWaterSense", "Weija"):                 # text: event-driven designs faster than ARQ + buffer
                g = out[(out.trace == tr) & (out.radio == R7)]
                md = {s_: np.median(g[g.strategy == s_].latency_h[np.isfinite(g[g.strategy == s_].latency_h)])
                      for s_ in ("arq_buffer", "design", "design_bounded_nf")}
                assert md["design"] < md["arq_buffer"] and md["design_bounded_nf"] < md["arq_buffer"], tr
            allo = out.groupby(["trace", "radio", "strategy"]).latency_h.apply(lambda v: np.isfinite(v).mean())
            M("onsetUnconfKnownMax", pct(allo.xs("unconf", level="strategy").max()), "2024 onset in outage: unconf known ever, max")
            M("onsetBufKnownMin", pct(allo[allo.index.get_level_values("strategy") != "unconf"].min()), "2024: buffering known ever, min")
            # tables: latency + energy (SF7), picture (SF7), tolerance levels (SF7)
            rows = []
            for tr, name in LINKS:
                a = la[(la.trace == tr) & (la.radio == R7)].iloc[0]; b = e[(e.trace == tr) & (e.radio == R7)].iloc[0]
                rows.append(f"{name} & {num(a.lat_arq_h, 2)} & {num(a.lat_batch_h, 2)} & {num(a.lat_event_h, 2)} & "
                            f"{num(a.lat_bounded_h, 2)} & {num(b.E_arq, 1)} & {num(b.E_batch, 1)} & {num(b.E_event, 1)} & "
                            f"{num(b.E_bounded, 1)} \\\\")
            open("draft/tables/tab_design.tex", "w", encoding="utf-8").write("\n".join(rows) + "\n")
            rows = []
            for tr, name in LINKS:
                for j, pa in enumerate(("DO", "pH", "T", "EC")):
                    a = L2[(L2.trace == tr) & (L2.radio == R7) & (L2.param == pa)].iloc[0]
                    rows.append(f"{name if j == 0 else ''} & {pa} & {pct(a.within_unconf)} & {pct(a.within_arq)} & "
                                f"{pct(a.within_batch)} & {pct(a.within_event)} & {pct(a.within_bounded)} \\\\")
                if tr != "InWaterSense":
                    rows.append(r"\addlinespace")
            open("draft/tables/tab_picture.tex", "w", encoding="utf-8").write("\n".join(rows) + "\n")
            rows = []
            for lv, lab in (("L1", "L1 (tight)"), ("L2", "L2"), ("L3", "L3 (loose)")):
                for tr, name in (("none", "No outage"), ("InWaterSense", "InWaterSense")):
                    a = lev[(lev.level == lv) & (lev.trace == tr) & (lev.radio == R7)].iloc[0]
                    pv = p[(p.level == lv) & (p.trace == tr) & (p.radio == R7)]
                    rows.append(f"{lab if tr == 'none' else ''} & {name} & {num(a.E_arq, 1)} & {num(a.E_bounded, 1)} & "
                                f"{times(a.arq_over_bounded)} & {pct(pv.within_bounded.min())} & {pct(pv.within_arq.min())} \\\\")
                if lv != "L3":
                    rows.append(r"\addlinespace")
            open("draft/tables/tab_sensitivity.tex", "w", encoding="utf-8").write("\n".join(rows) + "\n")
            # unconfirmed shows a better picture than ARQ + buffer under the water-quality records (back-off waits)
            g = L2[L2.trace.isin(["InWaterSense", "Weija"])]
            assert (g.within_unconf > g.within_arq).all()
            x = L2[(L2.trace == "InWaterSense") & (L2.radio == R7) & (L2.param == "DO")].iloc[0]
            M("picInwsDoUnconf", pct(x.within_unconf), "an2024 L2 InWaterSense SF7 DO unconf")
            M("picInwsDoArq", pct(x.within_arq), "an2024 L2 InWaterSense SF7 DO arq_buffer")
            # FIFO vs newest-first energy (L2, clean)
            cl = en[(en.setting == "clean") & (en.level == "L2") & en.strategy.isin(["design_bounded", "design_bounded_nf"])]
            r_ = cl.pivot_table(index=["trace", "radio", "site"], columns="strategy", values="energy_j_per_day")
            rr = r_.design_bounded_nf / r_.design_bounded
            M("nfRatioMin", f"{rr.min():.3f}", "2024 clean L2: newest-first / FIFO energy, min")
            M("nfRatioMax", f"{rr.max():.3f}", "2024 clean L2: newest-first / FIFO energy, max")
    # cross-year: the 2024 sites that were not in the 2023 set, and vice versa
    e23 = pd.read_csv(YEARS["Dev"][2], dtype={"site": str}); e24 = pd.read_csv(YEARS["Conf"][2], dtype={"site": str})
    s23, s24 = set(e23[e23.status == "ok"].site), set(e24[e24.status == "ok"].site)
    M("sitesBothYears", num(len(s23 & s24)), "sites eligible in both years")
    M("sitesOnlyConf", num(len(s24 - s23)), "sites eligible only in 2024")


def history_v01(M, pct, num):
    """Disclosed history from the archived v0.1 development runs (results/design/): the pre-specified H8 failure
    before the D4 fix, FIFO packing at SF12, and the v0.1 H4 count before the D5 fix."""
    D = "results/design"
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    ok = sorted(elig[elig.status == "ok"].site)
    pre = pd.concat((pd.read_csv(f"{D}/sensitivity/pre_D4/{s}_picture.csv", dtype={"site": str}) for s in ok), ignore_index=True)
    nf = pre[(pre.trace == "none") & (pre.strategy == "design_bounded_nf")]
    bad = nf[nf.within_tol < 1 - 1e-12]
    assert bad.site.nunique() == 1 and set(bad.radio) == {R12}
    M("hEightPreSite", bad.site.iloc[0], "v0.1 pre_D4: the only site where newest-first fell short")
    M("hEightPreMin", pct(nf.within_tol.min(), 3), "v0.1 pre_D4: min within-tolerance share of newest-first, no outage")
    h8 = pd.read_csv(f"{D}/sensitivity/summary_H8_newest_first.csv")
    M("fifoMinSfTwelve", pct(h8[h8.radio == R12]["fifo_min"].min(), 2), "v0.1 summary_H8 FIFO min within-tolerance, SF12, no outage")
    h4 = pd.read_csv(f"{D}/summary_H4_picture.csv")
    M("hFourPassVOne", f"{int(h4.H4_pass.sum())}/{len(h4)}", "v0.1 summary_H4 (before the D5 fix)")
    assert set(h4[~h4.H4_pass].param) == {"DO", "pH"}


def ack_variant(M, pct, num, times, pp):
    """Review C6 (results/revision/ack_variant.csv): application- vs network-server acknowledgement, 2023 sites,
    LoRaWAN, series without events, final design at L2. Medians over sites per link x radio."""
    d = pd.read_csv(f"{R}/ack_variant.csv", dtype={"site": str})
    e = d.pivot_table(index=["site", "trace", "radio"], columns="strategy", values="energy_j_per_day")
    g = pd.DataFrame({"app_over_net": e.bounded_application / e.bounded_network,
                      "arq_over_app": e.arq_buffer / e.bounded_application}).groupby(level=[1, 2]).median()
    M("ackCostMin", pct(g.app_over_net.min() - 1, 0), "ack_variant: application / network energy - 1, min over link x radio")
    M("ackCostMax", pct(g.app_over_net.max() - 1, 0), "same, max")
    M("ackArqOverMin", times(g.arq_over_app.min()), "ack_variant: ARQ+buffer / bounded (application ACK), min")
    M("ackArqOverMax", times(g.arq_over_app.max()), "same, max")
    assert (g.app_over_net >= 1).all() and (g.arq_over_app > 1).all()
    worst = min((d.pivot_table(index=["site", "trace", "radio"], columns="strategy", values=f"within_{p}")
                 .pipe(lambda w: (w.bounded_application - w.arq_buffer)).groupby(level=[1, 2]).median().min())
                for p in ("T", "EC", "pH", "DO"))
    M("ackPicWorst", pp(worst, 2), "ack_variant: bounded (application ACK) - ARQ+buffer picture, worst median site (pp)")
    assert worst >= -0.01


def gof(M, pct, num):
    """Review M1 (results/revision/gof_models.csv): bootstrap KS (B = 200, refitted), and AIC robustness."""
    d = pd.read_csv(f"{R}/gof_models.csv").set_index(["record", "model"])
    pmin = 1 / (1 + 200)
    geo = d.xs("geom", level="model")
    assert (geo.ks_p_boot <= pmin + 1e-9).all(), "geometric rejected on every record"
    assert (d.best_aic == d.best_aic_without_longest).all(), "AIC best model unchanged without the longest gap"
    M("gofPmin", num(pmin, 3), "bootstrap KS: smallest attainable p with B = 200")
    for rec, k in (("InWaterSense", "Inws"), ("UVA", "Uva")):
        x = d.loc[rec]
        assert (x.ks_p_boot <= pmin + 1e-9).all(), f"{rec}: every model rejected"
        M(f"gofGeomD{k}", num(x.loc["geom", "ks_D"], 2), f"gof_models {rec} geometric KS D")
        M(f"gofBestD{k}", num(x[x.index != "geom"].ks_D.min(), 3), f"gof_models {rec} smallest KS D of the others")
    w = d.loc["Weija (v0.1 EC record)"]
    M("gofWeijaLnP", num(w.loc["dlnorm", "ks_p_boot"], 2), "gof_models Weija EC lognormal p")
    M("gofWeijaPlP", num(w.loc["zeta", "ks_p_boot"], 2), "gof_models Weija EC power-law p")
    M("gofInwsN", num(int(d.loc[("InWaterSense", "geom"), "n_outages"])), "gof_models InWaterSense gaps")
    M("gofUvaN", num(int(d.loc[("UVA", "geom"), "n_outages"])), "gof_models UVA runs")


def energy_mc(M, pct, num, times):
    """Review C7/M6 (results/revision/energy_mc_draws.csv): every measured energy component x U_log[1/2, 2]."""
    d = pd.read_csv(f"{R}/energy_mc_draws.csv")
    lo = d[d.radio != "NB-IoT"]
    M("mcDraws", num(d.draw.nunique()), "energy_mc draws")
    M("mcArqDearer", pct((lo.arq_over_unconf > 1).mean(), 0), "energy_mc: LoRaWAN draws with ARQ dearer than unconfirmed")
    q = lambda g, c, a: g.groupby(["trace", "radio"])[c].quantile(a)
    M("mcArqLow", times(q(lo, "arq_over_unconf", 0.025).min(), 1), "energy_mc: LoRaWAN ARQ/unconf, lowest 2.5% quantile")
    b = d.groupby(["trace", "radio"]).apply(lambda g: (g.batch_over_fair < 1).mean(), include_groups=False)
    sf12 = b[b.index.get_level_values("radio") == "LoRaWAN SF12"]; oth = b[b.index.get_level_values("radio") != "LoRaWAN SF12"]
    M("mcBatchCheapOther", pct(oth.min(), 0), "energy_mc: SF7/NB-IoT draws with batch cheaper than the fair baseline, min")
    M("mcBatchCheapTwelveMin", pct(sf12.min(), 0), "energy_mc: SF12 share, min over records")
    M("mcBatchCheapTwelveMax", pct(sf12.max(), 0), "energy_mc: SF12 share, max")
    M("mcBatchTwelveHi", times(q(d[d.radio == "LoRaWAN SF12"], "batch_over_fair", 0.975).max()), "energy_mc: SF12 batch/fair 97.5% quantile, max")
    M("mcBufMedMin", times(q(d, "buffer_over_fair", 0.5).min()), "energy_mc: buffer/fair median, min over record x radio")
    M("mcBufMedMax", times(q(d, "buffer_over_fair", 0.5).max()), "same, max")
    M("mcBufLo", times(q(d, "buffer_over_fair", 0.025).min()), "energy_mc: buffer/fair 2.5% quantile, min")
    M("mcBufHi", times(q(d, "buffer_over_fair", 0.975).max()), "energy_mc: buffer/fair 97.5% quantile, max")
    nb = d[d.radio == "NB-IoT"]
    M("mcNbArqMed", times(nb.arq_over_unconf.median()), "energy_mc: NB-IoT ARQ/unconf median")
    assert (lo.arq_over_unconf > 1).all() and oth.min() >= 0.98


def deep(M, pct, num):
    """Review C4/E4 (results/revision/deep/deep_*.csv): SAITS and StemGNN against the paper's estimators on the SAME
    gaps (second half of 2023, models trained on the first half). Shares within tolerance pooled over gaps."""
    import glob
    d = pd.concat(pd.read_csv(f, dtype={"target": str}) for f in sorted(glob.glob(f"{R}/deep/deep_*.csv")))
    w = d.groupby(["mode", "H_h", "method"]).within.mean()
    for mode, mk in (("bridging", "Bridge"), ("realtime", "Rt")):
        for H, hk in ((1, "One"), (24, "Day")):
            for meth, k in (("SAITS", "Saits"), ("StemGNN", "Stem")):
                M(f"deep{mk}{hk}{k}", pct(w[(mode, H, meth)], 0), f"deep: {meth} {mode} {H} h, share within tolerance")
    M("deepBridgeOneInterp", pct(w[("bridging", 1, "interpolation")], 0), "deep: interpolation 1 h bridging, same gaps")
    M("deepBridgeDayInterp", pct(w[("bridging", 24, "interpolation")], 0), "deep: interpolation 24 h bridging, same gaps")
    M("deepRtOneDiel", pct(w[("realtime", 1, "own diel")], 0), "deep: own diel 1 h real time, same gaps")
    M("deepRtDayDiel", pct(w[("realtime", 24, "own diel")], 0), "deep: own diel 24 h real time, same gaps")
    for mode in ("bridging", "realtime"):
        for H in (1, 24):
            best_classic = w[(mode, H)].drop(["SAITS", "StemGNN"]).max()
            assert max(w[(mode, H, "SAITS")], w[(mode, H, "StemGNN")]) < best_classic, f"deep beats classic: {mode} {H}"
    e = d[(d.H_h == 24) & (d["mode"] == "bridging")].groupby(["param", "method"]).max_err.median()
    M("deepDayDoSaits", num(e[("DO", "SAITS")], 1), "deep: SAITS 24 h bridging DO median max error (%sat)")
    M("deepDayDoInterp", num(e[("DO", "interpolation")], 1), "deep: interpolation, same")
    M("deepDayPhSaits", num(e[("pH", "SAITS")], 3), "deep: SAITS 24 h bridging pH median max error")
    M("deepDayPhInterp", num(e[("pH", "interpolation")], 3), "deep: interpolation, same")
    assert e[("DO", "SAITS")] < e[("DO", "interpolation")] and e[("pH", "SAITS")] < e[("pH", "interpolation")]
    assert e[("T", "SAITS")] >= e[("T", "interp. + neighbour")] and e[("EC", "SAITS")] > e[("EC", "interpolation")]
    best = d[d.H_h == 24].groupby(["param", "mode", "method"]).within.mean().max()
    M("deepDayBestAny", pct(best, 0), "deep file: best within-tolerance share of any estimator, any parameter, 24 h")
    assert best < 0.6
    M("deepGaps", num(int(d[(d.method == "SAITS")].shape[0])), "deep: gap x parameter evaluations per model")


def all_revision(M, pct, num, times):
    gof(M, pct, num)
    deep(M, pct, num)
    energy_mc(M, pct, num, times)
    independent_energy(M, pct, num, times)
    gap_cause(M, pct, num)
    node_off(M, pct, num)
    arq_timing(M, pct, num, times)
    storage(M, pct, num)
    k_sweep(M, pct, num, times)
    lorawan_checks(M, pct, num)
    tolerance_events(M, pct, num)
    netsim(M, pct, num, times)
    reconstruct(M, pct, num)
