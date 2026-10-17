# Design evaluation: results (2026-10-12)

*Plan written before running: `DESIGN_EVAL_PLAN.md` (hypotheses, metrics, decision rules; deviations D1–D2 in its §7). Code: `src/design/` (Paper 1's detector and injection copied unchanged; `sitedata.py`, `run_design_eval.py`, `analyse_design_eval.py`). Raw results: `results/design/<site>_{events,energy,picture}.csv`. Summaries: `results/design/summary_*.csv`. Full printout: `results/design/analysis.log`. Tests: 116 pass (`tests/`).*

---

> **Rerun note (deviation D3, 2026-10-13).** The per-site seeds were changed from list position to site ID, and all strategies were rerun together with the bounded-trigger variant (Part 2 below). The numbers in §3 come from the first run, archived in `results/design/v1_superseded_D3/`; the rerun's values are in `results/design/summary_*.csv`.
>
> **Every H1–H4 verdict is identical on the rerun** (H4 fails in the same 19 cells). The largest change in any reported median: latencies 0.19 h; energies 2.3 J/day; ARQ/design energy ratio 0.03; picture shortfall 0.6 pp.

## 1. What was run

**Sites.** 30 USGS sites (2023; 5- to 60-min steps), with all four parameters present in ≥ 50% of the year.
- Excluded: 7 sites with sparse data, 1 with no approved pH, and 1 with only 72 days (01473900; see deviation D2).
- Three lower-Delaware sites are tidal and are reported separately where it matters.

**Links.** Three real outage records, mapped onto each site in physical time (random circular offset per site), plus a no-outage control:
- **InWaterSense** (46% of slots missing);
- **Weija** (≈ 16%);
- **UVA** (system outages ≈ 1%, plus 3.1% radio loss per attempt; deviation D1).

**Radios.** NB-IoT N211 RAI (10-s search), LoRaWAN SF7, LoRaWAN SF12.

**Strategies.**
- `unconf`: every reading, unconfirmed;
- `arq_buffer`: every reading, confirmed + buffer + back-off ≤ 6 h;
- `batch1h`: hourly batches, back-off ≤ 6 h;
- **`design`**: `batch1h` + an immediate upload when the node's detector fires; an alarm during an outage probes at once.

**Events.** Paper 1's injected steps and ramps (5σ and 8σ, 180 min; up to 60 per site and setting, fewer where the test period is short; **6,728** events in all) and Paper 1's frozen CUSUM detector. The same detector is used everywhere: on the node for the design, on the server for the others.

**Node detector** (median share of injected events detected; identical for all strategies that deliver every reading): step 5σ 0.63, step 8σ 0.90, ramp 5σ 0.15, ramp 8σ 0.65. False alarms ≈ 1.4 per parameter per 30 days, so alarms are rare (≈ 0.17 per day per node).

---

## 2. Verdicts on the pre-stated hypotheses

| Hypothesis | Rule | Verdict |
|---|---|---|
| **H1:** link up, the design is as fast as per-reading reporting | design − `arq_buffer` median latency ≤ 1 slot | **Pass, 12/12** trace × radio |
| **H2:** the design costs ≈ batching, and ≥ 1.3× less than per-reading ARQ | design / `batch1h` ≤ 1.10 and `arq_buffer` / design ≥ 1.3 | **Pass, 12/12** |
| **H3:** during outages everyone waits for the link; buffering eventually delivers; `unconf` loses | descriptive | **As expected** |
| **H4:** the design's real-time picture is within 5 pp of per-reading reporting | design − `arq_buffer` within-tolerance ≥ −5 pp, every parameter | **Fail, 29/48.** Fails for **DO and pH** on the UVA, Weija and no-outage links |

---

## 3. Results

### 3.1 Alarm latency when the link is up (H1)

Median over sites of each site's median latency from event onset to the server knowing (hours):

| Link | `unconf` | `arq_buffer` | `batch1h` | **design** |
|---|---|---|---|---|
| none | 1.00 | 1.00 | 1.25–1.32 | **1.00** |
| UVA | 1.00 | 1.00 | 1.44–1.46 | **1.00** |
| Weija | 1.00 | 1.00 | 1.31–1.50 | **1.00** |
| InWaterSense | 1.00 | 1.25 | 1.50–1.61 | **1.00–1.25** |

- The ≈ 1 h is the **detector's own delay**: the CUSUM needs about an hour of evidence. Delivery adds nothing for the design.
- **Hourly batching adds a median of 0.5 h** in every combination (Wilcoxon across sites; largest p = 3 × 10⁻⁶).
- **On InWaterSense the design is a quarter-hour faster than `arq_buffer`.** An alarm probes at once, while `arq_buffer` waits for its back-off schedule when an outage starts during the event.

**Share of all injected events the server knows within 1 h** (LoRaWAN SF7):

| Link | `unconf` | `arq_buffer` | `batch1h` | design |
|---|---|---|---|---|
| none | 0.333 | 0.333 | 0.207 | **0.333** |
| UVA | 0.307 | 0.327 | 0.203 | **0.327** |
| Weija | 0.261 | 0.279 | 0.174 | **0.281** |
| InWaterSense | 0.118 | 0.159 | 0.109 | **0.179** |

The ceiling is the detector's 57% eventual detection (ramps are hard), not the reporting scheme.

### 3.2 Energy (H2)

Median J/day of transmission (InWaterSense / UVA / Weija / no outage):

| Radio | `unconf` | `arq_buffer` | `batch1h` | **design** (with events) | `arq_buffer` / design |
|---|---|---|---|---|---|
| NB-IoT 10-s search | 153 / 54 / 87 / 51 | 46 / 54 / 49 / 53 | 23 / 14 / 15 / 14 | **24 / 14 / 16 / 14** | 1.8–3.9× |
| LoRaWAN SF7 | 42 (all) | 37 / 36 / 32 / 34 | 19 / 10 / 11 / 9 | **19 / 10 / 11 / 9** | 1.9–3.8× |
| LoRaWAN SF12 | 100 (all) | 110 / 115 / 106 / 112 | 77 / 63 / 62 / 60 | **78 / 63 / 63 / 60** | 1.4–1.9× |

**The design costs +0.0–2.0% over plain batching.** Alarm uploads are rare, and most ride on data that would have been sent within the hour anyway.

### 3.3 Events that start during an outage (H3)

Pooled detected events, LoRaWAN SF7:

| Link | n | `unconf` known ever | buffering strategies known ever | known ≤ 24 h (`arq_buffer` / `batch1h` / design) | median latency, h (same order) |
|---|---|---|---|---|---|
| InWaterSense | 1,784 | **0.031** | 0.993 | 0.470 / 0.490 / **0.501** | 27.6 / 24.5 / **22.7** |
| Weija | 592 | **0.052** | 0.995 | 0.341 / 0.353 / 0.353 | 55.0 / 55.3 / 55.3 |
| UVA | 57 | **0.000** | 1.000 | 0.614 / 0.614 / 0.614 | 13.4 / 13.9 / **12.0** |

- **Unconfirmed reporting almost never learns of an event that starts during an outage.** The alarming readings fall inside the outage and are lost.
- **Buffering strategies learn of ~all of them, but only after the outage.**
- The design's immediate alarm probe makes it the fastest of the three on InWaterSense (by 2–5 h) and UVA (by 1.4 h), and ties on Weija (55.3 h vs 55.0 h for `arq_buffer`). **The outage, not the scheme, sets the latency** (median 12–55 h).

### 3.4 The real-time picture between deliveries (H4, failed)

Median share of time the server's shown value is within Paper 1's L2 tolerance (LoRaWAN SF7):

| Link | Param | `unconf` | `arq_buffer` | `batch1h` | design | design − `arq_buffer` (pp) |
|---|---|---|---|---|---|---|
| none | DO | 1.000 | 1.000 | 0.919 | 0.922 | **−7.8** |
| none | pH | 1.000 | 1.000 | 0.922 | 0.922 | **−7.8** |
| none | T | 1.000 | 1.000 | 0.969 | 0.970 | −3.0 |
| none | EC | 1.000 | 1.000 | 0.982 | 0.982 | −1.8 |
| Weija | DO / pH | 0.912 / 0.936 | 0.909 / 0.932 | 0.821 / 0.868 | 0.821 / 0.868 | **−6.7 / −6.2** |
| InWaterSense | DO / pH | 0.768 / 0.843 | 0.728 / 0.806 | 0.689 / 0.770 | 0.692 / 0.776 | −3.8 / −3.1 |

- **Mechanism.** Between hourly uploads the server shows the last value plus the site's own diel change. DO and pH move fastest relative to their tolerances (2 %sat; 0.1 pH), so an estimate up to an hour old leaves tolerance about 8% of the time. T and EC pass.
- **Not a tidal-site artefact.** On the 27 non-tidal sites the shortfalls are DO −7.8 and pH −7.8 pp (no outage).
- **Widespread.** The shortfall exceeds 5 pp at 57% of sites for DO and 77% for pH.
- **Tidal sites** additionally fail EC by about 20 pp (tidal salinity is not diel).
- **A side observation:** under outages, `unconf` shows a *better* picture than `arq_buffer`, for example InWaterSense DO 0.768 vs 0.728. When the link returns, `unconf` delivers at once, while the back-off makes `arq_buffer` wait up to 6 h. The back-off saves energy and costs timeliness right after outages.

**Verdict:** as the plan requires, H4 is reported as **failed** for DO and pH. The design as specified does not keep the real-time picture of the fast parameters as good as per-reading reporting.

---

## 4. What this means

1. **Alarms and energy work as designed.**
   - The design matches per-reading reporting on alarm latency (H1) at the cost of hourly batching (H2): 1.4–3.9× less energy than per-reading ARQ, and 100% of readings delivered.
   - During outages it is the fastest buffering strategy, or tied, though the outage dominates (H3).
2. **The real-time picture of DO and pH is the design's weakness (H4).**
   - A fixed hourly batch hides up to an hour of fast change.
   - The event detector does not help, because these excursions are normal diel motion, not events.
3. **The remedy is Paper 1's mechanism.** A refinement, *not* evaluated here and to be pre-registered separately:
   - the node runs the **same estimator the server uses** (dual prediction);
   - it uploads early whenever the server's picture would leave tolerance;
   - by construction this keeps the picture within tolerance whenever the link is up, at the cost of extra uploads in fast-changing hours.
   - This joins Paper 1's bounded-error suppression to Paper 2's batching and outage handling.
   - **To be tested:** the energy cost, and whether it restores H4.

## 5. Limitations

- **Synthetic events:** injected steps and ramps, 3 h long. Real events, such as storms, differ.
- **Detector:** Paper 1's detector catches ramps poorly, and it is not re-tuned here.
- **Outage records:** InWaterSense and Weija replay every missing slot as link down (pessimistic for ARQ, whose retries cannot help).
- **Not modelled:** node off vs network down; backfill contention; buffer-media failure.
- **Server estimator:** the simplest diel estimator; a learned one might narrow the H4 gap but not remove it for hour-long blind spells.


---

# Part 2: the bounded-error trigger (2026-10-13)

> **Post-D4 note (2026-10-14).** The numbers in Part 2 come from the run before deviation D4 (`results/design/pre_D4/`). After D4 (node's trigger counts only readings that have physically arrived; newest *valid* reading first), all 30 sites were rerun.
> - **H1–H7 verdicts are unchanged.**
> - **Only `design_bounded` changed:** picture ≤ 0.17 pp, energy ≤ 0.09 J/day (median summaries). Every other strategy is identical.
> - The current values are in `results/design/summary_*.csv`.

*Plan: `DESIGN_EVAL_PLAN.md` Part 2, written before implementation. Code: `make_trigger` in `src/design/sitedata.py`; `trigger` hook in `src/energy/loss_handling.py`. Tests: 120 pass, including an end-to-end check that the server picture stays within tolerance at every scored slot when the link is up.*

**What it adds to the design.**
- The node keeps an exact copy of the server's estimator. Uploads are confirmed and the buffer is FIFO, so the node knows exactly which readings the server holds.
- It uploads at once whenever any parameter's true reading differs from what the server is showing by more than the L2 tolerance.
- **Pre-fixed:** the trigger is *not* consulted during an outage. Only detector alarms probe, so a drifting estimate cannot burn energy on a dead link.

## Verdicts

| Hypothesis | Rule | Verdict |
|---|---|---|
| **H5:** picture as good as per-reading reporting | `design_bounded` within-tolerance ≥ `arq_buffer` − 1 pp, every param × trace × radio | **Pass, 48/48** |
| **H6:** no dearer than per-reading ARQ | `design_bounded` energy ≤ `arq_buffer`, every trace × radio | **Pass, 12/12** |
| **H7:** alarm latency unchanged | `design_bounded` − `design` ≤ 1 slot | **Pass, 12/12** (median difference 0 slots) |

## Results

**Real-time picture** (median share of time within tolerance, LoRaWAN SF7 / NB-IoT; `design` → `design_bounded`, with `arq_buffer` in brackets):

| Link | DO | pH | T | EC |
|---|---|---|---|---|
| none | 0.912 → **1.000** (1.000) | 0.921 → **1.000** (1.000) | 0.969 → **1.000** (1.000) | 0.983 → **1.000** (1.000) |
| UVA | 0.902 → **0.992** (0.992) | 0.919 → **0.995** (0.995) | 0.957 → **0.992** (0.992) | 0.978 → **0.995** (0.995) |
| Weija | 0.828 → **0.903** (0.902) | 0.871 → **0.931** (0.930) | 0.848 → **0.875** (0.877) | 0.881 → **0.899** (0.898) |
| InWaterSense | 0.708 → **0.737** (0.738) | 0.766 → **0.795** (0.799) | 0.656 → **0.673** (0.669) | 0.711 → **0.721** (0.715) |

**Energy** (median J/day, with injected events; `design_bounded` vs `batch1h` and `arq_buffer`):

| Link | Radio | `batch1h` | design | **`design_bounded`** | `arq_buffer` | bounded / batch | ARQ / bounded |
|---|---|---|---|---|---|---|---|
| none | NB-IoT | 13.5 | 13.6 | **21.0** | 52.8 | 1.55 | 2.32 |
| none | SF7 | 9.0 | 9.0 | **13.7** | 34.2 | 1.53 | 2.30 |
| none | SF12 | 60.2 | 60.2 | **64.7** | 112.3 | 1.11 | 1.69 |
| Weija | SF7 | 10.7 | 10.8 | **15.0** | 32.1 | 1.39 | 2.01 |
| InWaterSense | SF7 | 18.7 | 19.0 | **22.9** | 36.3 | 1.20 | 1.53 |
| InWaterSense | SF12 | 76.2 | 76.9 | **81.9** | 107.9 | 1.07 | 1.30 |

Across all 12 trace × radio combinations, the bounded design costs **7–55% more than plain batching** and **1.3–2.3× less than per-reading ARQ**.

## Findings

1. **The trigger fixes H4 completely.** The picture matches per-reading reporting for every parameter on every link and radio. With the link up and no radio loss it is within tolerance at 100% of scored slots, for every site and parameter, on SF7 and NB-IoT.
2. **It keeps most of batching's saving.** The bound costs about 4–8 J/day, because the trigger fires mostly in fast-changing daytime hours for DO and pH.
3. **Alarms are unaffected** (H7).
4. **An SF12 detail found by checking a shortfall** (the picture reached 99.7–99.97% instead of 100% with no outage on SF12):
   - At the scheduled hourly upload, a 4-reading batch needs two SF12 frames (3 readings per frame, RP002). The newest reading goes in the second frame and waits 247 s for the 1% duty cycle.
   - At that one slot the server shows the estimate, and the trigger is not consulted, because a scheduled upload is happening anyway.
   - Confirmed on site 01458500: **all 51** out-of-tolerance slots are scheduled-upload slots whose reading waited exactly 247 s.
   - **Design fix:** pack the newest reading into the first frame of every upload. Recorded as a design note, not applied after the fact, because H5 passes without it.
5. **An edge case: hourly sampling.** At Trenton (01463500), which samples hourly, an hourly batch is a single reading. The bounded design and per-reading ARQ therefore cost the same (ratio 1.000 on NB-IoT). Batching gains nothing at a cadence of one hour or slower.

## What this means for the paper

The full design gives, under real outages, on 30 rivers:
- **completeness:** buffer + back-off delivers every reading;
- **alarms:** as fast as sending every reading;
- **a real-time picture:** as good as sending every reading, with Paper 1's bounded-error guarantee while the link is up;
- **energy:** 1.3–2.3× less than per-reading ARQ.

The design combines hourly batching, immediate event uploads, the bounded-error trigger, and buffer + back-off. The one thing it cannot fix is the outages themselves: events that start during an outage are learned of only when the link returns (12–55 h median). That is a property of the network, not the scheme, and a reason to engineer gateway diversity and watchdogs ([56], [59]).


---

# Part 3: newest-first packing and tolerance sensitivity (2026-10-14)

*Plan: `DESIGN_EVAL_PLAN.md` Part 3 (written before implementation) and deviation D4 with its amendment. Code: `src/design/run_sensitivity.py`, `analyse_sensitivity.py`. Results: `results/design/sensitivity/` (clean series, all 30 sites; pre-fix results archived in `pre_D4/`). Tests: 126 pass.*

## Verdicts

| Hypothesis | Rule | Verdict |
|---|---|---|
| **H8:** newest-first makes the bound exact on SF12 | 100% within tolerance on the no-outage link, every site × param × radio; energy within ±1% of FIFO | **FAIL as pre-registered** (4 slots of ~84,000 at one site). **Pass after the D4 fix** (post hoc): min 1.0000 everywhere; energy 0.994–1.002× FIFO |
| **H9:** picture as good as per-reading ARQ at L1 and L3 | `design_bounded` ≥ `arq_buffer` − 1 pp | **Pass**: 48/48 at L1, 48/48 at L3 |
| **H10:** no dearer than per-reading ARQ at L1 and L3 | `design_bounded` energy ≤ `arq_buffer` | **Pass**: 12/12 at L1, 12/12 at L3 |

## H8: what failed, and why

- **The failure.** The first newest-first run was exact everywhere except **4 slots at 01467200** (5-min sampling, tidal, SF12). There are two defects in the implementation, both relative to the stated design:
  1. The "newest" item promoted to the first frame could be a **sensor-gap placeholder**, so the newest *valid* reading rode in a later frame.
  2. The node's copy of the server treated readings as available **as soon as an upload began**. At 5-min sampling an hourly SF12 upload is 4 frames, and with the duty cycle the later frames arrive after the next slots.
- **The fix**, applied before rerunning: promote the newest valid reading, and count a reading only after its arrival time.
- **The fix mattered beyond the 5-min site.** Checking a 15-min site showed that **post-outage backlog uploads span many slots at every site** (at SF12, two days of readings ≈ 64 frames). The old trigger was over-optimistic there too, so all sites were rerun. The effect on results was small (above).
- **Lesson:** the node's copy of the server must model **when** data arrive, not just **whether**.

## Tolerance sensitivity (H9, H10)

Median energy, J/day, LoRaWAN SF7, clean series:

| Level | Link | `arq_buffer` | design (no trigger) | `design_bounded` | bounded / design | ARQ / bounded |
|---|---|---|---|---|---|---|
| **L1** (T 0.1 °C, DO 1 %sat, pH 0.05, EC 1%) | none | 34.2 | 9.0 | 19.9 | 2.20 | 1.48 |
|  | InWaterSense | 36.3 | 18.9 | 28.3 | 1.44 | 1.23 |
| **L2** (T 0.2, DO 2, pH 0.1, EC 2%) | none | 34.2 | 9.0 | 13.5 | 1.49 | 2.33 |
|  | InWaterSense | 36.3 | 18.9 | 22.7 | 1.17 | 1.55 |
| **L3** (T 0.5, DO 5, pH 0.2, EC 5%) | none | 34.2 | 9.0 | 9.9 | 1.10 | 3.28 |
|  | InWaterSense | 36.3 | 18.9 | 19.8 | 1.03 | 1.82 |

**Across all trace × radio combinations:**

| Level | ARQ / bounded | bounded / plain design | Picture vs ARQ |
|---|---|---|---|
| L1 | 1.18–1.48× | 1.18–2.24× | −0.6 to +0.4 pp |
| L2 | 1.31–2.35× | 1.06–1.51× | −0.3 to +0.7 pp |
| L3 | 1.39–3.35× | 1.01–1.10× | −0.1 to +0.3 pp |

**Findings:**
1. **The bound holds at every level** (H9). The node's copy of the server makes the guarantee independent of the tolerance.
2. **The price of the bound grows as the tolerance tightens.** At L1 the trigger roughly doubles the plain design's energy, yet it is still 1.2–1.5× cheaper than per-reading ARQ (H10). At L3 the trigger hardly ever fires (+1–10%).
3. **Without the trigger, tight tolerances are not met.** At L1 the plain design's picture falls short of per-reading reporting by a median 26.5 pp for DO, 19.3 for pH, 6.3 for EC and 5.5 for T. The trigger is what makes batching usable for demanding monitoring.
4. **The trade-off is now explicit and tunable.** The tolerance the operator needs sets the energy, and the design is never worse than sending every reading.

## What this means for the paper

The proposed scheme has four parts:
- hourly batching;
- immediate event uploads;
- a bounded-error trigger that models arrival times, with newest-valid-first packing;
- buffer + back-off through outages.

Its properties, under real outages on 30 rivers:
- **completeness:** every reading delivered;
- **alarms:** as fast as per-reading reporting;
- **real-time picture:** within a chosen tolerance whenever the link is up, at L1, L2 and L3;
- **energy:** 1.2–3.4× less than per-reading ARQ, with the saving set by the tolerance.

**Still not fixable by any scheme:** events and data during outages, which reach the server only when the link returns.
