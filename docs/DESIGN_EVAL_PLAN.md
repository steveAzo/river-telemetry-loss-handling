# Design evaluation: plan written before running (2026-10-12)

**Purpose.** Evaluate the proposed reporting design against the alternatives, under real outages. The design is:
- routine data batched hourly;
- an immediate upload when the node's event detector fires;
- the site's own diel-model estimate shown by the server between deliveries;
- buffer + back-off through outages.

This plan is fixed *before* any result is seen, like Paper 1's Weija pre-registration. Deviations will be listed in the results report with reasons.

---

## 1. Data

- **Signals:** every USGS site in `data/clean/usgs/` with 2023 approved data for all four parameters (T, EC, pH, DO), and complete cycles (all four present) in ≥ 50% of the year's slots at the site's native step. Excluded sites are listed with the reason.
- **Time grid:** the site's native regular grid over its 2023 record. A slot without a complete cycle is a *sensor gap*: the node still wakes and transmits on schedule (energy is counted), but no metric is scored at that slot.
- **Training / test split:** first 20% of the record for detector training (Paper 1's rule); metrics only on the remaining 80%.
- **Outage processes (the link):** three real delivery records, mapped onto each site's grid in *physical time*, wrapped circularly, with a random start offset per site (seed = site index):
  - **InWaterSense** node 1 (GPRS; 46% of slots missing);
  - **Weija** conductivity (≈ 16%);
  - **UVA** LoRaWAN `sensor04`, union of gateways (4.4%; the sensor whose loss is closest to the pooled 4.5%).

  Plus a **no-outage** control. A site slot is "link down" if the record's nearest slot is missing. No extra i.i.d. radio loss is added: the records already contain their real radio losses.
- **Radios:** NB-IoT N211 RAI (10-s no-network search), LoRaWAN SF7, LoRaWAN SF12.

## 2. Events and detector (inherited from Paper 1, frozen)

- **Injected events:** Paper 1's `inject.py`, copied unchanged: steps and ramps of amplitude 5σ and 8σ (σ = the month's robust residual scale), lasting 180 min, in the test period, ≥ 3 days apart, one parameter each. Four settings per site.
- **Detector:** Paper 1's frozen choice: `CusumDetector`, mode lag, lag 120 min, k = 3, H = 8, c = 6; one per parameter; trained on the training period. Recording resolution is estimated from the data: the most common positive difference between sorted distinct values.
- **Not re-tuned.** Detection *rates* are therefore Paper 1's; what is compared here is how fast the server learns of an event.

## 3. Strategies

| Name | Description | Who detects |
|---|---|---|
| `unconf` | every reading, unconfirmed | server, on the readings it receives (a lost reading is a gap) |
| `arq_buffer` | every reading, confirmed, buffer + back-off ≤ 6 h | server |
| `batch1h` | hourly batch, buffer + back-off ≤ 6 h | server |
| `design` (`batch_events`) | `batch1h` + immediate upload when the **node** detector fires; an alarm during an outage probes at once | node; the server learns at arrival |

**Fairness:** the same detector is used everywhere. For strategies that deliver every reading in order, the server's detector fires on the same reading as the node's, at the time all readings up to it have arrived. For `unconf`, the server's detector is actually run on the delivered readings (new segment after a gap > 60 min, as in Paper 1).

## 4. Metrics

1. **Event detection:** the share of injected events the server learns of. An alarm on the event's parameter must occur inside the event (Paper 1's definition), and it must arrive.
2. **Alarm latency:** arrival time of the alarm at the server minus the event onset.
   - Reported as the median and 90th percentile, and as the share of events known within 1 h, 3 h and 24 h of onset.
   - Split by whether the link was up at onset (`up`) or down (`outage`).
3. **Energy:** J/day of transmission, including event uploads and uploads caused by false alarms. Lifetime with Paper 1's floor and the 6600 mAh battery. Alarms per 30 days are reported.
4. **Completeness:** the share of readings delivered.
5. **Real-time picture:** at every scored slot τ, the server shows:
   - the reading for τ if it has arrived by τ;
   - otherwise the latest arrived reading s* plus the site's own diel change, x(τ − 24 h) − x(s* − 24 h), if both of those readings have arrived by τ;
   - otherwise the latest arrived reading.

   Scored on the un-injected series, per parameter: the share of slots with |error| ≤ Paper 1's L2 tolerance (T 0.2 °C, DO 2 %sat, pH 0.1, EC 2% of median), and the median |error|.

## 5. Hypotheses and how they will be judged

Judged on medians over sites, per trace × radio, with Wilcoxon signed-rank tests across sites where a direction is claimed.

- **H1 (link up):** the design's alarm latency is within one slot of `arq_buffer`'s (≈ real time). Plain `batch1h` is slower by about half the batch interval.
- **H2 (energy):** the design's energy is within +10% of `batch1h` (alarm uploads are rare) and at least 1.3× below `arq_buffer`, on every trace × radio.
- **H3 (outages):** for events starting during an outage, all strategies are limited by the outage. The buffering strategies (`arq_buffer`, `batch1h`, design) deliver the alarm after the outage. `unconf` loses events whose alarming readings fall inside the outage.
- **H4 (picture):** the within-tolerance share of the real-time picture under the design is within 5 percentage points of `arq_buffer`'s, for every parameter, on each trace.

**A hypothesis fails if** its stated condition fails for the median site on any trace × radio, unless the failure is explained by a documented, mechanistic reason. That explanation is reported, not used to rescue the claim.

## 6. Known limitations (stated in advance)

- **Injected events are synthetic:** real events, such as storms, are larger and slower.
- **Event types:** the detector's ramp detection is weak (Paper 1).
- **Node off vs network down:** the outage records cannot separate them.
- **Backfill contention and buffer-media failure** are not modelled (`papers/LITERATURE_NOTES.md` §E).
- **Server picture:** uses the simplest diel estimator, not a learned model.

---

## 7. Deviations from the plan (recorded when made)

- **D1 (2026-10-12, after a single-site smoke test, before any multi-site result):** the UVA record is replayed as **system outages = link down**, plus sensor04's **radio losses applied per attempt** (p = 0.0308), instead of "every missing frame = link down".
  - **Reason (mechanistic):** UVA's missing frames are mostly single-frame radio losses, separable from system outages (scoping §2.5b). Replaying them as whole-slot link failures made every retry in that slot fail, which misrepresents ARQ and buffering against radio loss.
  - **Kept as planned:** InWaterSense and Weija keep "every missing slot = link down", because their causes cannot be separated. This is pessimistic for ARQ; it will be stated.
  - **Seeds:** the random seed for radio loss is the site index.
- **D2 (2026-10-12, found after the all-site run):** the eligibility check measured complete-cycle coverage over each site's own record span, not over the calendar year as §1 states.
  - **Effect:** one site, 01473900 (Wissahickon Creek at Fort Washington: 72 days of approved data, 19.7% of the year), was wrongly included.
  - **Fix:** it is excluded and the analysis is rerun on the remaining 30 sites. No other site changes status. Its results files are kept but filtered out (`analyse_design_eval.py`).
- **D3 (2026-10-12, before any bounded-trigger result):** the per-site random seed for the outage offset and radio loss was the site's *position* in the eligible list. Excluding 01473900 (D2) shifted the seeds of later sites, so their stored results no longer matched the current list.
  - **Fix:** the seed is now derived from the **site ID** (a stable integer), and **all strategies are rerun together** with the bounded-trigger variant (Part 2).
  - **H1–H4 are re-judged on the rerun**, and the rerun's numbers supersede those in `DESIGN_EVAL_RESULTS.md` §3. Any change in a verdict will be reported.

---

# Part 2: bounded-error trigger (written 2026-10-12, before implementation and before any result)

**Motivation.** H4 failed for DO and pH. Between hourly uploads, the server's diel estimate leaves Paper 1's L2 tolerance about 8% of the time.

**Variant `design_bounded`** = `design` plus a *bounded-error trigger*:
- The node knows which readings the server holds, because all uploads are confirmed. It recomputes, at each slot, the exact value the server shows (§4.5 estimator: latest delivered reading + own diel change).
- If any parameter's true reading differs from that value by more than its L2 tolerance, the node uploads its buffer **now** (the same bulk upload as an alarm).
- **Pre-fixed choice:** during an outage the trigger does **not** cause extra probes; only detector alarms probe immediately. A drifting estimate would otherwise make the node probe constantly into a dead link.
- Everything else is as in `design` (batch interval 1 h, back-off ≤ 6 h).

**Hypotheses** (same data, links, radios, metrics and median-over-sites rules as Part 1):
- **H5 (picture):** for every parameter on every trace × radio, the within-tolerance share under `design_bounded` is ≥ `arq_buffer`'s − 1 pp. This is the H4 condition tightened from 5 pp to 1 pp, because the trigger is meant to make it hold by construction while the link is up.
- **H6 (energy):** `design_bounded` uses **no more energy than `arq_buffer`** on every trace × radio. Also reported, without a pass rule: its ratio to `batch1h`, and triggered uploads per day.
- **H7 (alarms):** alarm latency with the link up is unchanged: `design_bounded` − `design` ≤ 1 slot (median site).

**Expected limitation, stated in advance:** at loose tolerances relative to the diel range (EC, T) the trigger rarely fires; at tight ones (DO, pH in productive rivers) it may fire most hours. H6 tests whether that stays cheaper than per-reading ARQ.

---

# Part 3: newest-first packing and tolerance sensitivity (written 2026-10-13, before implementation)

**Note on the EC tolerance.** Paper 2 computes the EC tolerance as a share of the **whole-record** median EC. Paper 1 used the **training-period** median. Paper 2 keeps its own definition throughout, for internal consistency; the difference is small and is stated here once.

**Change N: newest-first packing.** In every upload that needs more than one frame, the **first frame carries the newest buffered reading**, plus the oldest others; the remaining frames go in FIFO order.
- **Motivation:** Part 2 finding 4. On SF12 the newest reading waited 247 s for the duty cycle.
- **Consequence:** delivery is then no longer a contiguous prefix, so the node's trigger is rewritten to check each needed reading's arrival directly, exactly as the server's estimator does. Its decisions must be **identical** to the old trigger's whenever delivery is FIFO (tested).
- **Variant:** `design_bounded_nf`.

**Sensitivity S: tolerance levels.** `design_bounded` at Paper 1's **L1** (T 0.1 °C, DO 1 %sat, pH 0.05, EC 1%) and **L3** (T 0.5, DO 5, pH 0.2, EC 5%), besides L2.
- `arq_buffer` and `design` are tolerance-independent in what they send; their pictures are scored at each level.
- **Clean series only** (no injected events): the trigger does not affect alarms (H7). Energies here are therefore the clean-run values for every strategy, so the L2 numbers can differ slightly from the event-averaged H6 numbers.

**Hypotheses:**
- **H8 (newest-first):** on the no-outage link, `design_bounded_nf` is within tolerance at 100% of scored slots for every site, parameter and radio, **including SF12**. Its energy is within ±1% of `design_bounded` (same frames, different order).
- **H9 (sensitivity):** the H5 condition (picture ≥ `arq_buffer` − 1 pp) holds at L1 and L3 for every param × trace × radio.
- **H10 (sensitivity, energy):** the H6 condition (energy ≤ `arq_buffer`) holds at L1 and L3 for every trace × radio.
  - **Stated expectation:** at L1 the trigger fires much more often, so H10 may fail at L1 on some radios. The aim is to find the tolerance at which the design stops being cheaper, not to pass. A failure is reported as the boundary.
- **D4 (2026-10-13, after the H8 result; recorded before the fix):** H8 **failed as pre-registered**. Newest-first packing reached 100% on the no-outage link everywhere *except* 4 slots out of ~84,000 at one site (01467200, 5-min step, SF12; median 1.0 everywhere).
  - **Two implementation defects**, each relative to the stated design, found in those 4 slots:
    1. "Newest" was the newest *buffered slot*, which can be a sensor-gap placeholder. The newest *valid* reading then went into a later frame.
    2. The node's copy of the server treated a reading as available as soon as its upload began. At 5-min sampling an hourly SF12 upload is 4 frames, and with the 1% duty cycle the later frames arrive after one or more following slots have passed.
  - **Fix:** the newest *valid* reading goes first, and the trigger counts a reading as available only once its arrival time has passed.
  - **Scope of the rerun:** only 5-min sites can have uploads that span slots, and 01467200 is the only one evaluated, so only that site is rerun, in both runners. Its pre-fix results are archived.
  - **Reporting:** the pre-registered H8 verdict stays **FAIL**; the post-fix result is reported separately, as post hoc.
  - **D4 amendment (same day, before any rerun result):** the claim "only 5-min sites are affected" was **wrong**.
    - **Why:** after an outage, the backlog upload is long (at SF12, two days of readings ≈ 64 frames with a duty-cycle wait between each), so it spans many slots at *every* site. The old trigger assumed the server had the whole backlog as soon as the upload started.
    - **Checked on 01458500 (15-min):** only `design_bounded` rows on outage links change (energy ≤ +0.46 J/day; picture ≤ 0.4 pp; 2 event rows). Every other strategy is unchanged; the residual differences of ±0.0000 are the 6-significant-digit CSV rounding.
    - **Corrected scope:** **all 30 sites are rerun in both runners.** Pre-fix results are archived in `results/design/pre_D4/` and `results/design/sensitivity/pre_D4/`.

---

# Revision (2026-10-17, after the external Q1 review)

- **D5 (2026-10-17, found while building the confirmatory runner, before any 2024 data were analysed):** a floating-point tie at the tolerance.
  - **What:** pH and T are recorded in 0.1 steps. An error of exactly one tolerance step (pH 0.1; T 0.2 = two steps) is computed as 0.0999…96 or 0.1000…05 depending on the values (7.3 − 7.2 vs 7.4 − 7.3). The main runner (`run_design_eval.py`) scored `|error| <= tol` without slack, so such slots were counted in or out at random; the sensitivity runner (`run_sensitivity.py`) already used `+ 1e-9`. The bounded trigger fired on `|error| > tol`, with the same tie. The reconstruction script (`chain_outage.py`) has the same tie.
  - **Size:** on two sites (01438500, 01463500) the main-run picture scores move by up to 10.5 pp (pH, Batch 1 h) and 2.6 pp (T); energies, latencies and the sensitivity runs are unaffected.
  - **Fix:** one inclusive comparison, `within_tol` in `sitedata.py` (`|error| <= tol + 1e-9`), used for every score and by the trigger (which now fires only beyond the tolerance). Tests: `tests/test_confirm.py`.
  - **Consequence:** all 30 development sites are rerun with `src/confirm/run_confirm.py` (salt 0), every H1–H10 verdict is re-judged, and every verdict change is reported. The v0.1 results stay archived in `results/design/`.
