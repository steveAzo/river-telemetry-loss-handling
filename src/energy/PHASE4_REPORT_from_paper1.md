# Phase 4 report: energy, battery life, and where report suppression actually matters

*2026-10-04. Code: `src/energy/params.py` (every parameter with its source), `src/energy/model.py`, `src/energy/run_phase4.py`; analysis `src/analysis/phase4_analysis.py`. Tables: `results/phase4/tables/`. Figures: `results/phase4/figures/`. Tests: `tests/test_energy.py`. Hardware: none (model from published measurements, as planned).*

## 1. Model and its validation

**Daily energy of a node** that samples every cycle and sends N_r reports per day:
- the **sleep floor**: host microcontroller in deep sleep, plus the radio's sleep;
- **sensing**: host awake with the probes powered, the same for every scheme;
- **reporting**: radio energy per report, plus the host awake while the modem works.

**Parameter sources:**

| Component | Source | Values |
|---|---|---|
| NB-IoT report | Michelinakis 2021 (paper 11): commercial networks, two modules | release-after-send (RAI-200) 0.11–0.31 J; confirmed via reply (RAI-400) 0.12–0.33 J; default timers 0.82–1.27 J; bad coverage up to 1.33 J. PSM sleep 9.35–10.61 µW |
| LoRaWAN report | Casals 2017 (paper 09): mDot measured state by state, recomputed for our 20-byte report | SF7: 0.24 J unconfirmed, 0.16 J confirmed (ACK in RX1); SF12: 0.73 / 0.86 J. Sleep 45 µA |
| Host and sensors | Libelium Waspmote datasheet | 17 mA awake + 1.6 mA Smart Water board; 33 µA deep sleep |
| Sensing time per sample | Not documented in our sources, so **swept** | 1 / 5 / 15 / 30 s |

**Validation against the sources:**
- The model reproduces **20 of the 24** battery lifetimes in Michelinakis's Table X exactly (to 0.1 years). The other 4 contradict the paper's own equation; for example, N211/Op2 lists 5.7 years at a 24-h interval but 5.9 years at 4 h.
- It reproduces Casals's airtime table exactly and 5 of 6 lifetime checkpoints to within 4%. The sixth is inconsistent with their own 60-min value.
- It reproduces Casals's finding that confirmed uplink is *cheaper* at DR5 (the ACK in RX1 skips the RX2 wait). At DR0 their tables imply +12–18% rather than the "≈3%" stated; we keep the conservative value.

## 2. Battery life (6,600 mAh, as on the Weija node; confirmed uplink with 1% loss; USGS medians, L2)

| Radio | Sensing time | Report every cycle | Send-on-delta | **RLS-D** | Gain |
|---|---|---|---|---|---|
| NB-IoT N211, RAI | 5 s | 2.6 y | 4.3 y | **4.6 y** | **1.72×** |
| NB-IoT N211, RAI | 1 s | 3.5 y | 7.8 y | **8.8 y** | 2.35× |
| NB-IoT N211, RAI | 30 s | 0.96 y | 1.13 y | 1.14 y | 1.19× |
| NB-IoT N211, default timers | 5 s | 0.87 y | 2.3 y | **2.7 y** | 2.88× |
| LoRaWAN SF12 | 5 s | 1.5 y | 2.9 y | **3.2 y** | 2.05× |
| LoRaWAN SF7 | 5 s | 2.7 y | 3.75 y | **4.0 y** | 1.41× |

**Uncertainty: is the host awake while the modem works?** If the host sleeps instead, the gains fall (N211 RAI 1.72× → 1.47×, LoRa SF7 1.41× → 1.20×, default NB-IoT 2.88× → 2.30×). The paper will report both ends of each range.

**Findings.**
1. **Error-bounded, report-level suppression extends battery life 1.1–3.5×.** The gain is set by the ratio of report energy to sensing energy (fig 10). It is largest for costly radios (default NB-IoT timers, LoRaWAN SF12) and short sensing. With 30 s sensing per sample almost nothing else matters.
2. **RLS-D's extra gain over send-on-delta is modest:** +6.9% (L1), +5.5% (L2), +1.2% (L3), +0.1% (L4) for N211 RAI with 5 s sensing; up to +18% at single sites.
   - After suppression, reporting is only 10–27% of the energy (RAI/LoRa), against sensing 40–63% and sleep 21–39%.
   - **This answers Phase 3's open question:** RLS-D's higher report counts at L4 have no practical lifetime cost.
3. **The event detector costs about 1% of battery life** (RLS-D + sensitive detector 4.58 y vs 4.62 y).
4. **Equal-accuracy comparison** (fig 11; N211 RAI, 5 s sensing):
   - At the same worst-case error, RLS-D at L4 lives **53% longer** than 30-min reporting (5.39 vs 3.52 y).
   - At about the same battery life, RLS-D at L2 has a **7.8× smaller** worst-case error than hourly reporting (4.62 vs 4.32 y). It also reports events immediately (Phase 2).

## 3. When energy is NOT the binding constraint (framing for RQ4)

**Solar nodes have a large margin.** The node averages 0.6–1.0 mW (2.8 mW in the worst case modelled). The Weija node's 2 W panel would deliver about 15 kJ/day at roughly 3.5 peak-sun hours with 0.6 derating (both assumptions). That is **≥ 33× the worst-case need**; a 0.06 W panel would suffice.

**Report suppression therefore matters most for:**
- battery-only nodes: submerged or enclosed probes, pipes, manholes (InWaterSense node 2 sat in a manhole);
- smaller and cheaper batteries and panels;
- non-energy costs, which scale directly with reports:
  - per-message or data charges on cellular IoT plans;
  - LoRaWAN airtime under the EU868 1% duty cycle;
  - channel capacity.

**Proposed RQ4 wording:** "what report suppression buys in battery life, hardware size and per-message cost, and when each matters." This is for discussion with the Prof.

## 4. Limitations

- **Sensing time per sample is not documented** in our sources, so it is swept (1–30 s). A datasheet or bench measurement would pin it down. This is the single largest uncertainty, and it changes conclusions quantitatively, not qualitatively.
- **The radio parameters come from specific modules and operators** (u-blox N211, Quectel BC95, MultiTech mDot). Michelinakis shows that the choice of module and operator matters more than anything else, so the absolute lifetimes are indicative while the ratios are robust.
- **Assumptions:**
  - an ideal battery with no self-discharge (as in the sources);
  - the test period (≈ 80% of a year, spring to winter) stands in for a full year;
  - no LTE-M or GPRS: no measured per-report energy in our sources. InWaterSense used GPRS, which is typically far costlier per connection, so the gains would be larger. A source is needed before claiming this.
- **TAU is ignored:** every scheme reports at least daily, so tracking-area updates aren't needed (Michelinakis Sec. IX).
