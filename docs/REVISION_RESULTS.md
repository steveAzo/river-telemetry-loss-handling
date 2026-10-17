# Revision results (running log, started 2026-10-17)

Every number here comes from a file under `results/revision/` or `results/confirm/`, written by the script named. The paper will take its numbers from these files through `src/paper/paper_numbers.py`, not from this log.

---

## Defect found and fixed: D5 (tolerance tie)

- pH and T are recorded in 0.1 steps; an error of exactly one tolerance (pH 0.1) was counted in or out by floating-point noise (7.3 − 7.2 < 0.1 < 7.4 − 7.3). Fixed everywhere with one inclusive comparison (`sitedata.within_tol`); the trigger fires only beyond the tolerance. Tests: `tests/test_confirm.py`.
- Effect on the design runs (two sites checked): picture scores move by up to 10.5 pp (pH) and 2.6 pp (T); bounded-design energy falls by 0.4–2.5 J/day (spurious tie triggers removed); nothing else changes.
- Effect on reconstruction (`results/revision/chains/`): median errors unchanged; within-tolerance shares rise (pH up to 38 pp per pair). Example: own-diel, pH, 24-h gaps, median over pairs 29% → 45%.
- All 30 development sites are rerun with the frozen code (`results/confirm/2023_dev/`).

## C3 / E3: held-out confirmatory test

- Plan `docs/CONFIRMATORY_PLAN.md`, code frozen 2026-10-17T10:02:58Z (`docs/CONFIRMATORY_FREEZE.txt`) before any 2024 file was downloaded for analysis. Eligibility rule written as code reproduces the 2023 file exactly.
- 2024 data: all 39 candidates downloaded (3 after retries of connection resets); 33 eligible by the frozen rule (2023: 30).
- **Confirmatory verdicts (2024, 33 sites; `results/confirm/an2024_verdicts.json`), judged by the frozen script:** CH1 12/12, CH2 12/12, CH5 48/48, CH6 12/12, CH7 12/12, CH8 pass (minimum within-tolerance share 1.0), CH9 48/48 at L1 and at L3, CH10 12/12 at L1 and at L3. Every primary hypothesis passes in every combination.
- CH4 (expected to fail): fails in 9/48, all DO, on the no-outage, UVA and Weija links (event − ARQ+buffer = −6.9 to −9.0 pp). The plan expected DO and pH; pH clears the 5-pp rule in 2024.
- Secondary: 99.7% of injected events physically plausible; CH1 and CH7 pass on plausible events alone (12/12). ARQ+buffer / bounded energy (median site) 1.34–2.55× with site-bootstrap 95% CIs all above 1.28; bounded / batch 1 h 1.05–1.28×; bounded − ARQ picture ≥ −0.007 pp.
- **Development rerun (2023, 30 sites, D5-corrected; `results/confirm/an2023_verdicts.json`), same script:** CH1, CH2, CH5–CH10 all pass in every combination (as in v0.1). CH4: 38/48 pass, failures all DO (−5.1 to −10.8 pp). **Correction:** v0.1 reported H4 failing for DO *and pH* (29/48); the pH failures were the D5 tie, not batching. ARQ+buffer / bounded 1.32–2.51× (v0.1, FIFO packing: 1.30–2.32×); bounded / batch 1.05–1.34×.

## C1 / E1: cause of missing readings (`src/revision/gap_cause.py`)

- **Weija** (other streams of the same node as evidence): of the 916 missing conductivity slots in the v0.1 record, 773 (84%) were node-silent (no genuine reading from any stream) and 143 (16%) had another stream delivering (link up: a sensor/processing gap, not a delivery gap). In gaps ≥ 6 h only 6% of slots had another stream delivering: Weija's long gaps are node-wide silence (node off, logger down or uplink down: indistinguishable). Node-level record: loss 13.9%, 31 gaps, S(1 d) = 0.81 (v0.1 conductivity record: 15.8%, 62 gaps, 0.81).
- **InWaterSense** (two nodes, one shared gateway and GPRS link; node 2 operating May–Aug 2015, covering 57% of node 1's lost slots): node 2 was silent during 79% of node-1 missing slots vs 31% locally when node 1 delivered. Attribution (local baseline): gaps ≥ 6 h are ~74% shared-cause (gateway, GPRS, server or shared power) and ~26% node-1-specific; gaps < 6 h are 63% node-specific (as radio losses would be).
- **Node-off sensitivity** (`run_loss_revision.py` B): with f = 0–50% of long-gap slots reassigned to node-off periods, buffering still delivers every generated reading; delivered/expected falls to 0.83 (InWaterSense) and 0.92 (Weija node record) at f = 0.5; buffer energy vs the fair baseline (SF7, InWaterSense) 0.85 → 1.02. Weija has few long gaps: realised f is coarse (0.49, 0.69).

## C2 / E2 and M7: ARQ timing and the LoRaWAN version (`run_loss_revision.py` A)

- Specification texts checked (`papers/standards/`): LoRaWAN 1.0.2 §18.4 "strongly recommends" 8 transmissions with the data rate lowered every two; LoRaWAN L2 1.0.4 §4.3.1.3/§5.3 replaces this with NbTrans transmissions (default 1, range 1–15, network-set, no stepping); RP002: RETRANSMIT_TIMEOUT 1–3 s. The v0.1 ARQ is the 1.0.2 behaviour; 1.0.4 variants added.
- Retry instants modelled (RX windows, RETRANSMIT_TIMEOUT, 1% duty cycle, DR stepping).
- ARQ gain over unconfirmed (pp of all readings), no added radio loss, InWaterSense: full-slot 0; uniform restoration 0.1–4.6 (more at SF12, whose retries span longer); burst model (short gaps as radio bursts, optimistic) 6.5–7.7; out of 46 pp lost. Buffering recovers all 46 pp at 0.67–1.14× unconfirmed energy; ARQ costs 2.3–7.3×. Weija: ARQ < 1 pp in every model.
- 1.0.4 (no stepping) vs 1.0.2 at SF7: 6.8× vs 7.3× unconfirmed energy (8 transmissions); identical at SF12.

## C5 / E6: storage and backlog (`run_loss_revision.py` C)

- Flash energy (Winbond W25Q128JV Rev F, §9.4, AC table; host awake): typical 20 µJ, worst 200 µJ per 12-B reading; adds ≤ 0.03 J/day against 19–160 J/day of radio energy.
- RAM buffer: 2 KB loses 24% of readings (InWaterSense), 8 KB 10%; ≥ 22 KB (the longest backlog) loses none.
- Drain limited by the duty cycle (one frame per slot kept free for live traffic): every reading still delivered; at SF7 backlogs clear in hours; at SF12 on InWaterSense (1 frame/slot) median clearance 1.2 h but the worst backlog persists for weeks in the record's bad period, delaying live readings (p95 600 h). The v0.1 model let backfill and live traffic share the channel freely.

## E7 / M5: back-off cap and batch period (`sweep_k_batch.py`)

- InWaterSense, SF7, buffer + back-off: probing every slot costs 2.2× the energy of K = 6 h; K 6 → 24 h saves a further 12% while the p90 recovery latency (link back → gap's last reading delivered) triples (20 → 61 h). K = 3–6 h is the knee. NB-IoT: every-slot probing costs 3.7× (search energy).
- Batch period: energy falls steeply to 1 h, then slowly; within-1-h share collapses beyond 1 h.

## M1 / M2: absolute goodness of fit (`outage_gof.py`)

- Every outage is bounded by deliveries on both sides: outage lengths are uncensored by construction.
- With ~2,700 outages (InWaterSense) every model fails the bootstrap KS test (p ≤ 0.005, B = 200), including the AIC winner; the geometric's misfit is an order of magnitude larger (D = 0.49 vs 0.03). Wording: no tested distribution fits absolutely; the geometric fails worst, and in the decision-relevant tail. (Final run pending: sampler fix for the truncated lognormal.)

## M3 / M4: frame counters and UVA bins (`lorawan_checks.py`)

- UVA: 2.09 M receptions, 1.23 M unique (sensor, FCnt); no counter reuse (0 pairs received > 60 s apart); one counter decrease; every sensor-month at the 5-min cadence; jump threshold 1,000 vs 5,000 changes missing frames by 2%.
- UVA system bins 5/10/15/30 min: availability 98.7% throughout; outages 14 → 8; down-time share in outages ≥ 1 d 82–84%; system share of missing frames 28.0–28.6%.
- LoED well-heard devices: pooled loss 10.0% (reset threshold 100) vs 10.9% (1,000); 81 of 179 devices show a counter reset (median 1).

## M12 / E10 and M14 (`tolerance_events.py`)

- Tolerances (median over sites) vs USGS "excellent" accuracy (Wagner et al. 2006, TM 1-D3, Table 18): DO 2 vs 4.7 %sat; EC 4.2 vs 6.3 µS/cm; T 0.2 vs 0.2 °C; pH 0.1 vs 0.2. L2 is at or inside the USGS excellent band for all four; L3 about the excellent/good boundary; all far below the median daily range (DO 10 %sat, EC 12 µS/cm, T 1.1 °C, pH 0.25).
- Injected amplitudes (median 5σ/8σ): DO 7.4/11.9 %sat, EC 7.4/11.9 µS/cm, T 0.74/1.19 °C, pH 0.50/0.80. Real 3-h excursions ≥ 5σ occur at 100% of sites (DO, T), 93% (EC), 60% (pH); ≥ 8σ at 97%, 93%, 83%, 37%. pH 8σ steps are on the large side.

## E9 / M9, M13: reconstruction statistics (`reconstruct_stats.py`)

- Chain-blocked bootstrap (9 chains, B = 5,000): pooled share of 24-h gaps kept within tolerance by the best of all six estimators: 31% (95% CI 18–49%); T 9%, pH 49%. Intervals are wide.
- Lags do not follow the flow: downstream neighbours get positive lags about as often as upstream ones (DO 64% vs 68%); EC 6-h-change correlations are weak (median 0.11–0.16). Distances 2.8–300 km (median 42).

## C8 / E8: many nodes recovering at once (`netsim.py`; ALOHA check in `tests/test_netsim.py`)

- Without jitter, synchronised back-off livelocks: nodes collide at every probe and none recovers within 72 h (200 nodes, SF7). Randomised probe jitter is required.
- With 1-h jitter, SF7: every node recovers up to 500 per gateway; median node clears in 2–9 h, the last within ~40 h; per-node energy 1.1–12.5× that of a node recovering alone.
- SF12: the gateway's RX1 downlink (1% sub-band) saturates and up to 29% of received frames go unacknowledged; beyond ~50 nodes per gateway, confirmed backfill after a 1-day outage does not complete within 72 h. Per-node results hold for small cells; large SF12 cells are downlink-limited.

## C7 (no hardware): what can be checked

- Independent measurement (Ugwuanyi et al. 2021, FiPy board): ≈1.2 J per 44-B LoRaWAN SF7 uplink, ≈21 J per NB-IoT uplink (TCP, no RAI). Our model at the same 44 B, host included: 0.45 J (SF7) and 0.54 J (NB-IoT RAI): the board measured 3× (LoRaWAN) and 40× (NB-IoT, TCP without RAI) more. (An earlier note in this log said ≈0.2 J for SF7; that was a rough estimate, corrected here from `revision_numbers.independent_energy`.) Absolute energy is platform- and stack-dependent; only the ordering agrees. Bouguera et al. (2018) is datasheet-modelled, not measured. Claims will be within-radio ratios; robustness by Monte Carlo over ×0.5–×2 per component (`energy_mc.py`, pending).

## Later results (2026-10-17, evening)

- **M1 final** (`gof_models.csv`, B = 200, inverse-CDF sampler fix): geometric rejected on every record (p ≤ 0.005). InWaterSense (1,619 gaps) and UVA (36,519 runs): every model rejected; D geometric 0.48 / 0.26 vs best other 0.027 / 0.008. Weija EC: lognormal p = 0.37, power law p = 0.64 (not rejected). AIC best model unchanged without the longest gap.
- **C6** (`ack_variant.csv`, 2023 sites, LoRaWAN): application-ACK variant +3% to +18% energy vs network-ACK; picture within 0.02 pp of per-reading at the median site; ARQ+buffer 1.29–2.00× its energy.
- **C7 Monte Carlo** (`energy_mc_draws.csv`, 100 draws, ×U_log[0.5, 2] per component, NB search 2.2–60 s): LoRaWAN ARQ > unconfirmed in 100% of draws (≥1.8× in 97.5%); NB-IoT ARQ ≈ unconfirmed (median 1.01×). Batch < fair baseline in ≥98% of draws at SF7/NB-IoT, 85–93% at SF12 (up to 1.24×). Buffer/fair median 0.81–1.10×, 95% range 0.50–2.08×: the sign of buffering's premium is not robust; text scoped accordingly.
- **E4 deep baselines**: StemGNN at the first setting (2 layers, 2 stacks, width 64) has 49 M parameters at a 192-h window and was paged out / killed on this 3.6-GB machine; rerun with 1 layer, 1 stack, width 16 (7.5 M parameters). SAITS: 0.14 M parameters.
- **Format**: two-column draft 19 pages; TGCN review copy (single column, double spaced, 12 pt) 45 pages, over the 30-page limit: condensation is required for both limits.
- **E4, first run discarded (setup defect, mine):** with global z-scores (half-year mean/SD), both deep models under-fitted by an order of magnitude even on 1-h gaps (SAITS T error 2.0 °C vs 0.025 °C for interpolation; more windows and 300 epochs did not help). Cause: the within-window signal sits far from zero on a global scale, giving level errors of ~0.3 SD. Fix: per-window, per-series normalisation from the window's observed values (RevIN-style). Probe on McKenzie: SAITS 1-h T error 0.32 °C; at 24 h SAITS beats interpolation (T 0.82 vs 1.00 °C; pH 0.15 vs 0.67). The discarded run is kept in `results/revision/deep_run1_globalz_discarded/`; the corrected run uses stride 12 h, up to 100 epochs, patience 10. The paper's reconstruction claims wait for the corrected run.
