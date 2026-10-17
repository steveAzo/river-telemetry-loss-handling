# Paper 2: literature notes

*Written 2026-10-12, after reading the downloaded papers. Numbers in brackets are file prefixes in `pdf/` and `txt/`.*

**Rule (as in Paper 1):** every statement below was checked against the PDF text. Where a paper was only skimmed (abstract, method section, evaluation set-up), this is said. The "background papers" listed in `../../proposals.md` do not exist and are not cited.

---

## A. Paper cards: the papers that decide our positioning

### [47] Kong, Xia, Liu, Chen, Gu, Wu & Liu, *Data Loss and Reconstruction in Wireless Sensor Networks*, IEEE TPDS 25(11), 2014 (INFOCOM 2013 version)
- **What it does:**
  - Analyses Intel Indoor, GreenOrbs (forest) and OceanSense data and reports large losses: 23%, 35% and 64%.
  - Proposes ESTI-CS: compressive sensing with spatial and temporal smoothness, plus a multi-attribute component.
- **Loss model (§4.2):** five *named* loss patterns, each motivated by its cause, not measured: element random; block random (congestion); frequent loss in a row (bad link); successive loss in a row (node damaged or out of energy); and a combination. The text says "we synthesize several typical data loss patterns".
- **Evaluation:**
  - Uses "small but complete subsets" with synthetic masks, at loss rates of 10–90%.
  - Baselines are CS, KNN, Delaunay triangulation and MSSA. There is no per-site day–night ("seasonal-naive") baseline, although the data are temperature and light with strong day–night cycles. MSSA can capture periodicity, so we critique carefully, not absolutely.
- **For us:**
  - The **anchor citation** for "WSN loss is not random".
  - They *name* the long-outage pattern but never *measure* durations, fit distributions or test clustering, and they have no protocol or energy view.
  - **Our contribution is to measure what they described,** across four real systems, and to show that it decides the protocol choice.

### [12] Cini, Marisca & Alippi, *Filling the G_ap_s* (GRIN), ICLR 2022; [13] Marisca, Cini & Alippi, *SPIN*, NeurIPS 2022
- **What they do:** graph-neural-network imputation (GRIN: bidirectional recurrent; SPIN: sparse spatio-temporal attention).
- **Missing data in the benchmarks:**
  - "Block missing": 5% random, plus *simulated failures lasting U(12, 48) steps* (1–4 h at 5-min steps) with 0.15% probability.
  - "Point missing": 25% random.
  - AQI: an evaluation mask copied from the previous month's real missingness.
- **Baselines:** mean, KNN, MF, MICE, VAR, rGAIN, BRITS (and GRIN for SPIN). There is **no seasonal-naive / diel baseline**. SPIN's *own* model includes sine/cosine time-of-day encodings.
- **For us:**
  - The state-of-the-art imputers are tested on **1–4 h failures**, but real deployment outages hold most of the lost data in **outages of ≥ 1 day** (§2.3–2.5 of the scoping report).
  - They do not compare against the strongest simple baseline that our river data require.
  - **They are baselines for the reconstruction part, not competitors for the paper.**

### [18] Chang, Tao, Wang et al., *Deep Compressed Sensing based Data Imputation for Urban Environmental Monitoring*, ACM TOSN 20(1), 2023 *(skimmed)*
- Evaluated with **"completely random missing"** at 10–70%, against ST-MVL and AKE. The same blind spot as GRIN and SPIN.

### [01] Huang, Liu, Li & Vucetic, *To Retransmit or Not*, ICC 2019; [02] same authors, HARQ for real-time remote estimation (arXiv 2019); [03] Nadeem, Li, Vucetic & Shirvanimoghaddam, HARQ optimisation, arXiv 2022/23; [04] *Transmit or Retransmit*, IEEE TIT 2024 *(abstracts and introductions read)*
- **The trade-off we study, in theory:** after a failure, retransmit the old measurement (more reliable with HARQ) or send a fresh one; minimise the long-run estimation MSE. Optimal policies have a switching structure.
- **Set-up:** linear time-invariant processes, one sensor, i.i.d. packet drops, mission-critical control timing.
- **For us:** they give the theory vocabulary, but not our setting: real outage processes, multi-day outages, LPWAN energy, environmental data.

### [05] Sun & Pappas, *Resource-Constrained Semantic-Aware Remote Estimation with Overlapping Sensor Coverage*, MobiHoc '26 *(abstract and introduction read)*
- Several sensors observe the same finite-state Markov source and differ in reliability and delay. A constrained-MDP scheduler picks the (source, sensor) pair.
- **For us:** the closest *theory* of "neighbours as redundancy". It has no real data and no energy model. Our river results (neighbours help little beyond each site's own day–night cycle) are an empirical counterpoint.

### [48] Sinopoli, Schenato, Franceschetti, Poolla, Jordan & Sastry, *Kalman Filtering with Intermittent Observations*, IEEE TAC 49(9), 2004
- With i.i.d. (Bernoulli) observation arrivals, the expected error covariance is bounded only if the arrival probability exceeds a critical value set by the system's instability.
- **For us:** the classic reference for estimation under loss, and an example of the **i.i.d.-loss assumption** that our outage data contradict.

### [33] Le Dinh, Hu, Sikka, Corke, Overs & Brosnan (CSIRO), *Design and Deployment of a Remote Robust Sensor Network: Experiences from an Outdoor Water Quality Monitoring Network*, IEEE LCN/SenseApp 2007
- **Deployment:** the Burdekin irrigation area (Australia); Fleck3 nodes; gateway on ADSL.
- **Delivery:** average per-node delivery **~64%**. Losses happened "in the gateway" because the gateway–server TCP connection "was down occasionally".
- **Recovery:** end-to-end NACK recovery with copies kept in RAM improved delivery by at most **10.6%**.
- **Their future work:** use the node's flash "to provide a significantly larger buffer that allows the system to handle network outage better".
- **For us:**
  - A **third water-quality deployment showing the system-outage regime**.
  - Early evidence that acknowledgement-style recovery barely helps against outages.
  - It shows that buffering was the practitioners' intuition, which we must credit; *our* contribution is the measurement and the trade-off analysis.

### [53] Puluckul & Weyn, *Experiences with Sub-Arctic Sensor Network Deployment*, IEEE WCNC 2025 (arXiv 2405.02986)
- **Outages:** "multiple short-duration outages lasting a couple of days to weeks, mostly due to the malfunctioning of the gateways and power or connectivity issues", plus two outages of about a month.
- **Their answer to loss:** **oversampling**. Nodes send every 15 min although the application needs one packet per hour, "to deal with packet losses". The nodes also have flash "for data buffering".
- **For us:** an independent report of the multi-day outage regime. Oversampling defends against radio loss but not against outages of days, which is where our analysis says the data are lost.

### [54] Low-cost weather stations in Kyrgyzstan, *Frontiers in Communications and Networks*, 2025
- Cellular networks in remote areas "often experience prolonged outages", because base stations rely on diesel generators.
- They propose a **disruption-tolerant gateway** that stores LoRaWAN messages locally and forwards them when cellular service returns (lab-tested on a Milesight UG67).
- **For us:** gateway-side store-and-forward is known practice. It covers *backhaul* outages only, not gateway power loss, radio loss or node-side problems. That is a distinction our two-regime analysis can quantify (UVA: system outages ≈ 28% of missing frames).

### [58] Langendoen, Baggio & Visser, *Murphy Loves Potatoes: Experiences from a Pilot Sensor Network Deployment in Precision Agriculture*, IPDPS workshops 2006
- **Latency tolerance:** the application needed advice each morning, so "sensor data need not be made available immediately, but can be buffered for up to one day". For time and manpower reasons they used standard immediate forwarding anyway.
- **Planned reliability scheme:** each node logs to EEPROM in a cyclic buffer, and the gateway sends a daily network-wide acknowledgement of missing packets. In effect, batching with backfill.
- **Outages:**
  - a "backbone connection outage" (1 July 2005);
  - the solar-powered gateway (Wi-Fi assumed duty-cycled by one partner, always on by the other) lost power every night until a few hours after sunrise, missing dawn, the agriculturally most critical period;
  - nodes ran out of batteries about three weeks into the restarted deployment.
- **For us:**
  - the most-cited deployment-failure paper names both of our premises: latency tolerance of hours to a day, and system outages (backbone; gateway power);
  - its planned scheme is our batching + backfill;
  - nightly gateway power loss is a periodic system outage worth naming.

### [59] Ingelrest, Barrenetxea, Schaefer, Vetterli, Couach & Parlange, *SensorScope: Application-Specific Sensor Network for Environmental Monitoring*, ACM TOSN 6(2), 2010
- **System:** environmental stations with a GPRS sink; 512 KB flash on the nodes; six deployments of 4–180 days.
- **§6.3.1, "simultaneous losses for all stations":** a GPRS driver bug stopped the sink reconnecting after unexpected disconnections. The outage lasted until the team noticed and rebooted the modem by SMS.
- **"After its reboot, the GPRS was sometimes so busy reading packets from the Flash memory that it could not handle arriving messages, causing their loss."**
- Temperature-driven clock drift between the mote and the GPRS chip also lost packets on the serial link.
- **For us:**
  - a system outage that hits all nodes at once (the regime);
  - **a backfill pitfall: draining a backlog can starve live traffic.** Our model does not include this contention. It is a design constraint: drain at a bounded rate, or interleave live data with the backlog.

### [57] McDonald, Geraghty, Humphreys, Farrell & Cahill, *Sensor Network with Delay Tolerance (SeNDT)*, ICCCN 2007
- **Design:** delay-tolerant network nodes for **lake water-quality monitoring** (Ireland) and noise logging.
- **Operation:** all data are stored on the node and collected manually over Wi-Fi from the shore, with data mules planned. Lake units woke for 2 min every 30 min.
- **Result:** solar charging matched consumption in summer but **did not charge at all in early winter**.
- **For us:**
  - prior DTN work in water quality, which must be cited;
  - no outage measurements and no protocol comparison;
  - winter power failure is a **node-off** outage, the cause that our water-quality records cannot separate from network outages.

### [52] Murphy, Tveito, Flittie et al., *Experiences Building and Deploying Wireless Sensor Nodes for the Arctic Tundra*, CCGrid 2021
- **Architecture:** observation units "cannot rely on a network connection", so data "must be stored locally". A *store* abstraction keeps append-only local logs.
- **Push protocol:** small chunks, advancing a saved file position **only after an ACK** from the server; the server can correct the position.
- **Losses:** two units lost data to **damaged SD cards**. The contact timeline shows long periods without server contact.
- **For us:**
  - a reference implementation of buffer + acknowledged backfill;
  - the buffer medium itself can fail, which is a threat to completeness that our model treats as perfect.

### [56] Brzozowski, Frohberg & Langendoerfer, *Real-World Deployments of Sensor Networks: Practical Lessons for Researchers*, WWIC 2018
- **Earlier deployments it cites:** the sink gathered **2%** of readings in one year's deployment and **51%** in the next, after simplification.
- **Silent gateway failure:** a GSM gateway (BeagleBone + USB modem) stopped forwarding because the modem silently disappeared from the OS. It was fixed by a daily hardware-watchdog reset.
- **Storage failure:** the SD card used to store readings failed. Control frames kept arriving but sensor data stopped; the authors recommend redundant storage.
- **For us:**
  - silent gateway failures, the system-outage regime;
  - the risk that the buffer's storage fails;
  - **watchdog resets** as a practical remedy that bounds how long such outages last.

### [49] Bhatia, Breza, Marfievici & McCann, *LoED: The LoRaWAN at the Edge Dataset*, DATA '20; [29] Nikseresht, Leal Sobral, Goodall & Campbell, *Long-term LoRaWAN Communication Metadata from an Urban Deployment*, BuildSys '25
- **Our real LoRaWAN loss sources.**
- **LoED:** London; 9 gateways in campaign windows; third-party devices.
- **UVA:** 10 sensors every 5 min, 3 gateways, 16 months, frame counters, co-located weather; LibraData doi:10.18130/V3/RFTICK, CC BY 4.0. The authors note intermittent loss to gateway B and frequent loss for two sensors to the indoor gateway C (NLOS).
- **For us:** the radio-loss regime (§2.4, §2.5b). UVA additionally gives system outages, gateway diversity and a rain test.

### [09-11, Paper 1] Casals 2017 (LoRaWAN energy), Sørensen 2021 (NB-IoT/LTE-M lifetime), Michelinakis 2021 (NB-IoT energy, IEEE IoT-J)
- **The energy sources of our model.**
- **Casals:** state-by-state current traces; ACK in RX1 vs RX2; up to 8 transmissions of a confirmed message, with the data rate lowered every 2 attempts (§3.3.2).
- **Michelinakis:** per-report energy with RAI; payload 20 → 512 B costs ~+60%, never > 100%.
- **Sørensen:** N211 power states (RX 222 mW; sync 160 mJ / 2.2 s).
- **Gap we flag:** none of them measures an NB-IoT modem's energy while searching when there is *no* network.

### [55] Azari, Stefanovic, Popovski et al., *On the Latency-Energy Performance of NB-IoT Systems in Providing Wide-Area IoT Connectivity*, IEEE TGCN 2019 *(title and authors checked; to read)*
- An analytical latency–energy model of NB-IoT. Likely the right citation for the batching (energy vs delay) trade-off on NB-IoT. **Read before writing.**

### [31] Ugwuanyi, Paul & Irvine, *Survey of IoT for Developing Countries: Performance Analysis of LoRaWAN and Cellular NB-IoT Networks*, Electronics 2021
- Measured on the same equipment: NB-IoT needs about **2 mAh more to join** and **1.7 mAh more per 44-byte uplink** than LoRaWAN.
- **For us:** an independent, developing-country (Nigeria) energy reference; useful for the Ghana framing.

---

## B. The rest, in one line each

| # | Paper | Use |
|---|---|---|
| 06–07, 40–41 | Semantic / goal-oriented estimation (TCOM, TIT, surveys) | Vocabulary (value of information); no real data |
| 08 | Yates et al., Age of Information survey, JSAC 2021 | Timeliness metric background |
| 09–11 | AoI scheduler (TAC); multi-sensor scheduling over lossy channels (TCNS); goal-oriented estimation (TCOM) | Theory context |
| 14, 16, 17 | BRITS (NeurIPS 2018); forecasting with missing data; Bansal et al. DeepMVI (VLDB 2021) | Imputation baselines |
| 15, 45, 46 | GNN time-series survey (TPAMI 2024); motif-aware GNN; scalable STGNN (AAAI) | Imputation background |
| 19 | Piao et al., low-rank spatio-temporal data collection, Sensors 2014 | Low-rank gathering |
| 20 | Zhang et al., lossy WSN, distributed storage + CS, Sensors 2018 | Multi-hop, mobile sink; peripheral |
| 21 | Resilient aggregation, EURASIP 2018 | Peripheral |
| 22, 23 | ML virtual sensor (JSAN 2020); IoT imputation (Future Internet 2022) | Imputation in WSN; random-missing evaluations |
| 24 | Rodríguez et al., water-quality imputation, 50–70% missing, Uruguay, Sustainability 2021 | Water-quality imputation (low-frequency data) |
| 25–27 | Peterson & Ver Hoef 2010 (Ecology); Som et al. 2014; scalable SSN 2025 | River-network spatial statistics (the "right neighbour") |
| 30 | Spadaccino et al., LoRaWAN behaviour from dataset traffic, Sensors 2022 | Another LoRaWAN dataset analysis |
| 32 | Zhao & Govindan, packet delivery in dense WSNs, SenSys 2003 | Classic bursty-loss evidence |
| 34 | Water-quality sensor placement for state estimation, JWRPM 2021 | Observability view |
| 35, 36 | Event-triggered control/estimation survey; event-triggered estimation with packet loss (IEEE Access 2020) | Paper 1 link (silence vs loss) |
| 37 | Jesus et al., data quality for dependable WSN monitoring, Sensors 2017 | Dependability background |
| 38, 39 | CS in IoT review (JSAN 2018); Razzaque et al., compression in WSN survey (TOSN 2013) | Background |
| 42 | Real-time cooperative communication for automation, TWC 2017 | Cooperation/relaying background |
| 43, 44, 50, 51 | 1-bit CDG; MC + CS gathering; Luo et al. CDG (MobiCom 2009); Cheng et al. STCDG (TWC 2013) | Compressive / matrix-completion data gathering (dense multi-hop) |

---

## C. Gap table (what exists vs what we add)

| Question | Closest prior work | What it lacks | What Paper 2 adds |
|---|---|---|---|
| How do real deployments lose data? | Kong [47] (named patterns); Le Dinh [33], Puluckul [53], Kyrgyzstan [54], Langendoen [58], SensorScope [59], Brzozowski [56] (anecdotes) | Durations, distributions, clustering; separation of radio vs system | Outage-length distributions from **4 real systems** (InWaterSense, Weija, LoED, UVA); memoryless model rejected; two-regime structure; gateway diversity masks gateway outages |
| Does retransmission (ARQ) help? | Huang/Nadeem [01–04] (theory, LTI, i.i.d.); Le Dinh [33] (+≤ 10.6%) | Real outage processes; LPWAN energy | Trace-driven: ARQ costs 1.5–7× and recovers *nothing* under real outages (LoRaWAN, 3 or 8 attempts) |
| Is buffering / store-and-forward worth it? | Practice: [33] future work, [52] store abstraction, [53] flash, [54] gateway buffer, [57] DTN, [58] node log + daily ACK | No quantification of energy, completeness and timeliness; no comparison | Buffer + back-off: 100% completeness at about the cost of the fair no-recovery baseline (−15% to +26%, radio-dependent); **back-off** is where NB-IoT energy is won; gateway-side buffering covers only back-end outages |
| Batching vs real time? | Paper 1 batching baseline; Azari [55] (NB-IoT latency–energy theory) | Under real outages | Hourly batching delivers about the same share within 1 h as per-reading reporting (outages, not the scheme, cap timeliness) at 1.3–3.3× less energy than the fair per-reading baseline |
| Can neighbours / reconstruction replace delivery? | GRIN/SPIN [12, 13], Kong [47], STCDG [51], Sun & Pappas [05] | Tested on random or 1–4 h gaps; no diel baseline; no protocol view | 9 river chains / 27 sites: own diel model beats neighbours in real time for DO and pH; neighbours help T; no method stays within tolerance at 24 h; **diel confound** in naive tests |

---

## D. Still to obtain or read

- **Read in full:** [55] Azari et al. (NB-IoT latency–energy); [01–04] full papers (policy structure, for the outage-age-aware design).
- **Unavailable:** paper 28 (Jia et al., physics-guided recurrent graph model for river networks, SDM 2021) is paywalled with no open copy. It is not needed for the reshaped scope. If cited at all, cite it from its abstract only and say so; better, leave it out.
- **Search not yet done:** NB-IoT behaviour when the network is absent (cell search, back-off timers, "out of service" energy). We need a measured value or a vendor figure.

## E. What the deployment papers change in our design and limitations (2026-10-12)

**Store-and-forward is established practice.** [33] future work, [52] store abstraction, [53] flash buffering, [54] gateway buffer, [57] DTN, [58] node logging + daily acknowledgement. We must say so plainly. Our contribution is to measure outages, compare remedies on energy / completeness / timeliness, and identify which mechanism wins on which radio.

**Three constraints our model does not capture yet** (state them; consider modelling the first):
1. **Backfill contention** [59]: draining a backlog can starve live traffic. Mitigation: bounded drain rate; interleave live readings with the backlog.
2. **Buffer media failure** [52, 56]: SD cards and flash fail. Completeness depends on storage reliability; redundant storage is the remedy.
3. **Silent gateway failures** last until someone or something (a watchdog) acts [56, 59]. The *duration* of system outages is therefore partly an operations variable. That fits our observation that outages are long and heavy-tailed, and suggests watchdog resets as a remedy that bounds outage length.

**Latency tolerance is documented:** "can be buffered for up to one day" [58]. This supports batching for routine environmental data.
