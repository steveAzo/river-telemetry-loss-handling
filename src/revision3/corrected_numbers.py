"""Revision 3, Step 5: every paper number regenerated from the corrected (post hoc) runs, by the paper's own scripts.

src/paper/paper_numbers.py and src/paper/revision_numbers.py are run unchanged. This wrapper only
  * applies the audit corrections to the energy model (corrected.apply(): numbers computed from the model itself,
    such as the host power and the per-report energies, use the corrected currents);
  * redirects reads of result files that depend on energy or DO to their corrected versions (MAP below);
  * redirects the outputs to results/revision3/numbers/ (numbers.tex and tables/), so that the draft is untouched
    until every changed number has been reviewed (results/revision3/numbers/changes.md);
  * first regenerates results/revision3/rerun/reconstruct_* with src/revision/reconstruct_stats.py, unchanged, on
    the corrected river chains;
  * adds one macro, hostSenseMW (power while sensing: host, sensor board, and four sensors).
Inputs that depend on neither (outage records, goodness of fit, gap cause, LoRaWAN counters) are read as they are.
The frozen confirmatory verdicts (results/confirm/an2024_verdicts.json) stay the confirmatory result; the corrected
verdicts must be identical to them (asserted).
Usage (from Paper2/): python -I src/revision3/corrected_numbers.py [--adopt]   (--adopt: copy into draft/)
"""
import builtins
import glob as _glob
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, "src/paper")
from revision3 import corrected  # noqa: E402

R3 = "results/revision3"
OUTDIR = Path(f"{R3}/numbers")
RR = f"{R3}/rerun"
REV_FILES = ["loss_A.csv", "loss_B.csv", "loss_C.csv", "sweep_k_batch.csv", "netsim.csv", "energy_mc_draws.csv",
             "energy_mc_summary.csv", "ack_variant.csv", "tolerance_summary.csv", "tolerance_sites.csv",
             "reconstruct_bootstrap.csv", "reconstruct_pairs_spatial.csv"]
MAP = ([("results/scoping/loss_handling.csv", f"{RR}/loss_handling.csv")]
       + [(f"results/revision/{f}", f"{RR}/{f}") for f in REV_FILES]
       + [("results/revision/chains/", f"{RR}/chains/"), ("results/revision/deep/", f"{RR}/deep/"),
          ("results/confirm/an2024_", f"{R3}/an2024c_"), ("results/confirm/an2023_", f"{R3}/an2023c_"),
          ("results/confirm/2024/", f"{R3}/corrected_2024/"), ("results/confirm/2023_dev/", f"{R3}/corrected_2023_dev/"),
          ("draft/tables/", f"{OUTDIR}/tables/")])
USED = set()


def remap(p):
    if not isinstance(p, (str, Path)):
        return p
    s = str(p).replace("\\", "/")
    for a, b in MAP:
        if s.startswith(a):
            USED.add(a)
            return b + s[len(a):]
    return p


_read_csv, _open, _glob_glob = pd.read_csv, builtins.open, _glob.glob


def install():
    pd.read_csv = lambda p, *a, **k: _read_csv(remap(p), *a, **k)
    builtins.open = lambda p, *a, **k: _open(remap(p), *a, **k)
    _glob.glob = lambda p, *a, **k: _glob_glob(remap(p), *a, **k)


# the call sequence of paper_numbers.py's __main__ block, checked against its source
PN_CALLS = ["outages_water", "outages_lorawan", "outage_models_table", "strategies", "chains", "energy_params",
            "records_extra", "outages_extra", "lorawan_extra", "handling_extra", "chains_extra", "standalone_extra"]
RN_CALLS = ["all_revision", "design_years", "history_v01", "netsim_table", "ack_variant"]


def check_sequence():
    src = _open("src/paper/paper_numbers.py", encoding="utf-8").read().split('if __name__ == "__main__":')[1]
    pn = [m for m in re.findall(r"^    (\w+)\(\)\s*$", src, re.M) if m != "write"]
    rn = re.findall(r"^    RN\.(\w+)\(", src, re.M)
    assert pn == PN_CALLS, f"paper_numbers main changed: {pn}"
    assert rn == RN_CALLS, f"paper_numbers main changed: {rn}"


def macros(path):
    out = {}
    for line in _open(path, encoding="utf-8"):
        m = re.match(r"\\newcommand\{\\(\w+)\}\{(.*)\}  % (.*)$", line.rstrip("\n"))
        if m:
            out[m.group(1)] = (m.group(2), m.group(3))
    return out


def report():
    old, new = macros("draft/numbers.tex"), macros(OUTDIR / "numbers.tex")
    changed = [k for k in old if k in new and old[k][0] != new[k][0]]
    lines = ["# Paper numbers: frozen-model draft vs corrected post hoc runs", "",
             f"Macros: {len(old)} in draft/numbers.tex, {len(new)} corrected; {len(changed)} changed.", "",
             "| Macro | Draft | Corrected | Source |", "| --- | --- | --- | --- |"]
    lines += [f"| {k} | {old[k][0]} | {new[k][0]} | {new[k][1]} |" for k in changed]
    lines += ["", "Only in the draft: " + (", ".join(sorted(set(old) - set(new))) or "none"),
              "Only in the corrected set: " + (", ".join(sorted(set(new) - set(old))) or "none"), "", "Tables:"]
    for f in sorted((OUTDIR / "tables").glob("*.tex")):
        d = Path("draft/tables") / f.name
        same = d.exists() and _open(d, encoding="utf-8").read() == _open(f, encoding="utf-8").read()
        lines.append(f"- {f.name}: {'unchanged' if same else 'CHANGED'}")
    (OUTDIR / "changes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(changed)} of {len(old)} macros changed -> {OUTDIR / 'changes.md'}")


def whole_node(M, pct, times):
    """Audit issue 5: transmission energy vs whole-node energy (held-out 2024, corrected model, clean series).
    Node energy per day = B / (365 Y) from each row's lifetime Y (it includes the sleep and sensing floor), so the
    floor is recovered exactly as node - E_tx. Final design = design_bounded_nf at L2; ARQ + buffer at '-'."""
    from run_design_eval import BATTERY
    en = pd.concat(pd.read_csv(f, dtype={"site": str}) for f in sorted(_glob_glob(f"{R3}/corrected_2024/*_energy.csv")))
    fin, arq = "design_bounded_nf", "arq_buffer"
    k = ["trace", "radio", "site"]
    # as analyse_confirm.py: ARQ+buffer on the clean series; the design with its event uploads (mean over the
    # injected-event settings, L2). The floor (sleep + sensing) is the same for both on a site and radio.
    a = en[(en.setting == "clean") & (en.strategy == arq)].set_index(k)
    floor = BATTERY / (365 * a.lifetime_y) - a.energy_j_per_day
    e_arq = a.energy_j_per_day
    e_fin = en[(en.setting != "clean") & (en.strategy == fin)].groupby(k).energy_j_per_day.mean().reindex(e_arq.index)
    assert e_fin.notna().all()
    node_arq, node_fin = floor + e_arq, floor + e_fin
    share = pd.DataFrame({fin: e_fin / node_fin, arq: e_arq / node_arq}).groupby(level=[0, 1]).median()
    assert ((share > 0) & (share < 1)).all().all()
    M("txShareFinalMin", pct(share[fin].min(), 0), "corrected_2024: final design (with event uploads), median over sites of E_tx / node energy, min over link x radio")
    M("txShareFinalMax", pct(share[fin].max(), 0), "same, max")
    M("txShareArqMin", pct(share[arq].min(), 0), "corrected_2024: ARQ+buffer E_tx / node energy, min")
    M("txShareArqMax", pct(share[arq].max(), 0), "same, max")
    # ratios as analyse_confirm.py forms them: per site, then the median over sites per link x radio
    tx = (e_arq / e_fin).groupby(level=[0, 1]).median()
    node = (node_arq / node_fin).groupby(level=[0, 1]).median()
    an = pd.read_csv(f"{R3}/an2024c_energy.csv").set_index(["trace", "radio"]).arq_over_bounded
    assert (tx.reindex(an.index) - an).abs().max() < 0.02, "tx ratio differs from the analysis script's"
    assert (node < tx).all() and (node > 1).all()
    M("nodeArqOverFinalMin", times(node.min()), "corrected_2024: ARQ+buffer / final design, whole-node energy (median over sites of per-site ratios), min")
    M("nodeArqOverFinalMax", times(node.max()), "same, max")
    life = node                                       # lifetime ~ 1 / node energy: Y_final / Y_arq = node ratio
    assert (life > 1).all()
    M("lifeGainMin", pct(life.min() - 1, 0), "corrected_2024: lifetime gain of the final design over ARQ+buffer, min")
    M("lifeGainMax", pct(life.max() - 1, 0), "same, max")


def no_batch(M, pct, num, times, pp):
    """Audit issue 11 (results/revision3/no_batch/, src/revision3/no_batch_ablation.py): the final design without its
    hourly batch (bounded-error trigger, alarms, buffering kept). Medians over the 2024 sites per link x radio."""
    d = pd.concat(pd.read_csv(f, dtype={"site": str}) for f in sorted(_glob_glob(f"{R3}/no_batch/*.csv")))
    assert d.site.nunique() == 33
    g = d.groupby(["trace", "radio", "variant"]).median(numeric_only=True).unstack("variant")
    fin, trg = "final design", "trigger only"
    e = g["energy_j_per_day"][trg] / g["energy_j_per_day"][fin]
    assert (e < 1).all()
    M("noBatchSaveMin", pct(1 - e.max(), 0), "no_batch: 1 - trigger-only / final design energy (site medians), min over link x radio")
    M("noBatchSaveMax", pct(1 - e.min(), 0), "same, max")
    w = g["within_1h"]
    M("noBatchHourMin", pct(w[trg].min(), 0), "no_batch: trigger-only share of readings delivered within 1 h, min over link x radio")
    M("noBatchHourMax", pct(w[trg].max(), 0), "same, max")
    M("noBatchHourNoneFinal", pct(w[fin].xs("none", level="trace").min(), 0), "no_batch: final design within 1 h, no outage, min over radios")
    diff = max((g[f"within_{p}"][trg] - g[f"within_{p}"][fin]).abs().max() for p in ("T", "EC", "pH", "DO"))
    M("noBatchPicMaxDiff", f"{100 * diff:.1f}","no_batch: largest |trigger-only - final design| picture share (site medians), any parameter")


def headroom(M, pct):
    """Audit issue 12 (results/revision3/rerun/headroom_summary.csv, src/revision3/run_headroom.py): energy a
    probing schedule fitted to the record's gaps (lognormal, 2-fold cross-validated, 20 splits) saves over the
    design's capped back-off, at the same detection delay, as a share of the design's daily energy."""
    s = pd.read_csv(f"{RR}/headroom_summary.csv")
    s = s[s.frontier == "lognormal_cv"].set_index(["record", "radio"]).max_saving_share
    lo = s[s.index.get_level_values("radio").str.startswith("LoRaWAN")]
    nb = s[s.index.get_level_values("radio").str.startswith("NB-IoT")]
    M("probeSaveLoraMax", pct(lo.max(), 1), "headroom lognormal_cv: largest saving on LoRaWAN, any record")
    M("probeSaveLoraWeijaMax", pct(lo.xs("Weija (node record)", level="record").max(), 1), "same, Weija, max over SFs")
    M("probeSaveNbMax", pct(nb.max(), 0), "headroom lognormal_cv: largest saving on NB-IoT (10-s search), any record")
    M("probeSaveNbRecord", nb.idxmax()[0], "the record of that NB-IoT maximum")


def do_altitude(M, num):
    """Audit issue 18: the barometric factor at the highest sites (data/clean/usgs_baro, src/revision3/do_baro.py)."""
    pr = {}
    for f in _glob_glob("data/clean/usgs_2024_baro/*.csv") + _glob_glob("data/clean/usgs_baro/*.csv"):
        pr[Path(f).stem] = float(_read_csv(f, usecols=["p_ratio"], nrows=1).p_ratio.iloc[0])
    hi = {s: p for s, p in pr.items() if p < 0.95}            # the high sites (all Klamath, about 1,200 m)
    assert hi and all(s.startswith(("115", "420853")) for s in hi), hi
    M("doAltFactorMin", num(1 / max(hi.values()), 2), "do_baro: 1 / (p/p0), lowest of the high (Klamath) sites")
    M("doAltFactorMax", num(1 / min(hi.values()), 2), "same, highest")
    M("doAltSites", num(len(hi)), "do_baro: sites with p/p0 < 0.95 (both years)")


def main():
    check_sequence()
    corrected.apply()
    (OUTDIR / "tables").mkdir(parents=True, exist_ok=True)
    install()
    from revision import reconstruct_stats as RS          # corrected chains -> rerun/reconstruct_*
    RS.main(f"{RR}/reconstruct")
    import paper_numbers as PN
    PN.OUT, PN.TAB = OUTDIR, OUTDIR / "tables"
    for c in PN_CALLS:
        getattr(PN, c)()
    import revision_numbers as RN
    M, pct, num, times, pp = PN.M, PN.pct, PN.num, PN.times, PN.pp
    RN.all_revision(M, pct, num, times)
    RN.design_years(M, pct, num, times, pp)
    RN.history_v01(M, pct, num)
    RN.netsim_table()
    RN.ack_variant(M, pct, num, times, pp)
    M("hostSenseMW", num(corrected.P_SENSE * 1e3, 0), "revision3 corrected.P_SENSE (mW): host, board, T, EC, DO, pH")
    whole_node(M, pct, times)
    no_batch(M, pct, num, times, pp)
    headroom(M, pct)
    do_altitude(M, num)
    for y in ("2023", "2024"):                             # the correction must leave every verdict unchanged
        frozen = json.load(_open(f"results/confirm/an{y}_verdicts.json"))["verdicts"]
        corr = json.load(_open(f"{R3}/an{y}c_verdicts.json"))["verdicts"]
        assert frozen == corr, f"{y}: verdicts changed {frozen} vs {corr}"
    PN.write()
    unused = [a for a, _ in MAP if a not in USED]
    print("redirects never used:", unused)
    report()
    if "--adopt" in sys.argv:                              # copy into the draft (the paper's numbers since revision 3)
        import shutil
        body = (OUTDIR / "numbers.tex").read_text(encoding="utf-8").split("\n", 1)[1]
        Path("draft/numbers.tex").write_text("% Revision 3: generated by src/revision3/corrected_numbers.py (paper_numbers.py "
                                             "and revision_numbers.py on the corrected post hoc runs) -- do not edit by hand.\n"
                                             + body, encoding="utf-8")
        for f in (OUTDIR / "tables").glob("*.tex"):
            shutil.copy(f, Path("draft/tables") / f.name)
        print("adopted into draft/numbers.tex and draft/tables/")


if __name__ == "__main__":
    main()
