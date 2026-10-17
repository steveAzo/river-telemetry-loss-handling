# Paper 2: initial scoping analysis (proposal 2, "cross-node reconstruction")

**Status:** scoping, revised 2026-10-12 after reading the downloaded literature (`papers/LITERATURE_NOTES.md`) and auditing the method. Nothing here is frozen; this is the evidence for choosing a scope with the Prof. Later sections keep their history: where a result was corrected, the correction is marked in place.
**Starting point:** `../proposals.md` §2, *"Spatial-Temporal Telemetry Reconstruction for Fading Mitigation in Multi-Node Riverbank Ad-Hoc Channels"*.
**Target:** a top journal (IEEE IoT-J or equivalent; see §7).

---

## 0. Bottom line (rewritten 2026-10-12 after the literature reading and the method audit)

1. **Proposal 2 as written cannot be done on InWaterSense** (§1). Its premises fail: the two nodes measure different water and share one gateway, node 2 is faulty, the neighbour predicts worse than persistence, and **rain does not affect sub-GHz link loss**. That last point is now tested on 16 months of real LoRaWAN data (§2.5b).
2. **Real deployments lose data in two regimes** (four systems: InWaterSense, Weija, LoED, UVA; §2.3–2.5b):
   - **many short radio losses:** ~10% of frames on well-heard LoRaWAN links, 84–89% of runs a single frame;
   - **few long system outages:** gateway, back-end, power or connectivity failures lasting hours to weeks, which hold a large share of the lost data (InWaterSense ~51% in outages ≥ 1 day, CI 29–65%; UVA 83% of system down-time in outages ≥ 1 day).
   - The memoryless loss model used across the literature is rejected on every record, and no single distribution fits all records; the two regimes must be modelled explicitly.
   - Practitioners report the same outages (Le Dinh 2007, Puluckul & Weyn 2025, Kyrgyzstan 2025), but nobody has measured them.
3. **What to do about them** (trace-driven, measured radio energy; §2.6b):
   - **ARQ** costs 1.5–7.4× the energy and recovers *none* of the outage losses.
   - **On NB-IoT, back-off** during outages is where the energy is won.
   - **Buffer + back-off** delivers 100% of readings at about the cost of the fair no-recovery baseline (−15% to +26%).
   - **Hourly batching** delivers 100% at 1.3–3.3× less energy, with about the same share of readings reaching the server within 1 h, because **timeliness is capped by the outages, not by the reporting scheme**.
4. **Reconstruction is for the real-time picture, not for the record** (§2.2b–c):
   - **gaps ≤ 1 h:** estimates stay within Paper 1's tolerance ~90% of the time;
   - **gaps of 24 h:** ≤ 25%, whatever the method;
   - **the right real-time estimator is the site's own diel model.** Neighbouring river sites add a little for temperature only, and naive tests overstate spatial value because of the diel confound.
5. **Recommended scope (§5, option A, reshaped):** *"Retransmit, Backfill or Reconstruct? Loss Handling for River Water-Quality Telemetry under Real Outages"*.
   - **Contributions:** (i) a real-outage characterisation; (ii) a trace-driven energy / completeness / timeliness comparison; (iii) a design combining hourly batching, immediate event reports, a diel-model real-time estimate between batches, and buffer + back-off through outages; (iv) the spatial-reconstruction result as a careful, mostly negative finding.
   - **Venue:** IEEE IoT-J is the primary target, and the write-up is not limited to 8 pages (§7).
   - **Still to do before the scope is frozen:** read the NB-IoT latency–energy theory (Azari 2019); find a source for NB-IoT "no network" energy; evaluate event latency; agree with the Prof.

## 1. Premise audit of proposal 2

| Premise in proposals.md | What the evidence says | Source |
|---|---|---|
| Node 1 and node 2 are two river points 100 m apart, with "predictable propagation delay" between them. | Node 1 (housing) is **at the discharge point source**, where the discharge tube ends. Node 2 (manhole) is ~100 m downstream. They measure different water (effluent-influenced vs mixed river). At typical velocities, 100 m is minutes, shorter than the 10-min cadence, so there is no usable lag. | Data in Brief 44 (2022) 108486, p. 8; `papers/txt/00_Ahmedi2022_InWaterSense_Dataset_DiB.txt` (gateway and node-location section) |
| A "deep GPRS fade at one node" can be repaired from the "parallel" stream of the other node. | **Both nodes reach the server through one gateway**, which is housed in node 2's manhole and sends everything over one GPRS link. A GPRS outage removes both streams at once. In the data, gaps co-occur: P(node 2 missing \| node 1 missing) = 0.73 vs a marginal 0.55 in the clean window. | Dataset paper l. 319–325; `src/scoping/inws_two_node.py` |
| Rain attenuation causes deep GPRS fades. | Rain attenuation is negligible at sub-3 GHz cellular frequencies (it matters above ~10 GHz). Outages at 900/1800 MHz come from coverage, congestion, network or power failures, which are mostly common to co-located nodes. *To cite properly: ITU-R P.838 coefficients.* | Standard propagation result; verify before writing |
| The two streams overlap enough to learn a cross-node model. | Node 2 produces 6,713 cycles, almost all in May–Aug 2015. It is plausible only until ~20 June 2015: from 21–22 June, T drops to 3 °C and EC jumps to 864 µS/cm. That leaves **~7 weeks** of usable joint data. | `inws_two_node.py`; Paper 1 §5.1 |
| The neighbour reconstructs lost packets well. | Even in the clean window, a linear model from node 2 predicts node 1 **worse than node 1's own 1-hour-old value** for all four parameters: RMSE T 2.77 vs 1.14 °C, DO 25.9 vs 8.4 %sat, EC 39.5 vs 33.0, pH 0.67 vs 0.58. Correlation of first differences is ≈ 0 (T 0.06, EC 0.14, pH 0.01, DO 0.00). | `inws_two_node.py` (window 1 May – 20 Jun 2015) |
| The two background papers listed. | **Neither exists.** OpenAlex has zero title matches. The same is true of proposal 1's first background paper. The proposal list must not be cited. | `openalex_title_check.py` |

**Consequence:** InWaterSense can only be a **counter-case** in Paper 2, as it was in Paper 1. Its most valuable asset for Paper 2 is unexpected: its **gap record, a real outage process of a GPRS water-quality deployment** (§2.3).

---

## 2. First experiments (2026-10-11)

### 2.1 InWaterSense, two nodes
Already summarised in §1. Script: `src/scoping/inws_two_node.py`.

### 2.2 USGS, Delaware River at Montague (01438500) → Frenchtown (01458500), 2023
- About 130 river-km apart, on the same main stem. Montague reports every 30 min, so the test uses a 30-min grid.
- **Test:** 300 random outages per parameter and length, at the target site. For each, compare the median maximum absolute error of:
  - the target's own last value ("persist");
  - linear interpolation using the value after the outage. This is an "oracle" for real-time use, but it is exactly what **backfill / delay-tolerant** reconstruction achieves;
  - the neighbour's lagged level ("nb_level"), or its change since the outage began, added to the last value ("nb_delta");
  - lag chosen by maximum correlation; regression fitted on the prior 7 days.
- Script: `src/scoping/usgs_pair_outage.py 01458500 01438500`.

**Target Frenchtown, neighbour Montague** (median max-abs error):

| Param | Outage | Persist | Interp (needs next packet) | Neighbour delta |
|---|---|---|---|---|
| T (°C) | 1 h | 0.10 | 0.03 | 0.07 |
| T | 6 h | 0.35 | **0.11** | 0.27 |
| T | 24 h | 0.90 | 0.71 | **0.68** |
| DO (%sat) | 1 h | 0.76 | **0.27** | 0.59 |
| DO | 6 h | 3.75 | **1.16** | 1.98 |
| DO | 24 h | 6.82 | 6.99 | **4.00** |
| pH | 24 h | 0.30 | 0.26 | **0.20** |
| EC (µS/cm) | 24 h | 7.0 | **3.0** | 10.0 (worse) |

The reverse direction (target Montague, neighbour Frenchtown) gives the same pattern: at 24 h, DO 9.1 → 4.6 and T 1.2 → 0.70.

**Reading:**
- For short outages the node's own history wins, and waiting for the next packet (backfill/interpolation) is best.
- Spatial information pays only once the outage is long enough for the river to drift, which is about a day here, and only for parameters with a shared diel or weather driver.
- Lags: for EC (13 h, Frenchtown target) it is a plausible travel time. For DO and pH the 21.5-h lag is a diel artefact, which a proper model must handle.
- This is one pair and one year: **provisional**.

> **Correction (2026-10-11, §2.2b):** the DO and pH gains above were the **day–night cycle, not spatial information**. Once the target's *own* "same hours yesterday" pattern is used as a baseline, the neighbour's real-time advantage disappears for DO and pH. The "interp" column is also **not backfill**: it bridges the gap from the values before and after it. True backfill (node buffers its readings and uploads them later) delivers the exact data, with zero error but late.

### 2.2b Full non-tidal Delaware chain, with a proper own-data control (2026-10-11)
- **Sites:** Callicoon → Montague → Frenchtown → Trenton (2023; 1-h grid because Trenton is hourly); all 12 ordered target–neighbour pairs.
- **Script:** `src/scoping/chain_outage.py`; summary `src/scoping/chain_summary.py`; results `results/scoping/chain_delaware.csv`.
- **Method:** lag and slope fitted on the first 20% of the year only; 300 outages per pair, parameter and length, drawn from the remaining 80%.
- **Real-time methods** (no data after the outage start):
  - persist (last value);
  - **diel** (last value + the target's own change over the same hours yesterday);
  - nb_delta (last value + neighbour change);
  - **diel_nb** (diel + the neighbour's departure from its own yesterday pattern).
- **Bridging methods** (the value after the outage is known): interp (straight line); interp_nb (line + the neighbour's shape).

**Median over pairs of the median max-abs error** (share of pairs where the best neighbour method beats the best own-data method):

| Param | Outage | Persist | Own diel | Best with neighbour, real time | Interp | Interp + neighbour |
|---|---|---|---|---|---|---|
| T (°C) | 6 h | 0.45 | 0.24 | 0.25 (50%) | 0.15 | 0.14 |
| T | 24 h | 1.13 | 0.75 | **0.65 (92%)** | 0.94 | **0.49** |
| T | 72 h | 1.96 | 1.43 | **1.08 (100%)** | 1.35 | **0.84** |
| DO (%sat) | 6 h | 5.2 | **1.8** | 2.1 (17%) | 1.7 | 1.7 |
| DO | 24 h | 10.2 | **4.2** | 4.9 (33%) | 10.3 | **6.8** |
| pH | 24 h | 0.48 | **0.25** | 0.30 (8%) | 0.47 | 0.46 |
| EC (µS/cm) | 24 h | 5.4 | 6.0 | 5.5 (25%) | **3.1** | 3.4 |

**Reading:**
1. **A site's own diel pattern is the strongest real-time reconstructor for DO and pH.** Neighbours add nothing on top.
2. **Neighbours help in real time only for temperature**, on outages ≥ 12 h: errors fall 6–26% vs own diel, in 75–100% of pairs. This is consistent with a shared, non-periodic weather driver.
3. **When bridging a gap after the link returns**, the neighbour's shape cuts error by ~34–45% for T and DO on outages ≥ 12 h, and by 12–17% for pH. EC never benefits.
4. **No reconstruction keeps Paper 1's error bound for long outages.** The share of outages with maximum error within the L2 tolerance falls from ≈ 0.9 at 1 h to ≈ 0.02–0.17 at 24 h, for every method.
5. **Consequence for the scope:**
   - If the bounded-error guarantee is to survive outages longer than a few hours, **only buffered backfill can provide it**.
   - Reconstruction's role becomes the **real-time interim estimate with a calibrated uncertainty**, plus a fallback when the buffer is lost (e.g. node reset).
   - Spatial information is a **secondary** contribution: worth it for T, and for bridging T and DO.
   - The other chains (Illinois, Tualatin, Clackamas, Klamath, McKenzie, Schuylkill) must confirm or overturn this before the scope is frozen.

### 2.2c All eight chains (2023; 2026-10-11)
- **Chains (first pass):** Delaware (4 sites), Illinois (3; see the update below for 5), Tualatin (4), Clackamas (3), McKenzie (2), Monongahela (2), Youghiogheny (2), Schuylkill (2; Philadelphia has no approved pH). Klamath (3) and Peoria/Des Plaines are still downloading.
- **Coverage:** 37–41 ordered pairs per parameter. Same method as §2.2b; results in `results/scoping/chain_*.csv`.
- **Bug fixed during this run:** the neighbour series was indexed by position, not by timestamp. It is now aligned to the target's timestamps. The Delaware results are byte-identical after the fix, because all four sites start at the same timestamp; all other chains were run with the fix.

**Median over pairs (share of pairs where the neighbour wins):**

| Param | Outage | Own diel (real time) | Best with neighbour (real time) | Interp | Interp + neighbour |
|---|---|---|---|---|---|
| T (°C) | 24 h | 0.68 | **0.59** (71%) | 0.82 | **0.49** (90%) |
| T | 72 h | 1.20 | **1.00** (85%) | 1.15 | **0.83** (98%) |
| DO (%sat) | 24 h | **3.6** | 4.2 (27%) | 7.4 | **4.5** (73%) |
| pH | 24 h | **0.13** | 0.14 (8%) | 0.20 | 0.20 (33%) |
| EC (µS/cm) | 24 h | 7.9 (persist 7.0) | 7.0 (20%) | **3.6** | 3.6 (22%) |

**Per chain, 24-h outages** (median gain from the neighbour, real time / bridging):

| Chain | T | DO |
|---|---|---|
| Delaware | +0.16 / +0.45 | −0.17 / +0.40 |
| Illinois | +0.10 / +0.32 | −0.02 / +0.04 |
| McKenzie | +0.06 / +0.13 | −0.18 / +0.59 |
| Tualatin | −0.07 / +0.20 | −0.07 / +0.13 |
| Clackamas | +0.06 / +0.01 | −0.12 / −0.13 |
| Schuylkill | +0.09 / +0.09 | −0.26 / −0.25 |
| Youghiogheny | −0.13 / +0.37 | n/a |
| Monongahela | +0.08 / +0.17 | n/a |

pH and EC show no gain anywhere except McKenzie pH bridging (+0.49).

**Reading (confirms §2.2b across rivers):**
1. **Real time:** the site's own diel model is the best estimator for DO and pH on every chain. The neighbour helps only temperature, modestly (+6–12% median at ≥ 24 h).
2. **Bridging after the link returns:** the neighbour reliably helps temperature (+18–29% at ≥ 12 h; wins in 85–98% of pairs). It helps DO on some rivers (Delaware, McKenzie) and hurts on others (Schuylkill, Clackamas). It never helps EC or pH.
3. **Error bound:** at 24 h, every method keeps the max error within the L2 tolerance in ≤ 25% of outages (EC bridging: 46%). **Long outages need buffered backfill** if the guarantee is to hold.
4. **A methodological finding worth stating in the paper:** a naive neighbour test (vs last value) shows large "spatial" gains for DO and pH (§2.2). They vanish against a diel baseline. Spatio-temporal reconstruction evaluated without a diel/seasonal own-history baseline will overstate the value of spatial correlation in river monitoring. *To check:* which baselines GRIN, SPIN and Kong et al. used. Typical baselines are mean, KNN, MICE and matrix factorisation, not a diel own-history model.

**Update (2026-10-11, late): all 9 chains, 27 sites (corrected 2026-10-14: earlier "32" was a miscount).**
- **Sites added:** Illinois now has 5 (Des Plaines at Joliet, Seneca, Starved Rock, Peoria, Florence), and Klamath has 3 (Miller Island, above Keno Dam, Keno). That gives 53–57 ordered pairs per parameter.
- **The conclusions above hold unchanged.** Share of pairs where the neighbour wins / median gain:

| Param | Outage | Real time | Bridging |
|---|---|---|---|
| T | 24 h | 72% / +0.06 | 93% / +0.23 |
| T | 72 h | 84% / +0.10 | 98% / +0.17 |
| DO | 24 h | 30% / −0.09 | 70% / +0.10 |
| pH | 24 h | 9% / −0.07 | 38% / −0.01 |
| EC | 24 h | 23% / −0.02 | 25% / −0.02 |

- **Within L2 tolerance at 24 h:** own diel 4–29% of outages; bridging 6–56%. Klamath (regulated) is the only chain where real-time DO gains (+0.04) and bridging pH gains (+0.12).

### 2.3 Real outage process (InWaterSense node 1, May 2015 – Jan 2016)
- 19,090 cycles delivered out of ~35,300 expected: **46% of slots missing**. 1,619 outage events; median length 2 slots; mean 10; maximum 1,879 slots (13 days).

| Outage length | Share of events | Share of lost slots |
|---|---|---|
| 1 slot (10 min) | 0.47 | 0.05 |
| 2–5 slots | 0.37 | 0.10 |
| 1–6 h | 0.13 | 0.16 |
| 6–24 h | 0.02 | 0.18 |
| ≥ 1 day | 0.01 | **0.51** (95% CI 0.29–0.65; §2.5) |

**Reading:**
- Losses are **bursty and heavy-tailed**, the opposite of the i.i.d. Bernoulli losses that Paper 1 and most of the reconstruction literature assume.
- Short outages are many but small. Long outages are rare but hold most of the lost data.
- **ARQ cannot fix a multi-hour outage.** Retransmitting into a dead link wastes energy. Only buffering + backfill (delay) or reconstruction (approximation) can.
- *Caveat:* gaps include power and node failures, not only link loss. Call them "outage traces", not "link-loss traces". Weija's gap record is a second, independent trace to extract.

### 2.3b Second real outage process: Weija (Ghana), 30 Oct 2018 – 11 Mar 2019 (added 2026-10-11)
- **Data:** the received per-parameter files (`data/weija_raw/`; the Prof allowed their use on 2026-10-11). Only non-imputed records count as delivered. Script: `src/scoping/weija_outages.py`.

| Stream (cadence) | Missing | Share of lost data in outages ≥ 1 day | Longest outage |
|---|---|---|---|
| Conductivity (32.5 min) | 15% | 0.83 | 7.5 d |
| pH (32.5 min) | 14% | 0.98 | 7.5 d |
| Temperature sensor two (32.5 min; Oct–Jan) | 2% | 0.71 | 1.1 d |
| Ca, F, temperature sensor one (32.5 min) | 40–44% | 0.92–1.00 | 36.7 d |
| DO, ORP, temperature sensor five (~5 h) | 17–23% | 0.71–0.94 | 14 d |

- **Reading:** the same structure as InWaterSense, on a different continent and system. Most outage events are short, but **71–100% of lost data is in outages of a day or more**. Long outages are therefore a property of real low-cost deployments, not an InWaterSense quirk.
- **Caveat:** Paper 1 found unflagged interpolation in these files (values with > 3 decimals, per-row ramps), so some short outages are hidden. Short-outage counts are lower bounds; long outages are reliable.

### 2.5 Outage-process models (2026-10-11, late)
- **Scripts:** `src/scoping/outage_models.py` (fits; `results/scoping/outage_models.csv`) and `src/scoping/outage_tail_check.py` (bootstrap CIs, tail and dependence checks; seed 20261011).
- **Models for outage length k ≥ 1 slot:**
  - geometric (memoryless: the Gilbert two-state model);
  - two-geometric mixture (a Markov chain with one up state and two down states);
  - discrete lognormal;
  - discrete power law.

**InWaterSense node 1** (1,619 outages; AIC = fit score, lower is better):

| Model | AIC | P(≥1 h) | P(≥6 h) | P(≥24 h) | P(≥72 h) | Lost share in ≥ 6 h | Lost share in ≥ 24 h |
|---|---|---|---|---|---|---|---|
| **Observed** | | 0.161 | 0.033 | 0.009 | 0.004 | 0.68 [0.55, 0.77] | 0.51 [0.29, 0.65] |
| Geometric | 10,537 | 0.591 | 0.025 | 0.000 | 0.000 | 0.11 | 0.00 |
| Two-geometric mixture | 7,107 | 0.144 | 0.067 | 0.016 | 0.000 | 0.74 | 0.35 |
| **Discrete lognormal** | **6,859** | **0.186** | **0.032** | **0.007** | **0.002** | **0.59** | **0.38** |
| Power law | 6,863 | 0.176 | 0.041 | 0.013 | 0.005 | 0.86 | 0.77 |

Brackets are bootstrap 95% CIs.

**Findings:**
1. **The memoryless (independent/Gilbert) loss model is rejected decisively.** It is worse by ≈ 3,700 AIC and predicts 0% of lost data in day-long outages vs 51% observed. The i.i.d. or Gilbert loss used in Paper 1 and most DPS and reconstruction work misrepresents real deployment outages.
2. **The discrete lognormal (μ = −3.74, σ = 2.79, in 611-s slots) matches the survival curve from 1 h to 72 h** and lies inside both CIs. The power law over-predicts the long-outage share; the two-geometric mixture has no outages ≥ 72 h.
3. **The "51% in outages ≥ 1 day" headline is uncertain:** 95% CI [0.29, 0.65], from 14 outages. Always quote it with the CI.
4. **Outages cluster.** Spearman(outage length, next outage length) = +0.27; Spearman(outage, next up-run) = −0.20. A renewal model that draws outages independently cannot reproduce "bad periods", and the up-runs are not geometric either (the two-geometric mixture wins by ΔAIC ≈ 2,600).
   - **Simulation design:** trace replay of the real delivery records (circular time shifts) is the primary loss model; a discrete-lognormal renewal model is used for sensitivity sweeps.
5. **Weija conductivity** (42 outages): too few to fit a tail. The lognormal and power-law survival curves match it (P(≥24 h): 0.060 / 0.057 vs 0.071 observed), but the day-long share has a CI of [0.00, 0.94] (3 outages). The lognormal fit is extreme (μ = −20.8, σ = 6.3): in effect a power law. This was re-checked with the corrected likelihood (§2.5b) and is a genuine optimum, not an artefact. Weija is **qualitative support only**.

### 2.5b Re-check of the outage models, and a third real network: UVA LoRaWAN (2026-10-12)
**Numerical bug found and fixed.**
- The discretised-lognormal likelihood divided two probabilities that both underflow at extreme parameters. With clipping, an optimiser could reach a spurious "perfect" fit (AIC 4).
- It is now computed with log upper-tail probabilities and fitted by weighted, multi-start maximum likelihood (`src/scoping/outage_models.py`).
- Tests: `tests/test_outage_models.py` checks normalisation including the analytic tail, agreement with the direct formula, parameter recovery, no spurious perfect fit, and geometric fits.
- **The InWaterSense and Weija results in §2.5 are unchanged by the fix** (identical AIC and shares, checked programmatically): those fits lay in the numerically safe region.

**Third real network.**
- **Source:** Nikseresht et al., BuildSys 2025 (paper 29); LibraData doi:10.18130/V3/RFTICK, CC BY 4.0; md5 verified.
- **Network:** 10 sensors every 5 min, 3 gateways, TTN, US915, 9 Feb 2024 – 11 Jun 2025 (16 months). The operators ran it continuously, so gaps are real outages, unlike LoED's campaign windows.
- **Script:** `src/scoping/uva_loss.py`; log `results/scoping/uva_loss.log`.
- **Classification of missing frames:**
  - **system** = no sensor at all reached the database in that 10-min bin (TTN, internet, or the operators' MQTT/database pipeline);
  - **gateway** = all of the sensor's serving gateways silent;
  - **radio** = otherwise.

| Quantity | Value |
|---|---|
| Pooled loss (frame-counter gaps) | 4.5% (per sensor 0.6–9.3%) |
| Missing frames: radio / system / gateway | **0.72 / 0.28 / 0.00** |
| Radio runs | 36,422; share of their lost frames in runs ≥ 1 h: **0.00** |
| System outages | 12 (availability 98.7%); median 1.7 h; max 82 h; **83% of system down-time in outages ≥ 24 h** |
| Share of *all* lost frames in runs ≥ 6 h / ≥ 24 h | 0.27 / 0.24 |
| Gateway C | down 30 days continuously, yet **no frames lost**: every sensor had a second serving gateway |
| Rain vs link loss (18 sensor–gateway pairs) | dry 0.0918 vs rain 0.0921; Wilcoxon p = 0.64: **no rain effect** |

**Model fits** (AIC):

| Record | Geometric | Two-type mixture | Lognormal | Power law | Best |
|---|---|---|---|---|---|
| InWaterSense | 10,537 | 7,107 | **6,859** | 6,863 | lognormal |
| Weija | 341 | 236 | 222 | **221** | power law (≈ lognormal) |
| UVA | 76,881 | **32,966** | 33,327 | 33,180 | **two-type mixture**; the only model near the observed ≥ 6 h share (0.27 vs 0.27) |

**Revised conclusions** (these replace the "lognormal is best" reading of §2.5):
1. **Every real record rejects the memoryless loss model, by thousands of AIC points** on the large records.
2. **No single distribution fits all three.** Outages are a *mixture of two populations*:
   - many short radio losses (UVA: 89% of runs are one frame, none ≥ 1 h; LoED: 84% single frames);
   - few long system outages (UVA: 83% of system down-time in outages ≥ 1 day; InWaterSense and Weija: about half or more of lost data in outages ≥ 1 day).
   - A well-run network (UVA) mainly has fewer system outages; the radio regime looks the same.
3. **Modelling decision for the paper:** represent the two regimes explicitly (radio loss: i.i.d. or mildly bursty; system outage: heavy-tailed durations), and use **replay of the real records** as the primary loss model.
4. **Gateway diversity masks gateway outages.** That is a design lever in its own right, and it explains why UVA's losses are dominated by the system (back-end) and radio regimes.
5. **The proposal's rain premise is not supported** by 16 months of real sub-GHz LoRaWAN data.

**Caveat:** "system" outages in UVA include the operators' own logging pipeline. From the user's point of view that is still data not reaching the record, which is exactly what backfill addresses.

### 2.6 Loss-handling strategies on real outage records: energy, delivery, delay (2026-10-11, late)

> **Superseded by §2.6b (2026-10-12).** The audit added a fair NB-IoT baseline (back-off without buffering), a batching reference and delivered-within-X-hours metrics, and fixed two simulator issues (batch back-off reset; end-of-record stranding). The headline "buffering uses less energy than unconfirmed" was mostly the effect of **back-off**, not buffering. Read §2.6b for the current results.
- **Code:**
  - `src/energy/loss_handling.py`: trace-driven model, built on a copy of Paper 1's energy model;
  - `src/energy/run_loss_handling.py`: runner, results in `results/scoping/loss_handling.csv`;
  - tests: `tests/test_loss_handling.py`; 68 pass, including Paper 1's energy tests, which confirm the copied model still reproduces its sources.
- **Set-up:** the real delivery records (InWaterSense node 1, 245 d at 611 s; Weija conductivity, 132 d at 32.5 min) are replayed as the link state, with one reading per slot. Lifetime includes Paper 1's sleep and sensing floor; 6600 mAh battery.
- **Strategies:**
  - `unconf`: unconfirmed;
  - `arq`: confirmed, up to 8 attempts on LoRaWAN (with the spec's data-rate decrease) or 3 on NB-IoT;
  - `arq_buffer`: confirmed + buffer + backfill;
  - `modem_buffer`: NB-IoT; the modem reports "no network";
  - `checkpointM`: unconfirmed + every M-th reading confirmed.

  The buffering strategies probe during outages either every slot or with exponential back-off capped at 1 h or 6 h.
- **Sources:** each energy figure is sourced in the module docstring.
  - **NB-IoT cell-search energy during an outage is not measured in any source we hold:** P_RX × T_search, with T_search swept over 2.2 / 10 / 60 s.
  - LoRaWAN maximum payloads per SF: verified against LoRa Alliance RP002-1.0.3 Table 12 (`papers/standards/`).

**InWaterSense record (p_radio = 0):**

| Radio | Strategy | J/day (transmission) | Life (y) | On time | Delivered | Median / p95 delay of late readings |
|---|---|---|---|---|---|---|
| LoRaWAN SF7 | unconf | 61.6 | 1.80 | 0.539 | 0.539 | – |
| LoRaWAN SF7 | arq | **447.1** | **0.46** | 0.539 | 0.539 | – |
| LoRaWAN SF7 | arq_buffer, probe every slot | 116.7 | 1.28 | 0.539 | 1.000 | 10.6 / 196 h |
| LoRaWAN SF7 | **arq_buffer, back-off ≤ 6 h** | **52.7** | **1.93** | 0.471 | **1.000** | 22.6 / 214 h |
| LoRaWAN SF7 | checkpoint6, back-off ≤ 6 h | 44.2 | 2.07 | 0.478 | 0.981 | 24.6 / 216 h |
| LoRaWAN SF12 | unconf / arq / arq_buffer ≤ 6 h | 147 / 796 / 159 | 1.10 / 0.28 / 1.04 | | 0.54 / 0.54 / 1.00 | |
| NB-IoT N211, 10-s search | unconf | 229.9 | 0.83 | 0.539 | 0.539 | – |
| NB-IoT N211, 10-s search | **modem_buffer, back-off ≤ 6 h** | **62.5** | **1.97** | 0.471 | **1.000** | 22.4 / 213 h |

**Weija record:** the same ordering.
- LoRaWAN SF7: unconf 19.3 J/d (84% delivered); arq 58.3 (84%); arq_buffer ≤ 6 h **16.8 J/d (100%)**.
- NB-IoT: unconf 40.1 vs modem_buffer ≤ 6 h **23.5 J/d (100%)**.

**Findings:**
1. **Standard ARQ is the worst choice under real outages.** On LoRaWAN it uses 3–7× the transmission energy of unconfirmed reporting and recovers **nothing**: retrying into a dead network fails, so 46% is still lost. It does recover i.i.d. radio losses (with p_radio = 0.096, the LoED full-data rate, its lost share stays at 0.461), but those are the minor part.
2. **Buffering with probe back-off delivers 100% of readings, and on most configurations uses less energy than unconfirmed reporting** (which keeps transmitting into the outage). *Corrected 2026-10-12; the first version said "on both radios", which is false:*
   - **NB-IoT, every search time:** less energy, from the outage effect alone. Confirmed RAI-400 is slightly *dearer* per message than RAI-200.
   - **LoRaWAN SF7:** about the same or less energy (52.7 vs 61.6 J/d InWaterSense; 16.8 vs 19.3 Weija; +0.6% on Weija with radio loss added). Part of this is not the outage effect: at SF7 the ACK arrives in RX1, so RX2 is never opened, and a confirmed success (0.164 J radio) is **cheaper** than an unconfirmed message (0.244 J; Casals Tables 5–8).
   - **LoRaWAN SF12: more energy** than unconfirmed (158.7 vs 147.2 J/d InWaterSense, +8%; 52.5 vs 46.1 J/d Weija, +14%), because the ACK comes in RX2 at SF12 and confirmed costs more (0.858 vs 0.729 J). Buffering still delivers 100% vs 54% / 84%.
   - **The honest claim:** buffering + back-off (cap 6 h, `arq_buffer`) delivers every reading at an energy change vs unconfirmed of:
     - NB-IoT: −3.6% to −85.5%, smallest with a short search time and few outages (Weija);
     - LoRaWAN SF7: −14.6% to +0.6%;
     - LoRaWAN SF12: +7.8% to +25.6%.

     This is across both records, p_radio ∈ {0, 0.096} and all three search times. ARQ, by contrast, costs 3–7× more and delivers nothing extra.
3. **The price is timeliness.** On-time delivery falls (0.539 → 0.471), and late readings wait a median ~22 h (p95 ≈ 9 days) on InWaterSense. **The back-off cap is the energy–latency knob.** This is the "outage-age-aware" design parameter of option A, and it defines the job of reconstruction: real-time estimates until the backfill arrives (§2.2b–c: the site's own diel model, plus neighbours for T).
3b. **With realistic radio loss on top** (p_radio = 0.096, LoED full data; rerun 2026-10-11): the conclusions hold. On InWaterSense, LoRaWAN SF7 gives:
   - unconf: 61.6 J/d, 49% delivered;
   - arq_buffer ≤ 6 h: **54.2 J/d, 100% delivered**.

   On NB-IoT, `modem_buffer` now loses 4.4%, because radio losses go undetected without ACKs, while the confirmed `arq_buffer` ≤ 6 h delivers 100% at the same energy (63.4 vs 62.8 J/d). **Confirmed + buffer + back-off is the better design on both radios.**
4. **Checkpointing** (LoRaWAN without per-reading ACKs) is cheapest but loses 2–6% of readings, from short outages that fall between checkpoints. Shorter outages are exactly where server-side reconstruction works well (§2.2b: within tolerance ~90% at 1 h).
5. **On NB-IoT**, the lifetime under outages is set by the unmeasured cell-search energy unless the node backs off. With back-off the conclusion does not depend on it. *To measure or source before submission.*

**Caveats:**
- The records cannot separate "network down" from "node off". If the node was unpowered, there is nothing to backfill, so the delivered = 1.0 rows are an upper bound for those periods.
- Duty-cycle waiting of LoRaWAN *retransmissions* is not modelled (it changes delay, not energy).
- A real node's flash buffer is finite; unlimited here, but the code supports a cap.

### 2.6b Loss handling, revised after the audit (2026-10-12): energy, completeness, timeliness
**What changed and why:**
1. **Fair NB-IoT baseline `unconf_backoff`:** unconfirmed sending that backs off when the modem reports "no network" and discards what it cannot send. The old `unconf` baseline cell-searched every slot during outages, which no sensible NB-IoT node would do. Against it, buffering's NB-IoT "saving" disappears.
2. **Batching reference `batchB`:** buffer everything and upload every B hours in bulk confirmed frames, with buffer and back-off on failure. Bulk frames are cheap per reading (NB-IoT: 42 readings for ~1.6× one message; LoRaWAN SF7: 18 per frame), so energy alone cannot rank strategies; delay is the price.
3. **Timeliness metric:** the share of *all* readings that reached the server within 1 h, 6 h and 24 h. "On time" (same slot) is meaningless for batching.
4. **Bug fixed:** in `batch`, every failed probe reset the back-off, so the node probed about every 2 slots. Probes are now single small confirmed messages, as in `arq_buffer`. A regression test covers all buffering strategies.
5. **Artefact fixed:** readings a node had not yet uploaded when the *record* happened to end were counted as lost. A flush period now lets the node finish if the link is up at the end (delays and energy counted). Tests cover both cases, including a record that ends during an outage, where the readings really are lost.
6. **ARQ with 3 attempts** added as a sensitivity (the spec default is 8).
7. Tests: 90 pass (`tests/`).

**Results** (`results/scoping/loss_handling.csv`; summary `loss_handling_summary.txt`; paired comparison `loss_handling_fair_comparison.csv`). InWaterSense record, no extra radio loss; back-off cap 6 h where applicable:

| Radio | Strategy | J/day | Life (y) | Within 1 h | Within 24 h | Delivered |
|---|---|---|---|---|---|---|
| NB-IoT, 10-s search | unconf | 229.9 | 0.83 | 0.539 | 0.539 | 0.539 |
| NB-IoT, 10-s search | **unconf_backoff** (fair baseline) | **59.5** | 2.02 | 0.471 | 0.471 | 0.471 |
| NB-IoT, 10-s search | arq_buffer | 63.8 | 1.95 | 0.528 | 0.742 | **1.000** |
| NB-IoT, 10-s search | **batch1h** | **23.6** | **2.88** | 0.521 | 0.746 | **1.000** |
| NB-IoT, 10-s search | batch6h | 13.3 | 3.29 | 0.113 | 0.763 | 1.000 |
| LoRaWAN SF7 | unconf (fair baseline) | 61.6 | 1.80 | 0.539 | 0.539 | 0.539 |
| LoRaWAN SF7 | arq (8) / arq (3) | 447.1 / 175.5 | 0.46 / 0.97 | 0.539 | 0.539 | 0.539 |
| LoRaWAN SF7 | arq_buffer | 52.7 | 1.93 | 0.528 | 0.741 | 1.000 |
| LoRaWAN SF7 | **batch1h** | **18.9** | **2.65** | 0.520 | 0.745 | **1.000** |
| LoRaWAN SF12 | unconf / arq_buffer / batch1h | 147.2 / 158.7 / 89.4 | 1.10 / 1.04 / 1.49 | 0.539 / 0.516 / 0.506 | | 0.54 / 1.00 / 1.00 |

**Findings** (ranges over both records, NB-IoT search 2.2 / 10 / 60 s, LoRaWAN SF7 / SF12, p_radio 0 and 0.096):
1. **ARQ is the wrong tool under real outages.**
   - On LoRaWAN it costs **2.6–7.4×** (8 attempts) or **1.5–2.9×** (3 attempts) the energy of unconfirmed reporting.
   - It recovers only the i.i.d. radio losses (+5–8 percentage points delivered when p_radio = 0.096) and **none** of the outage losses.
2. **On NB-IoT, back-off is where the energy is won.** Searching for the network in every slot of an outage costs **1.2–6.5×** the energy of backing off (`unconf` vs `unconf_backoff`); the ratio grows with the outage share and the search time.
3. **Buffering buys completeness at small cost.**
   - `arq_buffer` (back-off ≤ 6 h) delivers **100%** of readings for **−15% to +26%** energy vs the fair no-recovery baseline.
   - The sign depends on the radio: cheaper at LoRaWAN SF7 (cheap RX1 ACKs), dearer at SF12 and mostly dearer on NB-IoT (−5% to +15%).
4. **Batching hourly is the energy-efficient design for non-urgent telemetry.**
   - `batch1h` delivers 100% using **1.3–3.3×** less energy than the fair per-reading baseline.
   - It gets about the same share of readings to the server within 1 h (−3.3 to +7.3 percentage points vs `unconf`).
   - Under real outages, **timeliness is capped by the outages, not by the reporting scheme**, as long as the batch interval is about 1 h or less.
5. **The trade-off that remains is timeliness of individual readings** (minutes vs up to 1 h). That matters only for alarms.

**This points to a design** (to be built and evaluated, not yet a result):
- batch routine data (≈ 1 h);
- send **events immediately** (Paper 1's detector);
- show **reconstructed estimates** between batches. Gaps ≤ 1 h stay within tolerance ≈ 90% of the time, §2.2b–c; the site's own diel model is the right estimator;
- **buffer + back-off** through outages.

**Caveats:**
- **Node off vs network down:** the records cannot tell them apart, so delivered = 1.0 is an upper bound.
- **NB-IoT no-network search energy is unmeasured** (swept). With back-off it matters little.
- **Bulk-frame cost models:** NB-IoT +60% at 512 B (Michelinakis), LoRaWAN from Casals with airtime by payload. Batching's advantage rests on them and must be stated.
- **LoRaWAN duty-cycle waiting of retransmissions** is not modelled (it affects delay, not energy).
- **Event latency** (alarms) is not yet evaluated.
- **From the deployment literature** (`papers/LITERATURE_NOTES.md` §E), two effects the model does not capture:
  - **backfill contention:** draining a backlog can starve live traffic (SensorScope [59]); bounded drain rate or interleaving is needed;
  - **buffer media failure:** SD cards fail ([52], [56]); the model treats the buffer as perfect.

  Silent gateway failures last until a watchdog or a person acts ([56], [59]), so system-outage duration is partly an operations variable.

### 2.7 Design evaluation (2026-10-12; plan written before running)
- **Documents:** plan `docs/DESIGN_EVAL_PLAN.md` (deviations D1–D2 recorded in its §7); results `docs/DESIGN_EVAL_RESULTS.md`; code `src/design/`.
- **Set-up:** 30 USGS sites × 3 real outage links (+ none) × 3 radios × 4 strategies; 6,728 injected events (Paper 1 detector, frozen).
- **H1 pass (12/12):** with the link up, the design's alarm latency equals per-reading reporting (median ≈ 1 h, which is the detector's own delay). Plain hourly batching adds a median 0.5 h.
- **H2 pass (12/12):** the design costs +0–2% over plain batching, and 1.4–3.9× less than per-reading ARQ.
- **H3:** for events that start during an outage, unconfirmed reporting learns of 0–5%; buffering strategies of 99–100%, but only after the outage (median 12–55 h). The design is fastest or tied.
- **H4 fail (29/48):** the real-time picture of **DO and pH** between hourly uploads is 6–8 pp less often within tolerance than per-reading reporting (not a tidal artefact; > 5 pp at 57% / 77% of sites). T and EC pass.
- **Bounded-error trigger (Part 2, pre-registered; results 2026-10-13):** the node keeps an exact copy of the server's estimator and uploads whenever the server's picture would leave tolerance.
  - **H5 pass, 48/48:** the picture matches per-reading reporting for every parameter on every link; 100% within tolerance with the link up, SF7 and NB-IoT.
  - **H6 pass, 12/12:** 1.3–2.3× less energy than per-reading ARQ, and 7–55% more than plain batching.
  - **H7 pass:** alarms are unaffected.
  - **H1–H4 re-judged** on the rerun (seeds now from the site ID, D3): identical verdicts.
  - **SF12 packing detail:** two-frame batches delay the newest reading by 247 s. Fix: send the newest *valid* reading first (implemented; Part 3).
- **The full design** (hourly batching + immediate event uploads + bounded-error trigger + buffer and back-off) is now the paper's proposed scheme.
- **Part 3 (2026-10-14):**
  - **H8 (newest-first):** failed as pre-registered, in 4 slots at one site. The cause was two implementation defects: a gap placeholder promoted to the first frame, and arrival times ignored. Fixed (D4), rerun on all 30 sites: **pass post hoc**, exact everywhere.
  - **H9 / H10 (tolerance L1 / L3):** pass. The bounded design is 1.18–1.48× (L1), 1.31–2.35× (L2) and 1.39–3.35× (L3) cheaper than per-reading ARQ, with the picture within ±0.7 pp of it.
  - **Without the trigger at L1:** DO −26.5 pp and pH −19.3 pp.

### 2.4 Real LoRaWAN link loss (LoED; sample first, then the full dataset)
- **Data:** LoED (Bhatia et al., DATA '20; Zenodo 10.5281/zenodo.4121430, CC BY 4.0). Each uplink logs `device_address` and `fcnt`, so per-device loss = frame-counter gaps, taking a frame as received if any gateway heard it. Script: `src/scoping/loed_loss.py`.
- **Caveat:** the devices belong to other operators, so a "lost" frame is one that no LoED gateway heard. Across all 729 devices with ≥ 50 frames, median loss is 0.68, mostly because the devices are far from these gateways. Only **well-heard devices** (loss < 20%; n = 69) resemble a node's own link.
- **Well-heard devices:**
  - pooled loss 6.7%;
  - P(loss | previous lost) = 0.14, about 2× the marginal, so mildly bursty;
  - 87% of loss bursts are a single frame; the longest burst is 7 frames.
- **Reading: two loss regimes.**
  - **Radio loss** is short. ARQ can fix it, and so can the node's own temporal reconstruction.
  - **System outages** (InWaterSense, §2.3: gateway, power or backhaul) last hours to days. ARQ cannot fix them; only backfill or (spatial) reconstruction can.

  This split is the backbone of option A: the right loss-handling strategy depends on which regime a gap belongs to, and a node or server can tell the regimes apart by outage age.
- **Full dataset (done 2026-10-11, late; supersedes the sample figures above):**
  - **Data:** all 188 daily files (398 MB zip, md5 verified against Zenodo; read in place, not extracted); 5.12 M unique uplink frames, 8,503 DevAddrs, 9 gateways.
  - **Script:** `src/scoping/loed_full.py`; log `results/scoping/loed_full.log`; tables `results/scoping/loed_full_{gateways,devices}.csv`.
  - **Method:** a missing frame (frame-counter gap) is classed as **gateway-down** if none of the device's serving gateways logged anything in that hour, and as **radio loss** otherwise.

| Quantity | Value |
|---|---|
| Devices with ≥ 200 frames / well-heard (radio loss < 20%) | 1,780 / 179 |
| Well-heard: pooled radio loss; median per device | **0.096; 0.095** |
| Well-heard: P(loss \| previous loss) | 0.248 (≈ 2.6× the marginal: mildly bursty) |
| Radio-loss bursts: length 1 / 2–5 / > 5 | **0.84 / 0.15 / 0.01** (max 589, an outlier) |
| Well-heard: share of missing frames in gateway-down hours | 0.13 |
| Gateways logging continuously (130 d; 2 gateways) | **0 down hours** |
| Gateway inactive runs ≤ 72 h (plausible operational outages) | 7 runs, median 1 h |
| Same-minute co-loss with another device at a shared gateway | 0.192 vs independence baseline 0.182 [0.167, 0.195] |

  - **Reading:**
    - The LoRaWAN radio link loses ~10% of frames, almost always one at a time.
    - The LoED gateways themselves were almost never down, so radio loss is **the short-loss regime**, distinct from the day-long system outages of the two water-quality deployments (§2.3, §2.3b, §2.5).
    - Radio losses do not coincide across devices beyond what loss density alone produces.
  - **Correction:** the 6-day sample suggested 14× excess co-loss. That was an artefact. The random-shift baseline moved losses onto days missing from the sample, which deflated the baseline. With all days, no excess remains.
  - **Inconclusive:** whether a gateway logged nothing in the minute of a loss (coinciding 0.029, isolated 0.126). Quiet gateways often log nothing in a given minute anyway, so this does not identify gateway glitches.
  - **Caveats:**
    - Devices belong to third-party networks. "Lost" means not heard by any LoED gateway, and "well-heard" devices are the closest proxy for a node's own link.
    - Long gateway gaps are campaign windows, not failures.

---

## 3. Literature map: what exists and where the gap is

Papers downloaded to `papers/pdf/` (31 PDFs; text in `papers/txt/`). Number = file prefix. Paywalled or bot-blocked papers are listed in `papers/README.md` for manual download.

### 3.1 Spatio-temporal reconstruction in sensor networks (signal processing / data side)
| Work | What it does | What it does not do |
|---|---|---|
| Kong et al., *Data Loss and Reconstruction in Sensor Networks*, INFOCOM 2013 / IEEE TPDS 2013 (not OA, to obtain) | Low-rank and spatio-temporal reconstruction of lost readings; the anchor paper of this line | Random-mask losses; no protocol, energy or latency comparison |
| STCDG (IEEE TWC 2012), matrix-completion data gathering (44, 43; Sensors/IEEE Access variants) | Collect a subset of readings and complete the matrix | Dense networks of similar sensors (temperature fields); multi-hop cost models |
| Luo et al., compressive data gathering, MobiCom 2009 (not OA) | Compressive sensing over multi-hop gathering | Not for LPWAN star topologies |
| Zhang et al., spatio-temporal compressive sensing, SIGCOMM 2009 / ToN 2011 | Method template (low rank + temporal smoothness) | Traffic matrices |
| GRIN (12, ICLR 2022), SPIN (13, NeurIPS 2022), BRITS (14), GNN time-series survey (15, TPAMI 2024), downsampling (16), motif-aware GNN (45), scalable STGNN (46) | State-of-the-art graph and deep imputation | Imputation error only, on random or block masks; no communication cost, no latency requirement, no real outage processes |
| Water-quality imputation (24; WRR 2025 water-distribution paper, not OA) | Imputing WQ gaps | Offline gap filling, not online protocol design |

### 3.2 Remote estimation and the reliability–freshness trade-off (communication-theory side)
| Work | What it does | What it does not do |
|---|---|---|
| Sinopoli et al., Kalman filtering with intermittent observations, IEEE TAC 2004 (2,562 cites; not OA) | Estimation stability under Bernoulli loss | Single sensor, i.i.d. loss |
| **Huang, Liu, Li & Vucetic: *To Retransmit or Not* (01, ICC 2019), HARQ remote estimation (02); Nadeem, Li, Vucetic & Shirvanimoghaddam: HARQ optimisation (03)**; *Transmit or Retransmit*, IEEE TIT 2024 (04) | **The exact trade-off we pose:** send fresh data vs retransmit old data, to minimise the estimation MSE | LTI toy processes, one sensor, mission-critical control timing, no spatial side-information, no real data, no LPWAN energy |
| **Sun & Pappas: *Semantic-Aware Remote Estimation with Overlapping Sensor Coverage*, MobiHoc '26 (05)** | Several sensors observe the same source and differ in reliability and delay; a joint source–sensor scheduling CMDP | Finite-state Markov sources, theory only, no real data, no energy model. **Closest new competitor; cite and differentiate.** |
| AoI survey (08, JSAC 2021); semantic-aware estimation (06, 07, TCOM); AoI scheduler (09, TAC); multi-sensor scheduling (10, TCNS); goal-oriented estimation (11, TCOM); value of communication (41, TIT) | Freshness and semantics metrics; scheduling theory | Abstract sources; none uses environmental data or outage traces |
| Event-triggered estimation surveys (35) | "Negative information": silence is informative | Ambiguity between suppressed and lost packets: we already met this in Paper 1 |

### 3.3 LPWAN reliability and loss measurements
| Work | Relevance |
|---|---|
| Zhao & Govindan, SenSys 2003 (32) | Classic evidence that wireless sensor loss is bursty and heterogeneous |
| LoED, LoRaWAN-at-the-Edge dataset (arXiv 2010.14211, Zenodo 10.5281/zenodo.4121430) | Open gateway-side LoRaWAN packets. **Confirmed: it holds device address + FCnt**, so it gives real per-device loss traces (§2.4) |
| LoRaWAN campus study (Yasmin et al., 2 years, 300+ devices), Shanghai 8-month trace | Seasonal and interference effects mean losses are not i.i.d. |
| *Persistent Packet Loss in LoRaWAN*, SSRN 2026; *Long-term LoRaWAN metadata dataset*, BuildSys 2025 | Found in OpenAlex but **not confirmed by web search**; to verify before citing |
| Paper 1 energy sources (Sørensen, Michelinakis, Casals) | Reused: ACK/RX-window and retransmission energy for NB-IoT and LoRaWAN |
| IoT in developing countries: LoRaWAN vs NB-IoT (Electronics 2021, to download) | Ghana-relevant framing |

### 3.4 River-network statistics
| Work | Relevance |
|---|---|
| Spatial stream-network (SSN) models ("tail-up"/"tail-down" covariances): Ver Hoef & Peterson, JASA 2010; Peterson & Ver Hoef, Ecology 2010 (25); SSN/SSN2 R packages; scalable SSN (27); stream sampling (26) | The physically right notion of "neighbour" on a river (flow-connected vs not); needed for a credible spatial model |
| Physics-guided recurrent graph model for river networks (Jia et al. 2021; to download) | Graph + physics for stream temperature |
| Water-quality sensor placement for state estimation (34) | Observability viewpoint |

### 3.5 The gap (to be stated as a claim and defended)
No work evaluates **retransmission, buffering/backfill and server-side spatio-temporal reconstruction as competing loss-handling strategies**, measured jointly in energy, fidelity (maximum and RMS error, event capture) and latency, under **real, bursty, cross-node-correlated outage processes**, on **real multi-site environmental data**.
- The communication-theory side has the trade-off, but on toy sources.
- The imputation side has the models, but no protocol, energy or latency.
- The WSN reconstruction side assumes dense networks of similar sensors and i.i.d. losses.

---

## 4. Data available for Paper 2

| Source | What | Role |
|---|---|---|
| USGS continuous WQ, the same 4 parameters (T, EC, DO, pH) | **139 active stream sites** in NJ/PA/IL/OR have all four in real time (`results/scoping/usgs_scout_sites.csv`). **Same-river chains:** Delaware (8 sites: Lordville, Callicoon, Montague, Frenchtown, Trenton, Pennypack Woods, Penn's Landing, Chester), Illinois (5), Klamath (4), Tualatin (4), Susquehanna (3), Clackamas (3), Fishing Creek (3), Youghiogheny, Schuylkill, Wissahickon, Monongahela, Ohio (2 each). | Main benchmark: flow-connected multi-node networks. **To do:** check which sites have approved data in the same years (catalog dates were inconsistent; verify per site). Tidal sites (lower Delaware: Penn's Landing, Chester) must be excluded or handled, as in Paper 1. |
| **Chain availability, checked 2026-10-11** (`src/scoping/usgs_availability.py`, from approved daily means; `results/scoping/chain_availability.csv`) | Usable in **2023** (≥ 250 approved days for all four parameters): Delaware Callicoon → Montague → Frenchtown → Trenton (4 non-tidal; Pennypack Woods, Penn's Landing and Chester are tidal, a separate regime); Illinois Seneca → Starved Rock → Peoria → Florence (4) + Des Plaines at Joliet (tributary); Tualatin (3, + 1 seasonal); Clackamas (3); Klamath (3, regulated); McKenzie (2); Schuylkill (2; Wissahickon tributary pair only in 2024); Monongahela (2) and Youghiogheny (2), seasonal (~180–210 days). **Not chains:** "Fishing Creek" (two different streams with the same name) and Susquehanna (no common year). | ~30 sites in 9 chains for one common year |
| Paper 1's 13 USGS sites (2023, cleaned) | Already cleaned; two are Delaware main-stem (Montague, Frenchtown); Wissahickon and Schuylkill are tributary-connected | Immediate start |
| InWaterSense node 1 gaps | Real GPRS-deployment outage process (§2.3) | Loss/outage trace to replay |
| Weija (Prof's deployment) gaps | Second real outage process (Ghana) | Loss/outage trace; check what the received files allow |
| LoED (LoRaWAN) | Real multi-device LoRaWAN loss, if frame counters are present | Cross-node-correlated loss traces |
| Synthetic Gilbert–Elliott and common-shock loss | Controlled sweeps of burstiness and cross-node correlation | Sensitivity analysis |

---

## 5. Candidate scopes

### Option A (recommended; reshaped 2026-10-12): **"Retransmit, Backfill or Reconstruct?"**
*Working title: Retransmit, Backfill or Reconstruct? Loss Handling for River Water-Quality Telemetry under Real Outages.*

- **Question:** given how real low-cost deployments actually lose data, which combination of reporting and loss handling gives the best energy, completeness and timeliness, and what should the server show while data are missing?
- **Strategies compared** (implemented in `src/energy/loss_handling.py`, 90 tests):
  - unconfirmed;
  - unconfirmed + back-off (NB-IoT);
  - ARQ (3 or 8 attempts);
  - confirmed + buffer + back-off;
  - modem-detected buffering (NB-IoT);
  - checkpointing (LoRaWAN);
  - batching (1 h, 6 h).

  Each runs on two radios (NB-IoT with a swept search energy; LoRaWAN SF7 / SF12) and replays real delivery records.
- **Contributions** (the evidence already exists for 1, 2 and 4; 3 is to be built):
  1. **Real-outage characterisation** from four systems: two water-quality deployments (Kosovo GPRS, Ghana) and two LoRaWAN networks (LoED, UVA).
     - Two regimes (short radio losses, long system outages); the memoryless model is rejected everywhere, and no single distribution fits all records.
     - Gateway diversity masks gateway outages.
     - Rain has no effect on sub-GHz link loss.
     - This quantifies what Kong et al. described qualitatively and what deployment reports (Le Dinh 2007; Puluckul & Weyn 2025; Kyrgyzstan 2025) describe anecdotally.
  2. **Energy / completeness / timeliness comparison under real outages** (§2.6b):
     - ARQ is the wrong tool;
     - back-off is essential on NB-IoT;
     - buffering buys completeness at small cost;
     - hourly batching is 1.3–3.3× cheaper with about the same 1-h timeliness;
     - every result is stated with its radio-specific mechanism (RX1 vs RX2 ACK cost; NB-IoT modem feedback).
  3. **A design for river telemetry**, evaluated against the strategies above: hourly batched routine data, immediate event reports (Paper 1's detector), a diel-model real-time estimate between batches, and buffer + back-off through outages. **Metrics:** event latency, energy, completeness, and the server-side error of the real-time picture.
  4. **Spatial reconstruction on rivers, done carefully** (§2.2b–c): 9 chains, 27 sites. The site's own diel model beats neighbours in real time for DO and pH; neighbours help T; no method keeps the bound at 24 h. The **diel confound** explains why naive tests (and benchmark evaluations without a diel baseline) overstate spatial value.
  5. **Open benchmark:** outage records, river chains, simulator, tests.
- **Why it suits a top journal:**
  - Real-data evidence on a question that both the communication-theory literature (retransmit vs fresh data; Huang, Nadeem, Sun & Pappas) and the imputation literature (GRIN, SPIN, Kong) leave open.
  - It is rigorous in the way Paper 1 is: multiple real systems, tests, honest negatives.
- **Risks and how we handle them:**
  - *"Buffering and batching are obvious."* We credit the practice ([33], [53], [54]); the contribution is measurement, quantification, the per-radio mechanisms, and the ARQ finding.
  - *Node off vs network down* in the water-quality records: state completeness as an upper bound; UVA (operated network) separates the causes.
  - *NB-IoT search energy unmeasured:* swept; conclusions hold with back-off; seek a source or measurement.
  - *Batching's advantage rests on the bulk-frame energy models:* state them; test sensitivity.

### Option B: spatially-informed loss detection for event-triggered reporting
- **Idea:** under Paper 1's suppression, silence means "no change". A lost packet makes silence ambiguous, which is why Paper 1 needed heartbeats (+15–30% reports for RLS-D). If a correlated neighbour reports a change while the target stays silent, the server can suspect a loss and query, instead of paying for heartbeats.
- **Assessment:** elegant and protocol-level, but it relies on short-horizon cross-site correlation. §2.2 shows that correlation is weak at hour scales. It also helps only where Paper 1's prediction pays, which excludes InWaterSense and Weija.
- **Better as one mechanism inside option A (S5) than as a paper.**

### Option C: GNN imputation for river networks
- **Idea:** a new graph architecture for flow-connected river networks.
- **Assessment:** crowded (GRIN, SPIN and many follow-ups at ICLR/NeurIPS/AAAI/KDD), not communication-centric, and the competition is ML labs with GPUs. **Not recommended.** We use GRIN/SPIN as baselines in A, not as the contribution.

### Option D: proposal 2 as written (InWaterSense node 1 ↔ node 2)
- **Not viable** (§1). It would not survive review: shared gateway, a discharge point vs the river, only ~7 weeks of joint data, and a neighbour that predicts worse than persistence.

---

## 6. Next steps (updated 2026-10-12)

**Done since the first version:**
- USGS chains (9 chains, 27 sites, §2.2c);
- outage traces and models (§2.3–2.5b, including UVA);
- the energy model with ARQ / buffer / back-off / batching (§2.6b);
- the literature read (`papers/LITERATURE_NOTES.md`).

**Open, in order:**
1. **Decide with the Prof:** the reshaped option A. (Venue: IEEE IoT-J primary, no 8-page limit while writing, per the user 2026-10-12. Weija: use allowed, 2026-10-11.)
2. ~~Event latency~~ and ~~bounded-error trigger~~: done (§2.7; `docs/DESIGN_EVAL_RESULTS.md`).
3. **NB-IoT "no network" energy:** find a measured source (vendor application notes, measurement papers) or plan a bench measurement.
4. **Read in full:** Azari et al. 2019 (NB-IoT latency–energy, [55]); Huang/Nadeem [01–04] policy structure.
5. ~~Download the remaining deployment papers~~: done 2026-10-12 (paper 28 unavailable, not needed). Read them; design constraints in `papers/LITERATURE_NOTES.md` §E.
6. **Sensitivity:** bulk-frame energy (NB-IoT payload scaling; LoRaWAN payload), the back-off cap sweep, and buffer size.
7. **Re-run inline analyses as scripts:** §1 (daily and clean-window two-node analysis) and §2.3 (InWaterSense outage table) were computed inline; turn them into scripts before writing.

---

## 7. Venue (decided by the user, 2026-10-12)

- **Target:** a top journal. **IEEE Internet of Things Journal remains the primary target.**
- **Length:** the write-up is **not** constrained to IoT-J's 8-page limit (beyond which IoT-J charges page fees). Write the full paper the evidence needs; decide on cutting, a supplement, or a different top venue once the draft exists.

| Venue | Fit |
|---|---|
| **IEEE Internet of Things Journal** (primary) | Same community as Paper 1; values real data and energy; protocol + data paper |
| ACM Trans. Sensor Networks | Systems + real deployments (SensorScope [59] was published there); the Prof's 2017 survey venue; no strict page cap |
| IEEE Trans. Green Communications and Networking | Energy–reliability angle (Azari et al. [55] published there) |
| IEEE TWC/TCOM | Only if the design gets a real theoretical result (e.g. an optimal outage-age threshold policy, following Huang et al.) |

---

## 8. Files

- `src/scoping/`:
  - `inws_two_node.py`, `usgs_pair_outage.py`, `usgs_scout.py`, `usgs_availability.py`: data scouting;
  - `chain_outage.py`, `chain_summary.py`: river-chain reconstruction test (§2.2b–c);
  - `weija_outages.py`, `outage_models.py`, `outage_tail_check.py`: outage records and models (§2.3–2.5);
  - `loed_loss.py`, `loed_full.py`: LoED (§2.4);
  - `uva_loss.py`: UVA LoRaWAN (§2.5b);
  - `openalex_search.py`, `openalex_title_check.py`: literature search and citation checks.
- `src/energy/`:
  - Paper 1's `model.py` and `params.py` (copied unchanged);
  - `loss_handling.py` (strategies) and `run_loss_handling.py` (§2.6b).
- `src/data/`: `fetch_usgs.py`, `clean_usgs.py`, `clean_weija.py` (copied from Paper 1), `fetch_chains_2023.sh`.
- `tests/`: `test_energy.py` (Paper 1's), `test_loss_handling.py`, `test_outage_models.py`. 90 pass.
- `results/scoping/`: all outputs (CSV, logs).
- `papers/`: `pdf/` and `txt/` (54 papers), `standards/` (LoRaWAN RP002), `LITERATURE_NOTES.md`, `README.md`, `download_list.tsv`.
- `data/`: `clean/` (USGS, InWaterSense, Weija cycles), `inws_raw/`, `weija_raw/`, `loed_full/` (zip, md5 verified), `loed_sample/`, `uva_lorawan/` (md5 verified).
- `docs/TUTORIAL_PAPER2.md`: the ground-up tutorial (update pending, see the report history).
