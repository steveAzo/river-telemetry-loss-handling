# Paper 2 rescoping after two novelty rejections (2026-10-31)

Status: proposal for discussion with the Prof. Nothing below has been run yet. Every claim about prior work in Section 5 is from memory and must be verified against the PDFs before it is used.

## 1. What happened

- IEEE TGCN: rejected for novelty and scientific contribution.
- Ad Hoc Networks (Elsevier): desk-declined. In scope, but "lack of sufficient novelty". The editor attached three papers as examples. They are now in `papers/editor_examples/`.
- The submitted manuscript and the Prof's automated analysis (Q1_Novelty_Enhancement_Strategy) are in `submissions/2026-10_AdHocNetworks/` (gitignored). The old Q1 review report was deleted as superseded.

## 2. What the three example papers do

| Paper | Problem | Model | Proposed mechanism | Evaluation | Hardware |
|---|---|---|---|---|---|
| Martinez-Sanchez 2025 (Ad Hoc Netw.) | Too many uplinks in sensor networks | Formal model of transmission, persistence, evaluation and error | Send-on-Delta whose threshold the sink adapts from Bollinger bands over the whole network | 5 ESP32 nodes for 24 h, simulated scale-up to 40 nodes (noise added to real traces), compared post hoc with SoA and PSoD | Minimal (5 nodes, 1 day) |
| Yang 2026 (Ad Hoc Netw.) | Energy efficiency in multi-gateway LoRa | Analytical PDR model (co-SF and inter-SF interference, capture, duty cycle), validated against simulation, then an EE optimisation problem | Q-learning SF allocation with a spatial-interference penalty in the reward | Simulation only, up to 5,000 nodes and 6 gateways, compared with EF-LoRa and plain Q-learning | None |
| Ferhi 2025 (Phys. Commun.) | ACK overload in ultra-dense LoRaWAN | ACK probability as a learned function p_ACK = f(x) | Online logistic regression at the network server that decides per uplink whether to send an ACK | LoRaWANSim (MATLAB), 10 to 3,000 nodes, compared with always-ACK | None |

## 3. Diagnosis: the difference is the type of contribution, not the rigour

- Each example paper contributes one named mechanism, and the paper is built around it: problem, model, mechanism, comparison with baselines, one headline gain (89% fewer packets, more than 19% higher EE, UDR 54% vs 32%).
- Our manuscript states the opposite in its introduction: "The contribution of this study is not a new retransmission or prediction primitive." Its design (hourly batching, immediate alarms, a bounded-error trigger, buffering with back-off) is a combination of named, established tools. For a networking journal it reads as a careful evaluation study, which editors treat as incremental.
- Our rigour is higher than all three: four real records, bootstrap goodness-of-fit, rules frozen before a held-out year, deep baselines. Rigour does not substitute for a new mechanism.
- Two of the three papers use no hardware, and the third uses five ESP32 boards for one day. Hardware is not what separates them from us. A formal model plus a mechanism plus fair simulation or trace-driven evaluation is accepted.
- Our findings are spread over four research questions with many numbers. Theirs give one problem and one answer.

## 4. Assets we keep

- The measured loss structure: two regimes, a heavy-tailed gap-duration distribution with the geometric (memoryless) model rejected, InWaterSense 1,619 gaps, UVA 36,519 loss runs, and long gaps that are mostly shared-cause (about 74% at InWaterSense).
- The trace-driven LoRaWAN and NB-IoT energy model, the held-out protocol (freeze, hash, test), and the dual-prediction mirror of the server's estimate.
- The v0.3 design as the strong baseline any new mechanism must beat.

## 5. Candidate scopes

### S1 (recommended): value-aware, hazard-driven outage recovery

Core observation: the gap process is not memoryless. The probability that an outage ends in the next interval depends on how long the node has been silent (the hazard of the gap-duration distribution). The node also mirrors the server's estimate (dual prediction), so during an outage it knows exactly how wrong the server's picture currently is and whether an alarm is waiting. Under outage, the cost of staying silent is therefore observable at the node rather than assumed.

Mechanism (one decision rule, two parts):

- Part 1, probing: schedule reconnection probes from the measured gap-survival function, weighted by the observed cost of silence (server-estimate error, pending alarms, buffer fill). This replaces a fixed or exponential back-off with a rule derived from data and content.
- Part 2, post-outage drain: when a shared outage ends, nodes with identical schedules probe at the same moment. Desynchronise them and order the drain by value (the node and readings that most reduce the server's error go first), under the duty-cycle and ACK (downlink) budget.

Analytical contribution to attempt: a cost model (probe energy plus delay cost that grows with the observed error) and a structural result. Example: under a decreasing hazard, the optimal probe interval is non-decreasing in elapsed silence and non-increasing in observed error. Also a bound on the gap to an oracle that knows when the outage ends.

Evaluation: trace replay on the four records, single-node and multi-node (10 to 500 nodes, shared outages, SF7 to SF12, ACK capacity). Baselines: v0.3, exponential back-off, the back-off the LoRaWAN and NB-IoT specifications already define, a content-blind hazard schedule (ablation), and the oracle. Rules frozen before the confirmatory run, as before.

Why it can be new: it couples three things that the literature, as far as we know, treats separately: the measured non-memoryless gap process, node-side knowledge of the server's error, and post-outage contention. It also turns our RQ1 finding (memoryless rejected) from an observation into the foundation of a method.

### S2: the full OARS scheduler from the strategy document

S2 is a POMDP-style scheduler over every action (send, batch, defer, retry, probe, backfill). It is too broad for a defensible analytical result, and the document itself warns that combining existing features is not a contribution. S1 is a focused, provable subset of it.

### S3 (fallback): the evidence paper elsewhere

Submit the current study as a measurement and evaluation article to a journal that values empirical characterisation. This carries the lowest risk but does not answer the novelty criticism. Keep it only if S1 fails its gates.

## 6. Risks to settle before committing (go/no-go)

- G1, prior art (literature audit). Classical optimal checking and inspection schedules (the Barlow, Hunter and Proschan line, early 1960s) solve the single-node, content-blind version of Part 1. Adaptive contact probing in delay-tolerant networks (Wang et al., around 2007 to 2009) probes for contacts using contact statistics. The LoRaWAN and NB-IoT specifications define their own retry and back-off timers. The novelty must lie in the coupling (observable value, shared outages, LPWAN constraints), not in the hazard schedule alone. Verify every one of these against the papers. Stop if the coupled rule already exists.
- G2, headroom (existing code, no new method). Compare v0.3's back-off with an oracle that probes exactly when the outage ends, on energy, time to server consistency, and unconditional alarm latency, for LoRaWAN and NB-IoT. v0.3 found that buffering with back-off costs close to nothing in energy on LoRaWAN, so the headroom may be in delay and freshness, in NB-IoT (expensive attach), and in multi-node drain. If v0.3 is already within a few percent of the oracle everywhere, S1 is dead and a different mechanism is needed.
- G3, simplest competitor. Before claiming anything, test whether v0.3 with tuned back-off plus random jitter matches S1. If it does, the novelty is not demonstrated.

## 7. Gate results (2026-11-01)

### G2, headroom of Part 1 (probing schedule): FAILED

Script: `src/rescoping/headroom.py`; outputs `results/rescoping/headroom_{frontier,summary}.csv`. Every real gap is replayed as the v0.3 design notices it (at the next hourly upload), and v0.3's back-off (6-h cap) is compared with the exact optimal schedule (dynamic programming, the Barlow-Hunter-Proschan checking problem on the record's own gap distribution).

- In-sample (fitted and scored on the same gaps, optimistic): the optimum halves v0.3's failed probes on InWaterSense (2.6 vs 5.0 per day at the same 0.5-h delay).
- Out of sample (fitted on half the gaps, scored on the other half, 20 splits): the raw empirical optimum is worse than v0.3 (it overfits holes in the distribution; readings-weighted delay 16-22 h vs 2.6 h). A lognormal fitted on the training half, which a node could carry, saves at the same delay only 1.4-2.9% of the design's daily energy on LoRaWAN (InWaterSense, the most outage-heavy record), 0.4-1.1% on Weija, about 0 on UVA, and at most 9% on NB-IoT (InWaterSense), which rests on the unmeasured 10-s cell-search time. The delay gain is about 8 minutes, under an hourly batching design.
- Conclusion: exponential back-off with a cap is already close to optimal for these heavy-tailed gaps. Hazard-driven or value-aware probing would be a mediocre contribution. Dropped. (v0.3 already probes at once on an alarm, so the value-aware part adds little.)

### G1, prior art (searches 2026-11-01; claims from abstracts unless a PDF is listed in papers/)

- Part 1 neighbours: optimal checking (Barlow, Hunter and Proschan, SIAM J. 1963); DTN contact probing STAR (Wang, Motani and Srinivasan, IEEE/ACM ToN 2009, adapts to contact history and time of day); AoI-driven channel probing with threshold policies (e.g., arXiv 2201.02787, 2010.07626); remote estimation over Gilbert-Elliott channels with error-threshold policies (mature); semi-Markov channels studied for stability (arXiv 2203.16826) and a "wearing channel" SMDP (arXiv 2501.17473). Moot now that G2 failed.
- Part 2 neighbours (many nodes recovering after a shared outage):
  - Burst-MAC (Jain, Haque, Saifullah and Zhang, RTSS 2024; papers/pdf/60): detects a burst, then hash-based TDMA within channel/SF groups, ACK piggybacking; hardware plus NS-3. The strongest baseline for any drain mechanism.
  - Group or aggregated ACKs: DG-LoRa (Sensors 2021), multi-user ACK aggregation (2019), Ferhi (PhysCom 2025; ITL 2025).
  - Server-assigned slots: Haxhibeqiri et al. (IEEE IoT-J 2018) and time-slotted LoRa MACs.
  - Application-layer erasure coding: DaRe (Marcelis et al., IoTDI 2017; papers/pdf/61).
  - Event-burst scheduling: adaptive spatial scheduling (Sensors 2024).
  - Confirmed-traffic collapse through downlink starvation: studied in steady state (several papers; a recent multi-gateway analytical framework).
  - ALOHA bistability: Carleial and Hellman (IEEE TCOM 1975); limiting retries to at most 8 makes slotted ALOHA monostable (Sakakibara et al.).
  - Metastable failures in distributed systems: Bronson et al. (HotOS 2021), Huang et al. (OSDI 2022) (papers/pdf/65, 66).
  - Not found: an analysis of the post-outage transient in an LPWAN cell (every node starting with a large backlog), whether the cell escapes it, or how measured outage durations set that risk. Vendor guides name the "recovery burst" as a known operational risk.
- Consequence: every Part 2 mechanism ingredient (grants, group ACKs, coding, summary-first) exists. A mechanism alone would again be "a combination of known tools". A defensible contribution must lead with the analysis.

### Revised candidate S1' (for discussion, not yet gated)

Post-outage recovery of an LPWAN cell as a bistability problem:

- Model: post-outage drain of N duty-cycled Class A nodes through a half-duplex gateway with a downlink duty cycle; find the recovery capacity (largest backlog x cell size from which the cell returns to the good equilibrium), validated against simulation (as Yang 2026 validates its PDR model). Our own v0.3 network simulation already shows both failure modes: livelock without jitter, and SF12 backfill not finishing within 72 h beyond about 50 nodes after a 1-day outage.
- Data: with the measured heavy-tailed, mostly shared outages, the probability per outage that a cell enters the bad state, and the carry-over of backlog into the next outage.
- Mechanism: a recovery rule proven to remove the bad equilibrium up to the capacity bound, compared with LoRaWAN, v0.3 jitter, Burst-MAC and group ACKs.
- Open gates: (G1') read Burst-MAC, the confirmed-traffic analytical papers and the ALOHA stability lineage in full; (G2') reproduce the netsim failure regimes and check whether Burst-MAC alone already removes them. If it does, S1' is dead too.

### G1' for S1' (2026-11-03, full texts read): FAILED as a mechanism paper

Papers read: 60 Burst-MAC, 68 Hoang 2026, 69 Capuzzo 2018, 70 Haxhibeqiri 2019, 71 Carleial 1975, 72 Zorbas 2024, 73 Asteriou 2024, 74 DG-LoRa, 75 FREE (the 2019 multi-user ACK-aggregation paper was not obtained; DG-LoRa and Ferhi cover group ACKs).

- FREE (Abdelfadeel, Zorbas, Cionca and Pesch, IEEE IoT-J 2020; papers/pdf/75) already buffers data at end devices and drains it in bulk through gateway-computed, collision-free schedules (SF, channel, power, slots) under the EU868 duty cycle, with grouped ACKs and near-100% delivery. It names the same cause of confirmed-traffic failure (the gateway's duty cycle limits the ACKs it can send). Zorbas et al. (WF-IoT 2019) give offline schedulers for the same bulk transfer. A post-outage drain mechanism would be FREE invoked after an outage.
- Burst-MAC (RTSS 2024) assumes US FCC rules (no duty cycle, 64 channels), disables ACKs after the first rounds (80-85% PRR) and detects bursts from the packet-generation rate. It is not a solution for duty-cycled, complete backfill, but FREE is.
- Hoang 2026 (OJCOMS) models the confirmed-traffic "vicious cycle" but as a steady-state fixed point (iterated to one solution); its "flash crowd" is stationary extra load. Capuzzo 2018 and Khan 2019 are also steady-state. The post-outage transient (initial backlog, possible second equilibrium) is not analysed in any paper read.
- Verdict: the mechanism space is saturated (FREE, Burst-MAC, Haxhibeqiri, DG-LoRa, DaRe). What remains open is an analysis of the post-outage transient in standard LoRaWAN, whose practical message would be "use existing scheduled collection after outages". That repeats the rejected pattern (evaluation of known remedies). S1' is not recommended.

### Screens of 2026-11-03 (after the G1' failure)

The user asked for one seed at a time; silence ambiguity was chosen first (it stays in the river-telemetry domain and the editor's Send-on-Delta example sits in it).

- Seed (a), silence ambiguity: FAILED G1.
  - BaySail (Silberstein, Puggioni, Gelfand, Munagala and Yang, VLDB 2007; papers/pdf/76) states the problem exactly ("a non-report may either be a suppression or a failure") for value-based temporal suppression, adds application-level redundancy (counters, last-r transmission timestamps, direction bits) and resolves it by Bayesian inference; it finds this beats retransmission. LoRaWAN's frame counter is their counter scheme for free.
  - Control theory covers the same ambiguity for event-triggered estimators over lossy channels (e.g. Han et al., arXiv 1810.03310; GMM and particle-filter estimators; time-triggered heartbeats to detect loss).
  - Left open: bursty heavy-tailed outages (BaySail simulates failures at a rate on an AR(1) soil-moisture model) and online use. Both are extensions of a known framework, the pattern that was rejected.
- Seed (b), fleet-level outage diagnosis: FAILED G1 on substance, not on prior art alone.
  - Gateway and backhaul outages are directly observable to the network operator (gateway status messages reach the network server), so inferring them is only needed by application owners without network-server access.
  - The remaining problem (node fault vs radio path) is sink-side passive diagnosis, an established WSN field (Sympathy, SenSys 2005; PAD, Liu et al., IEEE TPDS 2010; survey Mehmood et al., Sensors 2018). A 2026 Internet of Things (Elsevier) paper, "From telemetry to network diagnostics: Supporting operators in massive IoT over LoRaWAN" (S2542660526001095, not read: paywalled), builds operator diagnostics from network-server telemetry, including frame-counter loss.
  - No labelled root causes exist in LoED or UVA, so validation would rest on synthetic fault injection.
- S4, post-outage metastability (reframing of the netsim failure regimes as a metastable failure in the sense of Bronson et al. 2021): FAILED G2 (src/rescoping/metastable_probe.py; results/rescoping/metastable_probe*.log).
  - Hypothesis: a cell stable under normal load is pushed by a shared outage into a persistent collapse (a second equilibrium the steady-state models of Hoang 2026 and Magrin et al. would miss, since they iterate to one fixed point).
  - Test: netsim's model unchanged, SF12, 1-h jitter, horizon 10-14 days, hourly backlog; control = the same cell with a 15-min trigger instead of a 24-h or 72-h outage; N = 25-200, two seeds for N = 120-180.
  - Result: one attractor per cell size, no hysteresis. N <= 50: control and outage runs both return to normal (backlog about 1 reading per node). N = 100-140: both settle into the same degraded state (e.g. N = 120: about 2,700-3,900 readings after 14 days for all three triggers); the outage only lengthens the approach (about a week at N = 100). N >= 160: both diverge; the cell is overloaded without any outage.
  - The degradation is the steady-state downlink (ACK) limit Hoang 2026 already describes. The earlier netsim statement ("backfill after a 1-day outage does not complete within 72 h beyond about 50 nodes") is a slow approach to that single equilibrium, not a trapped state.
- Assumption audit, first pass (2026-11-03, later). Candidate list: OpenAlex title search 2024-2026 restricted to Q1 networking venues (295 papers; the closest to our theme are CADD, Elsevier IoT 2026; Bisio et al., IoT-J 2026, compressive-sensing energy-accuracy frontier; Iloridou and Pavlidou, TMC 2025, buffered NB-IoT devices; Yang 2026 and Hoang 2026, multi-gateway). Screened and closed:
  - Outage-triggered ADR backoff (a long shared outage drives the fleet to SF12): Finnegan et al. (IEEE IoT-J 2020) already analyse ADR backoff, slow and gateway-duty-cycle-limited mass re-convergence, and a TTN case where SF12 nodes without downlink data are never moved back; Casals et al. (Sensors 2021, "SF12 well") cover congestion-driven SF12 drift. The remedy is a knob LoRaWAN 1.1 already exposes (ADR_ACK_LIMIT/DELAY), and a rough capacity count gives a transient of hours, not a trap.
  - River-aware dual prediction: v0.3's estimator already adds yesterday's same-time change (src/design/sitedata.py, server_picture); a better predictor is another DPS variant.
  - Gateway-outage-resilient SF allocation (multi-gateway papers assume gateways are always on). UVA (489 d, 3 gateways) shows gateway-specific outages far exceed shared ones (A: 7 runs >= 6 h, 298 h; C: one run of 716 h; shared: 150 h). Prior art: m-gateway connectivity (Yu, Xu, Cherkasova and Rosing, CNSM 2021). Decisive check: during every gateway-specific outage, including the 30-day one, sensors delivered about as many frames as in the equal period before; natural macro-diversity absorbed the outages, except one edge sensor (sensor09, 30-55% fewer frames while gateway A was down). Headroom limited to edge nodes.
  - Coordinated Send-on-Delta thresholds under a shared budget (the editor's Ad Hoc Networks example's core novelty, and its stated future work): deadband allocation under a network traffic constraint is in Otanez, Moyne and Tilbury (ACC 2002).
- S5, cost side (2026-11-03, src/rescoping/sensing_headroom.py; results/rescoping/sensing_headroom.{csv,log}):
  - Where the energy goes (src/energy/model.py, 96 samples and 24 hourly batches per day): the radio is 5-45% of a node's daily energy; sensing is 40-89% once probes need >= 5 s awake per sample (LoRaWAN SF7: 49% at 5 s, 75% at 15 s). Every delivery-side mechanism, ours and the competitors', works on the minority share.
  - Headroom for waking the slow probes (DO, pH) less often, 24 USGS 2023 sites with all four parameters, server holds the last sample, v0.3 tolerances (medians): fixed every slot 96/day, 0% of slots out of tolerance; every 2 slots 48/day, 2.4%; hourly 24/day, 9.4%; oracle 14.2/day, 0%. Large in principle (3-7x).
  - No causal cue reaches it: self-adaptive sampling on the probe's own change (Alippi-style) and gating on the cheap probes (T, EC) are no better than fixed at equal rate (gated about 24/day at 12.6%); a per-hour schedule learned from the previous 14 days gives 49/day at 1.6% vs fixed 48/day at 2.4%. Oracle samples are spread over the day (busiest 6 h hold 37%, uniform 25%).
  - Part of the oracle gap is sensor noise: pH is reported in 0.1 steps (= tolerance) and a median 27% of pH changes reverse in the next slot; DO moves by more than its tolerance between consecutive slots in a median 4.6% of slots (up to 27%).
  - Prior art for adaptive sampling of energy-hungry sensors is extensive (Alippi et al., IEEE TIM 2010; Kho, Rogers and Jennings, ACM TOSN 2009, periodic Gaussian-process models). S5 closed.
- Survey pass (2026-11-03): open-issue sections of Jouhari et al. (IEEE COMST 2023, papers/pdf/77) and Krekovic et al. (Elsevier IoT 2025, papers/pdf/79) are generic (resource management, multi-hop, carrier sensing, edge AI); the one recurring direction usable with our data is goal-oriented communication.
- S6, goal-oriented sensing (src/rescoping/goal_headroom.py; results/rescoping/goal_headroom.{csv,log}): the server must know whether DO < 5 mg/L, pH < 6.5 or pH > 9 at every slot; 37 USGS 2023 sites. Degenerate: at the median site no threshold is crossed (oracle median 0.05 samples/day; 4% of readings near a threshold); fixed once-daily sampling already misses a median 0.08% of slots (max 11%, concentrated at a few sites); a causal distance-to-threshold rule (learned rate bound) used 21-30 samples/day, partly from its 30-day warm-up, and did not beat a per-site fixed rate. Prior art: TEEN (2001), threshold queries in sensor databases, self-triggered control, age-of-incorrect-information threshold policies. Closed.
- Open-problem pass (2026-11-03, papers/pdf/83-96, supplied by the user; conclusions and future-work sections read):
  - Research papers: stated gaps are generic mechanism extensions. CADD (83): multi-gateway, adaptive SF, real hardware, "an explicit analysis of packet loss effects on data fidelity", faster or irregular data. Bisio et al. (84): delivery of information not accounted for in the compressive-sensing frontier. Bankov et al. (85): analytical NB-Fi ACK/retry configuration. Suman et al. (86), Mavros et al. (87), Iloridou and Pavlidou (88), Fan et al. (89), Bouazizi et al. (90): MAC, relay, random-access and SF-adaptation extensions. Zorbas et al. (96): "plenty of other SF configurations, including suboptimal approaches from the literature, can lead to a very similar performance" (a flat optimum, as in our screens). Casalbore et al. (95): operator diagnostics from network-server telemetry (closes seed b further).
  - Surveys: Alahmadi et al. (91): congestion-driven switching from ALOHA to scheduled access, downlink compression, gateway placement, distributed parameter configuration, slicing, and "most of the already proposed works in the literature assume ideal environments in terms of the interference and the propagation model". Maurya et al. (92): ML for ADR and resource allocation, security.
  - Water-quality reviews (93, 94): nitrogen and phosphorus rarely measured (ML surrogates from cheap parameters), reliance on batteries without energy harvesting, choice of sampling frequency, coverage gaps causing data loss and delay.
  - Verdict: no stated open problem gives us an asset edge. The network-mechanism gaps are simulation problems anyone can attack; the loss-and-fidelity gaps are BaySail and v0.3 territory; the domain gaps (surrogates, harvesting) are not networking contributions or have long prior art (energy-neutral operation, Kansal et al. 2007).
- Bounds-paper proposal (2026-11-03): oracle bounds across mechanism classes as the contribution, with a constructive core (what information captures the sensing oracle gap). Crowding check: no oracle-bound headroom study of LPWAN or sensor-network protocols on real traces found (closest: an analytical TLS-over-LoRaWAN ceiling; a downlink trace-replay thesis); learned adaptive sampling of water-quality sensors exists but is not crowded (Sensors 2017, DO and turbidity, about 31% battery saving; RL irrigation sampling 2026, sensing 38.8% vs LoRaWAN 38.4% of energy).
- S7, value of information for sensing (src/rescoping/voi_sensing.py, voi_summary.py; weather from src/data/fetch_openmeteo.py, Open-Meteo ERA5-based archive; results/rescoping/voi_sensing*.{csv,log}, voi_summary.csv). Design and pass rule fixed before running (docstring): one learned risk model per nested information set (F0 lag only = fixed; F1 + clock and last sampled values; F2 + cheap probes; F3 + solar radiation; F4 + rainfall; F5 + nearest same-river neighbour, an information bound), train odd months, test even months of 2023, raw and noise-controlled variants, 35-36 sites.
  - Pooled violation-share reduction vs F0 (best set): raw +11% at 24/day, +60% at 48/day; noise +34% at 24/day, +67% at 48/day. PASS RULE (>= 30% at both budgets in both variants) FAILED on raw at 24/day.
  - Wake-ups needed for F0's fidelity: raw 22.4 vs 24 (-7%), 35.6 vs 48 (-26%); noise 19.8 vs 24 (-17%), 33.3 vs 48 (-31%); the best set needs fewer wake-ups than F0 at 17/36 to 29/35 sites.
  - Almost all of the gain comes from F1-F2 (clock, last sampled values, cheap probes); weather and the neighbour add about 1 percentage point. At 12/day the learned policy is worse than fixed (-12% to -20% raw).
  - Lesson: the 6-site trial (+47% to +80%) overstated the effect; never judge a gate on a pilot subset.
  - Verdict: the constructive core is modest (about 7-31% fewer probe wake-ups, i.e. a few to about 25% of node energy where sensing dominates), close to the 2017 prior art's 31%, and external information is worth almost nothing. The bounds paper would therefore end as "simple rules are near the limit and extra information does not help": the negative-evaluation paper the user wants to avoid. Bounds paper not recommended.
- S8, joint oracle bound for OARS (2026-11-03, user's question: OARS is joint and adaptive, the earlier screens tested parts one at a time; src/rescoping/joint_oracle.py; results/rescoping/joint_oracle.{csv,log}). Total node energy (sleep + sensing + radio) of v0.3 (an2023_energy.csv E_bounded, 96 readings/day) vs a clairvoyant node making every decision jointly, at v0.3's service (every reading delivered within the hour plus the real-time tolerance between batches). Generous to the oracle: cheapest frame energy, no losses, backlog free, and radio capped at v0.3's energy with NO outages. Pass rule fixed before running: >= 30% at 5 s warm-up on two of three radios.
  - Result: FAIL. Median saving of total node energy at 5 s warm-up: 1-3% on the UVA and Weija outage records, 12-13% on InWaterSense (the worst record), 0% without outages; the largest anywhere is 19.7% (InWaterSense, NB-IoT, 1 s warm-up). This is a ceiling: our best causal probing policy captured 1.4-2.9% (G2).
  - Why: v0.3's service needs every reading sensed and delivered, so sensing cannot shrink; the oracle's frames (median 36.9/day) are not fewer than v0.3's diel-aware trigger needs; what remains is v0.3's outage waste, which is small except on InWaterSense.
  - Process note: the first run wrongly let the oracle deliver only the readings needed for the real-time value (14/day) and showed 54-72%. That is a weaker service, kept in the output as service B. A second correction charged the hourly batches their true number and size of frames (SF12 carries 3 readings per frame). Both errors favoured the oracle; both were found before reporting.
  - Service B (real-time value within tolerance, no complete record) would save 55-69% of total energy with clairvoyance, but it is a different product (Paper 3's tolerance-record ground), and S7 showed that a causal policy captures only 7-31% of the sensing part.
- Satellite direct-to-device IoT for remote rivers was considered and set aside: it is Paper 3's ground (byte-limited satellite messages, certified records).
- Pattern across all screens: in this corner of LPWAN telemetry, the simple rule is repeatedly at or near the optimum on real data (exponential back-off within 1-3% of the cross-validated optimum; one equilibrium after outages; natural diversity covers gateway failures). That regularity is a finding, but the user has ruled out an evidence paper. A mechanism needs a problem where a simple rule demonstrably leaves a large, measurable gap.
- The Prof's automated report (submissions/.../Q1_Novelty_Enhancement_Strategy_River_Telemetry.docx) recommends OARS, a joint online report/retry/buffer/probe/backfill scheduler, and sets its own test: "Design the simplest baseline that adds that same capability to V0.3; if it matches OARS, your proposed novelty is not sufficiently demonstrated." Our gates applied that test to OARS's components: belief-aware probing (G2, near-optimal back-off), congestion-constrained post-outage service (G1', FREE; S4, no trapped state), server-state uncertainty (seed a, BaySail). Its Option B (a measurement/evaluation paper) is our S3.

## 8. Lessons from the rescoping so far

- Outage handling for LPWAN telemetry is crowded at every layer we examined: retransmission, probing (near-optimal exponential back-off), and bulk recovery (FREE).
- Our durable assets are the measured outage processes (heavy-tailed, mostly shared), the USGS river data with the dual-prediction mirror, the trace-driven energy model, and the frozen-test protocol. A new scope should use them for a question nobody has answered, not to re-derive a known mechanism.
- After the 2026-11-03 screens, silence ambiguity and fleet diagnosis are also closed, and the post-outage collapse is not metastable. The seeds came from the neighbourhood of our own paper, which is where the field is most crowded. The next search should start from the other end: recent Q1 papers in LPWAN environmental telemetry and their stated assumptions, looking for an assumption our measured data shows false and that changes their conclusions.
- Two seeds screened on 2026-11-03 (both failed; see section 7):
  - Silence ambiguity in event-triggered telemetry: under Send-on-Delta or dual prediction, silence means "within tolerance" but may be an outage; the server cannot tell which and may display stale values as certain. Risk: a fixed maximum-silence timer may already be near-optimal (the back-off lesson), and event-triggered estimation with "negative information" exists.
  - Fleet-level outage diagnosis from delivery traces (LoRaWAN loss tomography): attribute each gap online to node, radio, gateway or backhaul from frame counters across many devices and gateways (LoED, UVA), to trigger the right remedy. Venue fit: Q1 network-management journals. Risk: network tomography is a large field; LPWAN-specific prior art not yet searched.

## 9. Next steps

1. Done: G1 and G2 for S1, G1' for S1', G1 for seeds (a) and (b), G2 for S4. All failed.
2. Assumption audit (proposed 2026-11-03): extract from 12-15 recent (2024-2026) Q1 papers on energy-efficient LPWAN telemetry (including the editor's three) the delivery and outage assumptions behind their headline results, and test each against the measured outage records. A candidate scope exists only where a broken assumption reverses or materially changes a published conclusion and the fix is not already published.
3. In parallel, the Prof decides whether S3 (Option B in the Prof's report: the evidence paper, now strengthened by the oracle bounds of G2 showing the simple design is near the optimum) is acceptable as a fallback.
3b. Status 2026-11-03 (end of day): steps 1-2 done, and the bounds paper (the reframed Option B) failed its value-of-information gate (S7). Every direction screened within LPWAN river telemetry and our assets is closed. The next decision belongs to the user: which uncongested area to scope next (a new starting point, not a neighbour of this paper), or whether to resume Paper 4 meanwhile.
4. Only then write a pre-registered design plan (as docs/DESIGN_EVAL_PLAN.md was), develop, freeze, and evaluate.
