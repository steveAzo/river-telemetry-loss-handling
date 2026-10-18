# Revision plan against the Q1 review (started 2026-10-17)

Source: `Q1_Journal_Review_Report.docx` (16 Oct 2026; strict pre-submission review for IEEE TGCN).
Decisions by the user (2026-10-17): target **IEEE TGCN**; title **"Outage-Aware Reporting and Loss Recovery for Energy-Efficient River Water-Quality Telemetry over LPWANs"**; **no hardware is available**; add GRIN + SAITS deep baselines; a derived Weija delivery trace (timestamps only) may be published. Condensation to 10 pages comes **after** every other fix.

Working rules (unchanged from the project): every number in the draft comes from `src/paper/paper_numbers.py`; every new code path gets a test; every correction is disclosed; new defaults must reproduce the stored v0.1 results exactly (regression tests) unless a change is intended and recorded.

Status key: TODO, DOING, DONE, PARTIAL (what is missing is stated), CANNOT (with the substitute).

---

## Order of work, and why

1. **Freeze the confirmatory plan first** (C3/E3). The held-out 2024 data must not be analysed before the design, thresholds, rules and code are frozen. Disclosure: on 2026-10-17 a two-day connectivity test (2024-03-01..02, site 01427510) was fetched to check that the USGS service still serves 2024 approved data; it was printed (first value of each series) and not analysed.
2. **Analyses on existing data** that may change wording but not the frozen design: C1 (gap causality), M1–M4, M13, M14, E10.
3. **Simulator extensions**, each off by default, each with a regression test: C2, C5/E6, C1 node-off sensitivity, C6, E7, M7, energy-uncertainty propagation (C7 substitute).
4. **Confirmatory run** on 2024 (E3), plus M11 on both years.
5. **Reconstruction**: E9 blocked bootstrap, M13, E4 deep baselines.
6. **Network scale** (C8/E8).
7. **Rewrite**: title, abstract, contributions, related work (+ table, new literature), assumptions table, terminology, claim-level wording (review §9), Fig. 4 scales, Table V phases, discussion, data/code availability.
8. **Formatting**: TGCN single-column review copy; then (separately, later) condensation to 10 pages.

---

## Critical issues (review §5)

| ID | Issue | Action | Status |
|---|---|---|---|
| C1 / E1 | Missing readings treated as communication outages without ground truth | (a) **Weija:** use the other parameter streams of the same node: a conductivity slot in which another stream delivered is a sensor/processing gap with the link up, not a delivery outage. Rebuild the Weija link record as *node-silent* slots and report how much of the conductivity loss was node-silent. (b) **InWaterSense:** node 1 and node 2 share one gateway and one GPRS link. In node 2's active window, classify node-1 gaps as *shared-path silent* (both nodes silent: gateway, GPRS, server or site power) vs *node-1-only* (node 2 delivered: node power, sensor or node radio). (c) **Terminology:** "delivery gap" for the two water-quality records; "system outage" only where verified (UVA all-sensor silence; LoED gateway silence). (d) **Sensitivity:** a share f ∈ {0, 10, 25, 50}% of long gaps (≥ 6 h) are node-off (no reading generated, no radio energy); report recovery of *expected* readings as an upper bound and ARQ/buffer energy. Buffering recovery stated as conditional on generation. | DONE (analysis); text in Secs. III-C, V-C |
| C2 / E2 | ARQ replay structurally pessimistic (whole slot down) | Model retry instants explicitly (ACK time-out, duty cycle, DR stepping). Three link-timing models: (i) full-slot down (current, pessimistic bound); (ii) each gap's restoration uniform between the last missing and the next delivered transmission instant; (iii) short gaps (≤ 1 h) treated as radio-loss bursts, retries failing with LoED's conditional loss probability (optimistic bound for ARQ). Report ARQ recovery and energy under all three; reword "recovers none" as a bounded statement. | DONE; text Sec. V-A |
| C3 / E3 | H5–H10 not independently validated | Held-out **2024** data, same candidate sites, same eligibility rule; design, thresholds, rules and code frozen in `docs/CONFIRMATORY_PLAN.md` (with SHA-256 of the code) **before** any 2024 file is downloaded for analysis. 2023 results become development evidence. | DONE: 2024 held-out (33 sites), every primary hypothesis passes; 2023 rerun with D4/D5 |
| C4 / E4 | "Reconstruction cannot replace delivery" too broad | Add **GRIN** (graph) and **SAITS** (transformer), trained per chain on the first 20% + non-gap data, evaluated on the identical gap protocol (bridging: non-causal; real-time: future masked). Narrow every claim to "the evaluated estimators, including two contemporary deep imputers". | DONE: SAITS + StemGNN (first config discarded: global normalisation); claims limited to evaluated estimators |
| C5 / E6 | "Buffering delivers every reading" relies on ideal storage | Finite buffer sweep (RAM-class 2/8/64 KB, flash/SD), flash write/read energy from a datasheet, drain-rate limit with live readings interleaved. Report max occupancy, dropped readings, backlog clearance time, live-reading delay. Reword as conditional. | DONE; text Sec. V-C |
| C6 | Node cannot know the application server's state from a MAC ACK | Define the ACK boundary: LoRaWAN confirmed-uplink ACK = network server; NB-IoT (UDP + application reply as measured) = application server. Add an end-to-end variant for LoRaWAN: a reading counts as "shown" only once an application-level cumulative ACK arrives in the downlink of a later uplink; simulate its energy and picture. Align with the outage taxonomy. | DONE: application-ACK variant +3-18% energy, bound kept; Sec. VII-H |
| C7 / E5 | No hardware validation | **CANNOT measure (no hardware).** Substitute: (a) cross-check the energy model against independent published measurements not used for its parameters; (b) Monte-Carlo propagation of energy-parameter uncertainty into every headline ratio and ordering; (c) state plainly that results are model-based; hardware is future work. Claims reworded to relative energy under a stated model. | CANNOT measure (no hardware); substitute DONE: independent-measurement check + Monte Carlo, claims scoped |
| C8 / E8 | Multi-node contention after recovery | Discrete-event LoRaWAN multi-node model (pure-ALOHA collisions per SF/channel with capture, gateway half-duplex, RX1/RX2 downlink duty cycles, node duty cycle): N nodes, outage duration, backlog, SF mix, recovery jitter. Report PDR, clearance time, collision rate, downlink utilisation, node energy. Validate against the ALOHA throughput formula (test). | DONE; text Sec. V-E, Table netsim |

## Mandatory experiments (review §6) not covered above

| ID | Action | Status |
|---|---|---|
| E7 / M5 | Sweep back-off cap K ∈ {1, 2, 3, 6, 12, 24} h and batch period ∈ {15 min, 30 min, 1 h, 2 h, 3 h, 6 h} on the development data; Pareto curves (energy, within-1-h share, latency after outages), per radio. Rationale for K = 6 h. | DONE (records); text Sec. V-D |
| E9 / M9 | Reconstruction: chain-blocked bootstrap (resample chains, then sites). Design: site-level bootstrap 95% CIs and paired effect sizes for energy, picture and latency differences. | DONE (reconstruction chain-blocked; design site-bootstrap, both years) |
| E10 / M12 | Share of injected values outside plausible ranges; compare κσ with real sharp 3-h excursions in the USGS records (calibration of the event family). Constrain injections in the confirmatory plan if needed. | DONE (calibration; 99.7% plausible; latency verdicts hold on plausible events) |

## Methodological comments (review §7)

| ID | Action | Status |
|---|---|---|
| M1 | Survival plots (empirical vs fitted), discrete KS with parametric bootstrap per model, bootstrap parameter CIs, censored first/last runs. Reword to "strongly unsupported relative to the tested alternatives" unless a formal test rejects. | DONE (bootstrap KS; Sec. IV-B) |
| M2 | Define the rejected process exactly: geometric outage lengths (one down state; Gilbert / Gilbert–Elliott sojourn) vs i.i.d. Bernoulli; avoid "memoryless loss" as shorthand. | DONE; text Sec. III-D |
| M3 | Document and quantify frame-counter handling in LoED/UVA: resets/rollover, rejoins, multi-gateway duplicates, retransmitted frames, address reuse, cadence changes; sensitivity of loss to the reset threshold. | DONE; text Sec. III-A |
| M4 | UVA system-outage rule at 5, 15, 30 min bins (besides 10). | DONE; text Sec. IV-C |
| M6 | Relative energy primary; lifetimes secondary/illustrative. | DONE |
| M7 | Verify retry count and DR stepping against the LoRaWAN specification text; state the version; add a sensitivity without DR stepping. | DONE: verified in LoRaWAN 1.0.2 Sec. 18.4 and L2 1.0.4; both evaluated |
| M8 | State NB-IoT stack: UDP socket, 512 B max datagram (N211), application reply as ACK, RAI, coverage class assumed; check against Michelinakis et al. | DONE; text Sec. III-E |
| M10 | Present development (H1–H4), post-hoc development (H5–H10 on 2023) and confirmatory (2024) phases; drop preregistration-like language. | DONE |
| M11 | Unconditional P(server knows event within 1/6/24 h) over all injected events, both years. | DONE |
| M13 | Site table: coordinates, distance, drainage area, upstream/downstream order, selected lag and correlation per pair. | DONE; Sec. VI-B |
| M14 | Tolerance table in physical units at representative sites, against USGS accuracy ratings and natural diel variability; justify EC as % of median. | DONE; text Sec. III-F |
| M15 | Release package: code, lock file, seeds, data-acquisition scripts, checksums, derived traces (Weija delivery timestamps allowed). User uploads. | DONE |

## Presentation (review §3, §8–§12)

| Item | Status |
|---|---|
| New title (no question mark) | DONE |
| Abstract: fewer numbers; delivery gaps vs verified outages; scoped reconstruction claim | DONE |
| Novelty paragraph (evidence-to-design pipeline); 3 contributions (review §12) | DONE |
| Related work: 2024–2026 imputation, adaptive monitoring (Arnaiz 2024), LoRaWAN buffering/prioritisation; synthesis table | DONE |
| Assumptions table: measured / inferred / assumed | DONE |
| Consistent terms: delivery gap, system outage, gateway outage, radio loss; "reading" defined | DONE |
| Claim-level wording (review §9, six claims) | DONE |
| Fig. 4: common scale or explicit in-panel note | DONE |
| Table V: development / post-hoc / confirmatory labels | DONE |
| Ref. [12] arXiv: check for a peer-reviewed version | DONE |
| Dataset access dates and software versions | TODO (at submission) |
| Remove draft banner; TGCN single-column review layout | DONE (review copy 25 pages) |

## Condensation (2026-10-17, after all fixes)

- Main paper 10 pages (two-column, including references): sections rewritten tightly; every claim kept, details moved verbatim to `draft/supplement.tex` (6 pages: Secs. S1-S6, Tables S1-S5, Figs. S1-S3, Eqs. S1-S12), referenced from the paper through `xr-hyper`.
- TGCN review copy (single column, double spaced, 12 pt) 25 pages, within the 30-page limit.
- Grammar and consistency pass on both documents (outage vs delivery gap; double negatives; sentence-initial numerals; missing multiplication signs; reference-title capitals).
- Mechanical audit: equations (1)-(7), Tables I-VII, Figs. 1-2 and Algorithm 1 all cited and numbered in order of first citation; every reference into the supplement resolves; the checker now also fails on LaTeX commands that lost their backslash.
