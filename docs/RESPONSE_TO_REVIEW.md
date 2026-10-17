# Response to the pre-submission review (16 October 2026)

Manuscript: "Outage-Aware Reporting and Loss Recovery for Energy-Efficient River Water-Quality Telemetry over LPWANs" (previously "Retransmit, Backfill or Reconstruct? Loss Handling for River Water-Quality Telemetry under Real Outages"). Target: IEEE Transactions on Green Communications and Networking.

Each item gives what was done and where it appears in the revised manuscript. Items marked PENDING await runs in progress; they will be completed before the manuscript is finalised. Analysis details and source files: `docs/REVISION_RESULTS.md`.

One thing could not be done: no hardware is available to the authors, so the hardware or hardware-in-the-loop validation (C7/E5) is replaced by the checks described under C7.

---

## Title (§3)
Changed to the review's formal alternative. "Real outages" no longer appears; the paper speaks of delivery gaps, and of system outages only where verified.

## Critical issues (§5)

**C1. Missing readings treated as communication outages.** Partly resolvable from the data, and resolved as far as the data allow (Sec. III-B):
- Weija: the node's other sensor streams show whether the node and uplink were alive. 84% of missing conductivity slots were node-wide silences, 16% conductivity-only gaps with the link up; in gaps of 6 h or more only 6% of slots had another stream delivering.
- InWaterSense: the second node behind the same gateway and GPRS link shows whether a gap was shared. Gaps of 6 h or more were about 74% shared-cause and 26% node-specific.
- Terms: "delivery gap" for the water-quality records; "system outage" only for verified cases (UVA, LoED).
- Sensitivity (E1): up to 50% of long-gap slots reassigned to a node that was off. Buffering still delivers every generated reading; expected-reading recovery falls to 83% (InWaterSense) and 92% (Weija); energy relative to the fair baseline 0.85 → 1.02. Buffering's recovery is presented as an upper bound, conditional on generation.

**C2. ARQ replay structurally pessimistic.** Retry instants are now modelled (receive windows, RETRANSMIT_TIMEOUT, duty cycle), and three timing models bracket the replay (full slot; uniform restoration within the gap's last slot; short gaps as radio bursts, optimistic for ARQ). On InWaterSense, LoRaWAN ARQ recovers 0, 0.1–4.6 and 6.5–7.7 percentage points of the 46 points lost, at 2.3–7.3× the energy of unconfirmed reporting; buffering recovers all 46 points. "Recovers none" is replaced by the bracketed statement (Sec. V-A).

**C3. H5–H10 not independently validated.** A held-out confirmatory test on 2024 data from the same candidate sites (33 eligible) was planned, and its code frozen with SHA-256 hashes, before any 2024 file was downloaded for analysis (`docs/CONFIRMATORY_PLAN.md`). The 2023 results are presented as development evidence (rerun with D4/D5 fixed). **Result (2024, 33 sites, frozen code):** every primary hypothesis passes in every combination (alarm latency 12/12, energy 12/12, picture 48/48 at L1, L2 and L3, exact picture with the link up); the expected failure of plain event-driven batching (H4) recurs, for DO only. Per-reading ARQ uses 1.34–2.55× the bounded design's energy (site-bootstrap 95% CIs all above 1.28×). Sec. VII, Table V.

**C4. Reconstruction claim too broad.** Two contemporary deep imputers added, SAITS (self-attention) and StemGNN (graph neural network), trained only on the first half of 2023 (with whole-site block masks of 1–72 h), tested on gaps in the second half, on the same 48,455 gap–parameter cases as the paper's estimators (Sec. VI-C). GRIN/SPIN could not be run on the available machine; ImputeFormer was tried and dropped for compute. A first deep configuration (global normalisation) under-fitted by an order of magnitude and was discarded before any comparison; this is stated. Result: the deep models keep fewer gaps within tolerance than the simple estimators (1 h bridging: 65% vs 97%; 24 h: 25% vs 31%), but SAITS reduces the median error of DO (4.3 vs 6.7 %sat) and pH (0.126 vs 0.148) when bridging day-long gaps. No estimator keeps more than 55% of day-long gaps of any parameter within tolerance. Every claim is limited to the evaluated estimators, which now include two deep imputers.

**C5. "Buffering delivers every reading" relies on ideal storage.** Finite RAM buffers (2 KB loses 24%, 8 KB 10%, 64 KB none), flash-write energy from a datasheet (at most 0.03 J/day), and a duty-cycle-limited drain (all delivered; at SF12 a backlog can persist for weeks in the worst period) are reported. The claim is now conditional on generation, storage and reconnection (Sec. V-C).

**C6. ACK boundary.** Stated explicitly: NB-IoT's confirmation is the application's reply (as in the energy measurements); LoRaWAN's is the network server's. A variant of the trigger that keeps the bound for both possible server states until an application ACK returns in a later downlink is implemented and tested. Result: the application-ACK variant costs 3–18% more energy; its picture stays within 0.02 pp of per-reading reporting; per-reading ARQ still costs 1.29–2.00× as much (Sec. VII-H).

**C7. No hardware validation.** Not possible (no hardware). Instead: (a) comparison with the only independent measurement found (a different board and stack measured 3× the model's per-message energy on LoRaWAN and 40× on NB-IoT), which is why every claim is a ratio between strategies on the same radio; (b) Monte Carlo propagation of ×0.5–×2 uncertainty on every measured energy component (100 draws): on LoRaWAN ARQ costs more than unconfirmed reporting in 100% of draws; hourly batching is cheaper than the fair baseline in ≥98% of draws at SF7 and on NB-IoT but only 85–93% at SF12; buffering's energy relative to the baseline is 0.50–2.08× (median 0.81–1.10). The paper states which orderings survive and which do not (Sec. V-F); (c) stated as a limitation, with hardware validation as future work.

**C8. Multi-node contention.** A discrete-event model of one gateway and up to 500 nodes recovering from a shared outage (Sec. V-E, Table netsim), validated against pure ALOHA. Without randomised probe jitter, synchronised back-off livelocks; with it, SF7 cells of 500 nodes recover, while SF12 cells beyond about 50 nodes are limited by the gateway's acknowledgement duty cycle. The per-node claims are scoped accordingly.

## Mandatory experiments (§6)
E1 = C1; E2 = C2; E3 = C3; E4 = C4; E5 = C7; E6 = C5; E8 = C8.
- **E7** Back-off cap and batch period swept (Sec. V-D): probing every slot costs 2.2× (SF7) and 3.7× (NB-IoT) the energy of K = 6 h; K 6 → 24 h saves 12% more while the 90th-percentile recovery latency triples.
- **E9** Chain-blocked bootstrap for the reconstruction results (e.g. 31% of day-long gaps within tolerance, 95% CI 18–49%); site-bootstrap CIs for every design statistic (both years).
- **E10** Injected events compared with real 3-h excursions at the same sites: 5σ events occur naturally at 60–100% of sites depending on the parameter; 99.7% of the 2024 injected events are physically plausible, and the latency hypotheses also pass on plausible events alone.

## Methodological comments (§7)
- **M1** Absolute goodness of fit added (bootstrap KS, B = 200, refitted): the geometric model is rejected on every record (p ≤ 0.005); on the large records every model is rejected, but the geometric misfit is an order of magnitude larger (D = 0.48 vs 0.027 InWaterSense; 0.26 vs 0.008 UVA); on Weija the lognormal and power law are not rejected. Rankings unchanged without the longest gap. Censoring: gap lengths are uncensored by construction. Wording changed to "strongly unsupported relative to the alternatives; no tested model fits the larger records exactly" (Sec. IV-B).
- **M2** The rejected process is defined exactly: a single loss state (Bernoulli and Gilbert–Elliott both give geometric gap lengths) (Sec. III-D).
- **M3** Frame-counter handling documented and tested (Sec. III-A): no counter reuse on UVA, one decrease, constant cadence; threshold sensitivity 2% (UVA), 10.0% vs 10.9% loss (LoED).
- **M4** UVA bins of 5–30 min: availability 98.7% throughout; long-outage down-time share 82–84%; system share of missing frames 28.0–28.6% (Sec. IV-C).
- **M5** = E7.
- **M6** Lifetimes are now illustrative; ratios are primary (Sec. III-E).
- **M7** Checked against the specification texts: the 8 transmissions with data-rate stepping are LoRaWAN 1.0.2 §18.4; LoRaWAN 1.0.4 uses NbTrans (1–15, default 1) without stepping. Both evaluated (6.8× vs 7.3× at SF7).
- **M8** NB-IoT stack stated: UDP datagrams to an echo server, 512 B maximum, RAI, normal coverage; the echo is the application-level acknowledgement.
- **M9** = E9.
- **M10** Development (2023) and confirmatory (2024) phases separated; preregistration language removed; the plans are described as kept with the code and hashed, not publicly registered. Table V now labels each hypothesis by when it was written and reports development and held-out verdicts side by side.
- **M11** All-event metric "server knows within 1/6/24 h" over all injected events reported for both years (Sec. VII-C).
- **M12** = E10.
- **M13** Spatial structure per pair added (distance 2.8–300 km; drainage-area order). Finding: selected lags do not follow the flow (downstream neighbours get positive lags as often as upstream ones), so the neighbour signal is mostly shared forcing. Text in Sec. VI-B.
- **M14** Tolerances related to USGS accuracy ratings (Wagner et al. 2006, Table 18) and natural variability (Sec. III-F): L2 lies at or inside "excellent" for every parameter.
- **M15** Release package prepared (`release/`): lock files, checksums, seeds, acquisition scripts, the frozen plan and hashes, and the derived Weija delivery trace. The authors archive it and insert the DOI.

## Literature (§10)
Added and verified against the registry: Arnaiz et al. 2024 (Integration), Jing et al. 2024 (CIKM, CASPER), SAITS, ImputeFormer, StemGNN, DaRe (LoRaWAN coding). "He et al. 2025, Electronics Letters" could not be found in any index; the closest real work (Qian et al. 2024, dense spatio-temporal transformer, Math. Biosci. Eng.) was not cited for lack of a direct role. No peer-reviewed LoRaWAN post-outage buffering study was found; the closest practice (gateway-side caching) is discussed through the deployment literature. Reference [12] (arXiv-only HARQ paper) is replaced by the peer-reviewed Huang et al., IEEE TWC 2020.

## Presentation (§11)
- Terms defined once and used consistently, including "reading" = one four-parameter sampling cycle (Sec. III).
- Assumptions table added (measured / inferred / assumed, and how each assumption is tested).
- Contributions reorganised into the review's three-part chain; novelty paragraph added.
- Abstract rewritten (250 words, fewer numbers, scoped claims). Fig. 4 rebuilt from 2024 data on one vertical scale. Single-column, double-spaced, 12-pt review copy generated from the same source by the build (currently 45 pages; condensation to the 30-page review limit and 10 published pages is the next step, as agreed). PENDING: dataset access dates (to be set at submission).

## Defect found during the revision
- D5: a floating-point tie at the tolerance (pH and T are recorded in 0.1 steps) counted errors of exactly one tolerance in or out at random in the main picture scores and the trigger. Fixed with one inclusive comparison, tested, recorded in `docs/DESIGN_EVAL_PLAN.md`, all affected runs repeated; the paper reports the corrected values.
