# Confirmatory evaluation on held-out data: plan fixed before the data are analysed (2026-10-17)

**Why.** The review (C3, E3, M10) notes that the bounded-error trigger was designed after H4 failed on the 2023 USGS data and was then judged on the same data. The 2023 runs are therefore *development* evidence. This plan tests the frozen design on data that played no part in its development: the **2024** records of the same candidate sites.

**Status of the held-out data when this plan was written.** No 2024 water-quality file had been downloaded for analysis. One connectivity test was made on 2026-10-17 (site 01427510, 2024-03-01..02, four series, first value of each printed) to confirm that the USGS service still serves 2024 approved data. Nothing else from 2024 was seen.

**Freezing.** The code that will produce and judge the results is listed in §8 with SHA-256 hashes, computed after the smoke tests on 2023 data and before the 2024 download. Any change after that is a deviation, recorded in §9 with its reason before its effect is known, and the result is rerun with every verdict reported before and after.

**Honest limit.** This plan is kept with the code and timestamped by its hashes; it is not registered with a third party. The paper will say exactly that.

---

## 1. Data

- **Candidate sites:** the 39 USGS sites in `data/clean/usgs/` (the development candidates).
- **Download:** `src/data/fetch_usgs.py <site> 2024-01-01 2024-12-31` for each candidate; cleaning with `src/data/clean_usgs.py 2024 data/clean/usgs_2024` (approved values only, as in development).
- **Eligibility:** `src/confirm/eligibility.py data/clean/usgs_2024 2024 results/confirm/eligibility_2024.csv`, the development rule written as code (it reproduces the 2023 file exactly): all four parameters present; complete cycles cover ≥ 50% of the record span and ≥ 50% of the 2024 calendar-year slots at the native step. No other exclusion. If fewer than 15 sites are eligible, the run still goes ahead and the small number is reported.
- **Training/test split, tolerances, detector, events, links, radios:** exactly as in development (DESIGN_EVAL_PLAN §1–§4, Parts 2–3, with deviations D1–D5). L2 EC tolerance = 2% of the site's 2024 whole-record median.
- **Seeds:** per site, (site ID + 2024) mod (2³¹ − 1), so link offsets and radio-loss draws are new. Event injection uses the development code and seed 0 on the new series.

## 2. The frozen design

Bounded event-driven batching as in the paper: hourly confirmed bulk uploads; immediate upload on a node alarm; immediate probe on an alarm during an outage; the bounded-error trigger (inclusive tolerance, D5) on the server estimate (own-diel), mirrored at the node with arrival *times* (D4); trigger not consulted during an outage; newest valid reading first (D4); back-off min(2ⁿ, K) slots with K = 6 h; buffer unlimited. Called **Bounded** below. FIFO packing (design_bounded) is run alongside and reported, as in development.

## 3. Strategies and runs

`src/confirm/run_confirm.py data/clean/usgs_2024 results/confirm/eligibility_2024.csv results/confirm/2024 2024`: Unconfirmed, ARQ + buffer, Batch 1 h, Event (event-driven batching), Bounded (FIFO and newest-first) at L1, L2, L3; links none / UVA / Weija / InWaterSense; radios NB-IoT (10-s search), LoRaWAN SF7, SF12. Events at L2.

## 4. Metrics

As in development: alarm latency (link up at onset, detected events), transmission energy per day (event-driven designs averaged over the four event settings), share of scored slots within tolerance (series without events).

## 5. Primary hypotheses and decision rules

Judged by `src/confirm/analyse_confirm.py` on the median site of each link × radio (12) or link × radio × parameter (48). A hypothesis passes only if its rule holds in **every** combination; any failure is reported with the combination, and no mechanistic explanation will be used to turn a failure into a pass.

| ID | Claim | Rule |
|---|---|---|
| CH1 | Link up: Event raises alarms as fast as per-reading reporting | Event − ARQ+buffer latency ≤ 1 slot |
| CH2 | Event costs about as much as batching, much less than per-reading ARQ | Event / Batch ≤ 1.10 and ARQ+buffer / Event ≥ 1.3 |
| CH4 | Event's picture is as good as per-reading reporting's (**expected to FAIL** for DO and pH, replicating development) | Event ≥ ARQ+buffer − 5 pp |
| CH5 | Bounded's picture is as good as per-reading reporting's | Bounded ≥ ARQ+buffer − 1 pp (L2) |
| CH6 | Bounded costs no more than per-reading ARQ | Bounded ≤ ARQ+buffer energy (L2, with events) |
| CH7 | The trigger does not delay alarms | Bounded − Event latency ≤ 1 slot |
| CH8 | Newest-first makes the picture exact with the link up | No-outage link: Bounded within L2 tolerance at every scored slot, every site × parameter × radio |
| CH9 | CH5 holds at L1 and L3 | as CH5, per level (series without events) |
| CH10 | CH6 holds at L1 and L3 | as CH6, per level (series without events) |

CH3 (events starting in an outage) stays descriptive.

## 6. Secondary analyses (reported, no pass rule)

- Site-bootstrap 95% CIs (10,000 resamples of sites) for every median-site statistic above.
- All injected events, detected or not: share the server knows within 1, 6 and 24 h of onset (review M11).
- Physical plausibility (review M12): an injected event is *plausible* if all its values stay within T ∈ [−0.5, 40] °C, EC > 0, pH ∈ [4, 11], DO ∈ [0, 250] %sat. CH1 and CH7 are repeated on plausible events only.
- The same script is run on the development rerun (2023, salt 0) so the two years are reported side by side.

## 7. What the paper will say

2023 results: development (H1–H4 written before their runs; H5–H10 written after H4 failed, before their runs). 2024 results: confirmatory, judged by this plan. If a confirmatory verdict differs from the development one, the confirmatory verdict is the one the paper states as its result.

## 8. Frozen code (SHA-256)

Filled in by `src/confirm/freeze.py` immediately before the 2024 download; see `docs/CONFIRMATORY_FREEZE.txt`.

## 9. Deviations after freezing

(none yet)
