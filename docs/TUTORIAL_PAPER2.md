# Paper 2 from the ground up: a tutorial

*Written 2026-10-12; updated the same day after the literature reading and method audit (new: UVA network, fair baselines, batching, three more mistakes and their fixes). It assumes you know nothing beyond Paper 1, and even Paper 1's ideas are re-explained where they are needed.*

**How to read it:**
- Read it in order.
- Parts 1–3 build the concepts.
- Part 4 tells the story of what we did and found, including our mistakes.
- Part 5 is the paper in one page.
- Part 6 tests you.
- Parts 7–8 are the glossary and the file map.

**Every number** comes from our own result files or from the model code; the paths are in Part 8. When you can do the exercises in Part 6 without looking, you understand the paper.

---

## Part 1. The problem, in plain words

### 1.1 The setting

- A **water-quality sensor node** sits in a river. Every 10–30 minutes it wakes up, measures temperature (T), conductivity (EC), dissolved oxygen (DO) and pH, and sends the readings to a server by radio. Then it sleeps again.
- The server is where people look: dashboards, alarms ("DO is crashing, fish will die"), and the long-term record used for science and regulation.

### 1.2 What goes wrong

Readings go missing. There are two very different reasons, and **the whole paper is built on the difference**.

1. **Radio loss (short).** One message is lost, for example because two devices transmitted at the same moment and collided, or because of a burst of interference. The next message usually gets through. Typical gap: **one reading**.
2. **System outage (long).** The path to the server is down: a gateway lost power, the mobile network or backhaul failed, a cable or SIM problem. *Every* message fails until someone or something fixes it. Typical gap: **hours to days**.

### 1.3 What can you do about a missing reading?

There are exactly three families of responses.

| Response | What it means | Good at | Bad at |
|---|---|---|---|
| **Retransmit** (ARQ) | The node waits for an acknowledgement ("ACK") and re-sends if none arrives. | Short radio losses | Long outages: re-sending into a dead network fails every time and burns energy |
| **Backfill** (buffer and send later) | The node stores readings it could not deliver, and uploads them when the link returns. | Long outages: the true data arrives, just late | Timeliness: the data is late, sometimes by days |
| **Reconstruct** | The server *estimates* the missing values from what it does have: the same site's past, other parameters, neighbouring sites. | Real-time estimates, short gaps | Accuracy over long gaps: an estimate is not a measurement |

### 1.4 The research question

> **Which response, or which mix, gives the best combination of energy, completeness and timeliness, under the outages that real deployments actually suffer?**

**Why this is a research question and not an engineering detail:**
- **The standard answer is ARQ.** Every textbook protocol does it. But ARQ was designed for short, random losses. Nobody had checked what it does under the long, clustered outages of real low-cost environmental deployments.
- **The reconstruction literature has the opposite blind spot.** It builds clever estimators but tests them on randomly deleted values, and never asks what the radio would have spent to avoid the gap.
- **The proposal we started from** (`../proposals.md`, proposal 2) assumed that neighbouring nodes could repair each other's losses. We tested that assumption properly, and it mostly fails (Part 4).

---

## Part 2. The concepts you need (with tiny examples)

### 2.1 The node and its energy budget

**Parts of the node:**
- a **host** microcontroller (Libelium Waspmote in both of our real deployments);
- the **probes**;
- a **battery**;
- a **radio modem**.

**Energy per day has three parts** (Paper 1's model, which we copied into `src/energy/`):

```
E_day = sleep floor                       (always: ~23 J/day)
      + sensing                            (every reading: host awake ~5 s at 69 mW)
      + transmission                       (what our strategies change)
battery life (years) = battery energy / E_day / 365
```

**Worked example** (from our code, 611-s cadence = 141.4 readings/day):
- Sleep floor: 86,400 s × (0.149 mW radio + 0.122 mW host) = **23.4 J/day**.
- Sensing: 141.4 × 0.0688 W × 5 s = **48.6 J/day**.
- So before sending anything, the node spends **72 J/day**.
- The 6,600 mAh battery holds 6.6 Ah × 3.7 V × 3,600 = **87,912 J**: about 3.3 years if it never transmitted.

Transmission is what we compare.

### 2.2 The two radios

- **LoRaWAN:**
  - You (or a community network) own the gateways.
  - It uses free radio bands (868 MHz in Europe, where our energy measurements come from).
  - The device just transmits; it does not "connect" first.
- **NB-IoT:**
  - It runs on the mobile operator's network (like a phone, but low-power).
  - The modem must find and attach to a cell before it can send.

Both are **LPWAN** (Low-Power Wide-Area Network) technologies: kilometres of range, tiny data rates, years of battery.

### 2.3 LoRaWAN in enough detail to reason about energy

**Spreading factor (SF7 … SF12).** LoRa trades speed for range. Each step up in SF doubles the time a symbol takes. Our code computes the **airtime** (time on air) of a 20-byte message:
- SF7: **72 ms**;
- SF12: **1,810 ms**, 25× longer.

Far or badly placed nodes need high SF, and pay for it in energy.

**Class A receive windows.** After every uplink, the device opens two short listening windows:
- **RX1**, 1 s after the transmission;
- **RX2**, 2 s after, at a fixed slow rate (SF12 in EU868).

The network can only talk to the device in these windows. Listening costs energy (27–38 mA).

**Unconfirmed vs confirmed messages:**
- **Unconfirmed:** no acknowledgement. The device never knows whether the message arrived. It still opens both windows.
- **Confirmed:** the network must send an ACK in RX1 or RX2.
  - If an ACK arrives, the device is done.
  - If none arrives, it waits a random ACK_TIMEOUT (1–3 s) and retransmits, up to **8 attempts**.
  - Every 2 attempts it drops to a slower, longer-range data rate: SF7, SF7, SF8, SF8, …

**A surprise worth understanding.** Our model uses Casals et al.'s measured current traces.
- At **SF7** the ACK comes in RX1, so RX2 is never opened. A confirmed success then costs **0.164 J** of radio energy, *less* than an unconfirmed message (**0.244 J**), which always opens both windows.
- At **SF12** the ACK comes in RX2, and confirmed costs more: **0.858 vs 0.729 J**.

This detail matters later (Part 4.8).

**Duty cycle.**
- European rules (ETSI) let a device occupy the main 868 MHz sub-band for at most **1% of the time**. After a frame of airtime T, it must wait about 99 T.
- A 51-byte SF12 frame (2.79 s on air) forces a **4.6-minute** wait.
- This throttles *backfill*: uploading a big backlog at SF12 takes hours.

**Maximum payload.**
- At SF10–12 a frame carries at most **51 bytes** of application data; at SF9, 115 B; at SF7–8, 222 B. (LoRa Alliance RP002-1.0.3, Table 12; we checked it, and a copy is in `papers/standards/`.)
- At 12 bytes per stored reading, an SF12 backfill frame holds **3 readings**; an SF7 frame holds 18.

### 2.4 NB-IoT in enough detail to reason about energy

- **PSM** (Power Saving Mode): deep sleep, ≈ 10 µW.
- To send, the modem wakes up, synchronises with the cell, sends, and releases the connection.
- **RAI** (Release Assistance Indication) tells the network "release me right after this" (RAI-200) or "after the reply" (RAI-400). With RAI a message costs ~0.31–0.33 J on the SARA-N211 module (Michelinakis 2021, measured on real networks).
- **Payload size barely matters.** 512 bytes cost ~60% more than 20 bytes, never more than double. So bulk backfill is cheap per reading on NB-IoT: one frame holds 42 readings.
- **What happens when there is no network?** The modem searches for a cell and eventually gives up.
  - **No source we hold measures this.** We model it as receive power (222 mW; Sørensen 2021) × search time.
  - We **sweep** the search time over 2.2 s (just the sync time Sørensen measured), 10 s and 60 s, because we do not know it.
  - At 10 s, one failed search, with the host awake, costs **2.9 J**: as much as about **5 successful messages**.
- **Important asymmetry.** NB-IoT *knows* when the network is down, because the attach fails. A LoRaWAN device sending unconfirmed messages can *never* know. This decides which strategies are possible on each radio.

### 2.5 The strategies we compare

**The basic strategies:**

| Code name | What the node does | Radio |
|---|---|---|
| `unconf` | Send every reading once, unconfirmed. Never retry. | Both |
| `unconf_backoff` | Unconfirmed, but when the NB-IoT modem says "no network", back off (below) and **discard** the readings it could not send. The *fair* no-recovery baseline on NB-IoT: no sensible NB-IoT node searches for a network in every slot of a long outage. | NB-IoT |
| `arq` (`arq3`) | Send confirmed; retry up to 8 (LoRaWAN spec default; `arq3` = 3) / 3 (NB-IoT) times; give up. NB-IoT stops at once if the modem reports "no network". | Both |
| `arq_buffer` | As `arq`, but a reading that fails all retries goes into a **buffer**, and the node enters **outage mode**: it sends one small confirmed **probe** per allowed slot. When a probe succeeds, it uploads the buffer in bulk frames (**backfill**). | Both |
| `modem_buffer` | Unconfirmed, but when the NB-IoT modem says "no network", buffer and backfill as above. Radio losses while the network is up go unnoticed. | NB-IoT |
| `checkpointM` | Unconfirmed, but every M-th reading is confirmed. If a checkpoint fails, buffer everything since the last good checkpoint, because the node cannot know which unconfirmed readings arrived. | Both |
| `batch1h`, `batch6h` | **Always** buffer, and upload the buffer every 1 h (6 h) in bulk confirmed frames. If an upload fails, enter outage mode as in `arq_buffer`. Every reading is late by design (up to the batch interval), but bulk frames are cheap per reading. | Both |

**Probe back-off.** Probing every slot during a long outage wastes energy. With **exponential back-off**:
- after the n-th failed probe the node waits min(2ⁿ, K) slots;
- K is the **cap**: we try "probe every slot", K = 1 h and K = 6 h.

**The trade-off:**
- During a long outage of D slots, the node probes about D/K times instead of D times.
- Once the link is back, the node notices only at its next probe, so readings taken in that window arrive late. The extra delay is less than K slots.
- **K is the energy-versus-timeliness knob of the paper.**

Exercise 4 in Part 6 makes you count the probes by hand.

### 2.6 Reconstruction methods (what the server can do alone)

When readings are missing from a gap of H hours, the server can estimate them.

**Real-time methods** (know nothing after the gap began):
- **persist:** repeat the last value.
- **diel:** the last value, plus how much the *same site* changed over the same hours **yesterday**. Rivers have strong day–night ("diel") cycles: sun warms the water; algae make oxygen by day and consume it at night. Yesterday's shape is a strong guess for today's.
- **nb_delta:** the last value, plus how much a **neighbouring site** changed since the gap began (with a fitted lag and slope).
- **diel_nb:** diel, plus only the part of the neighbour's change that *its own* yesterday-pattern does not explain. This is the fair test of "does the neighbour add anything beyond the day–night cycle?".

**Bridging methods** (the first value *after* the gap is also known; possible once the link is back):
- **interp:** a straight line from before the gap to after it.
- **interp_nb:** the line, plus the neighbour's wiggle around its own straight line.

Do not confuse **bridging** with **backfill**. Backfill delivers the *real measured* values (zero error, late). Bridging *estimates* them from the endpoints.

### 2.7 How we judge reconstruction: error and tolerance

- For each simulated gap we compute the **maximum absolute error** over the gap: the worst moment.
- We compare it with Paper 1's tolerance level **L2**: T 0.2 °C, DO 2 % saturation, pH 0.1, EC 2% of the site's median.
- "Within tolerance" means the estimate was never off by more than L2. This is the same guarantee Paper 1's reporting scheme gives, so it is the natural bar.

### 2.8 Statistics you will meet (and why each is used)

1. **Geometric distribution.** Suppose that, once an outage has started, it continues to the next slot with probability q, independently each slot. Then the outage length k (in slots) has
   - P(k) = (1 − q) q^(k−1);
   - mean 1/(1 − q).

   It is **memoryless**: an outage that has lasted 10 slots is as likely to end now as one that just began. This is the "independent loss" (Bernoulli/Gilbert) assumption used by Paper 1 and most papers.
2. **Heavy tails.** Real outages are not memoryless. The longer an outage has lasted, the longer it is likely to go on (a dead gateway stays dead until someone visits). We fit two heavy-tailed models:
   - **Discrete lognormal:** log(length) is roughly bell-shaped, so lengths range over orders of magnitude.
   - **Power law:** P(k) ∝ k^−α.
3. **Why a few long outages hold most of the lost data.** Count *lost slots*, not *outage events*. An outage of length k contributes k lost slots, so the share of lost data in outages ≥ L is
   - Σ_{k ≥ L} k·P(k) / Σ_k k·P(k).

   Long outages are weighted by their length. On InWaterSense:
   - 47% of outage *events* are one slot long, but they hold only 5% of lost slots;
   - outages ≥ 1 day are 1% of events but hold 51% of lost slots.

   This is the same effect as "most passengers are on crowded buses".
4. **AIC** (Akaike Information Criterion) = 2 × (number of parameters) − 2 × (log-likelihood). It measures how well a model fits, with a penalty for extra parameters. **Lower is better**; a difference of more than ~10 is decisive.
5. **Bootstrap confidence interval.**
   - Resample the observed outages with replacement 5,000 times, and recompute the statistic each time.
   - The middle 95% of the results is the interval.
   - It shows how much a number could move with different luck. Our "51%" has interval [29%, 65%], because it rests on only 14 long outages.
6. **Spearman correlation.** Rank-based correlation, robust to extreme values. We use it to test whether a long outage tends to be followed by another long one: +0.27, so yes, outages cluster.
7. **Pre-fitting on a training part.** Lag and slope for neighbour methods are fitted on the first 20% of the year only, and gaps are drawn from the remaining 80%. Fitting and testing on the same data would flatter the method.

---

## Part 3. How the pieces fit: the paper's logic

```
Real deployments lose data in two regimes (Part 4.3-4.5b, four real systems)
   ├─ short radio losses (many, 1 frame)   ──► brief retry, or the server estimates them
   └─ long system outages (few, hours-days) ──► retrying fails and wastes energy;
                                                 only BUFFER + BACK-OFF keeps the data
                                                        │
Energy model (Part 4.6-4.8): buffering costs about the  │
same as not recovering at all (fair baseline);          ▼
hourly BATCHING is 1.3-3.3x cheaper still,     backfilled data arrive LATE
with about the same 1-hour timeliness                   │
                                                        ▼
Between batches and during outages, the SERVER shows an estimate (Part 4.1-4.2):
  - the site's own day-night (diel) pattern is the best real-time estimator;
  - reliable for gaps of up to ~1 h, not for a day;
  - neighbouring river sites add a little for temperature only.
                                                        │
                                                        ▼
Design to build next: batch hourly + send events immediately + diel estimate between
batches + buffer and back off through outages.
```

---

## Part 4. The story: what we did, why, and what we found

### 4.0 Auditing the proposal (do this for every paper)

Proposal 2 said: use InWaterSense's two nodes, 100 m apart; when one suffers a "deep GPRS fade", rebuild its data from the other. We checked every premise against the dataset paper and the data (`PAPER2_SCOPING.md` §1).
- **Node 1 is at a discharge pipe and node 2 is downstream.** They measure different water.
- **Both nodes send through one gateway and one GPRS link.** An outage takes out both at once, so neither can cover for the other. In the data, missing readings co-occur: P(node 2 missing | node 1 missing) = 0.73 vs 0.55 overall.
- **Rain does not cause fades at GPRS frequencies** (it matters above ~10 GHz).
- **Node 2 is plausible for only ~7 weeks;** it fails after 20 June 2015.
- **Even then, node 2 predicts node 1 worse than node 1's own reading from an hour earlier,** for all four parameters.
- **The two "background papers" the proposal cites do not exist** (zero matches in the OpenAlex scholarly database).

**Lesson:** a proposal is a starting hypothesis, not a plan. Ours died on contact with the data, and something better grew from what was left.

### 4.1 Do neighbouring river sites help? First on one pair, then properly

**Data.** The US Geological Survey (USGS) publishes 15-minute water-quality data. We searched for rivers with several stations measuring all four parameters along the same channel, found 9 such "chains" (27 sites, 2023), downloaded and cleaned them.

**First test (one pair, Delaware River, Montague → Frenchtown, ~130 km).**
- We compared the upstream neighbour only against "repeat the last value".
- The neighbour seemed to help DO and pH a lot on day-long gaps.

**The mistake: the diel confound.** "Repeat the last value" is a weak baseline. Both sites share the same day–night cycle, so the neighbour was mostly telling us "it's afternoon now, DO goes up". The target site's *own yesterday* knows that just as well. We added the **diel** baseline, and the DO and pH "spatial gain" vanished.

**Proper test (9 chains, 27 sites, 53–57 site pairs per parameter, 300 gaps per pair and length).** Share of pairs where the neighbour wins, and the median gain:

| Param | Gap | Real time | Bridging |
|---|---|---|---|
| T | 24 h | 72% / +6% | 93% / +23% |
| DO | 24 h | 30% / −9% | 70% / +10% |
| pH | 24 h | 9% / −7% | 38% / −1% |
| EC | 24 h | 23% / −2% | 25% / −2% |

**Reading it:**
- **In real time**, a site's own day–night pattern beats any neighbour for DO and pH. Neighbours help temperature a little. That makes sense: weather (a cold front, a cloudy day) hits both sites and is not periodic.
- **When bridging**, the neighbour's shape helps temperature reliably and DO on some rivers.
- **Conductivity never benefits.** It is driven by local inflows and flow events, not by a shared rhythm.

**Second mistake, caught by a crash.** The script compared the two sites' records *by position* instead of *by timestamp*. That is fine when both start at the same instant (the Delaware sites did, so those results were unaffected), but it is wrong otherwise. We fixed it and re-ran everything. **Lesson:** always align time series by time, and be suspicious when results look too good or crash oddly.

### 4.2 Can reconstruction keep Paper 1's error guarantee?

No, not for long gaps. The share of gaps whose maximum error stays within tolerance falls from ≈ 90% at 1 hour to **≤ 25% at 24 hours, for every method**.

**Consequence:** if the guarantee must survive long outages, only **backfill** (real data, delivered late) can provide it. Reconstruction's job becomes the *interim real-time estimate*.

### 4.3 What real outages look like (InWaterSense and Weija)

**InWaterSense node 1** (Kosovo, 245 days, 10-min slots):
- 46% of slots missing;
- 1,619 outages; median 2 slots, longest 13 days;
- 47% of outages are a single slot, but outages ≥ 1 day hold **51% of lost data (95% CI 29–65%)**.

**Weija** (Ghana, the Prof's deployment, 32.5-min slots):
- the same shape: 71–100% of lost data in outages ≥ 1 day;
- only 42 outages, so it is supporting evidence, not a precise estimate;
- some short gaps are hidden by unmarked interpolation in the received files.

### 4.4 Fitting outage models

**InWaterSense outages, by model** (AIC: lower is better):

| Model | AIC | Share of lost data in outages ≥ 24 h |
|---|---|---|
| Observed | | 0.51 [0.29, 0.65] |
| Geometric (memoryless) | 10,537 | **0.00** |
| Mixture of 2 geometrics | 7,107 | 0.35 |
| **Discrete lognormal** | **6,859** | **0.38** |
| Power law | 6,863 | 0.77 |

**What it tells us:**
- **The memoryless model is rejected.** It is ~3,700 AIC worse and predicts that day-long outages essentially never happen. Any simulator that uses independent losses, as Paper 1 did, misrepresents real deployments.
- **The lognormal matches the whole survival curve** from 1 h to 72 h, and its predicted shares fall inside the bootstrap intervals.
- **Outages cluster.** A long outage is often followed by another (Spearman +0.27).

**But read on: Part 4.5b changes this conclusion.** On a third network (UVA) the lognormal is *not* best. The honest reading is that outages are a mixture of two populations, and no single distribution fits every record.

**So the simulator design is:** model the two regimes explicitly, and replay the *real* delivery records as the main method.

### 4.5 What real radio loss looks like (LoED, LoRaWAN)

**Data.** LoED (London, 9 gateways, 188 days, 5.1 million frames). Every LoRaWAN frame carries a device address and a frame counter, so a jump in the counter means frames were lost.

**Separating the two regimes.** We classified each missing frame:
- **gateway-down** if the device's usual gateways logged nothing in that hour;
- **radio loss** otherwise.

**Results for the 179 well-heard devices:**
- Radio loss is **9.6%**.
- **84% of loss bursts are one frame; 99% are ≤ 5.**
- The gateways that logged continuously for 130 days had **zero** down hours.

**Third mistake: the sample artefact.** On a 6-day sample, losses seemed to hit several devices at the same minute 14× more often than chance. On the full data the excess disappears: 19.2% observed vs an 18.2% baseline. The sample's baseline was distorted by shifting losses onto days that weren't in the sample. **Lesson:** never conclude from a convenience sample when the full data are available.

**So:** LoRaWAN radio loss is the **short regime**, and the long outages of Part 4.3 are a **different regime**. That difference drives everything that follows.

### 4.5b A third real network, and a bug in our own statistics (UVA LoRaWAN)

**Data.** University of Virginia campus (Nikseresht et al., BuildSys 2025):
- 10 sensors sending every 5 minutes;
- 3 gateways;
- 16 months;
- frame counters, plus a weather station.

The operators ran it continuously, so a gap is a real outage (unlike LoED's campaign windows).

**The three causes, separated:**
- **System:** no sensor at all reached the database.
- **Gateway:** all of a sensor's gateways were silent.
- **Radio:** anything else.

**Results:**
- Loss is 4.5%. **72% of missing frames are radio losses** (89% of runs are a single frame; none lasts an hour).
- **28% come from just 12 system outages** (median 1.7 h, longest 82 h). 83% of system down-time is in outages ≥ 1 day: the same two regimes again, in a well-run network.
- **Gateway C was down for 30 days without losing a single frame,** because every sensor had a second gateway. **Gateway diversity masks gateway outages.**
- **Rain:** link loss 9.18% dry vs 9.21% in rain (18 pairs, p = 0.64). The proposal's rain premise is not supported.

**Fifth mistake: a numerical bug in the lognormal fit.**
- The code divided two probabilities that both underflow to zero at extreme parameter values. With "safety" clipping, the optimiser found a fake "perfect" fit (AIC 4).
- We rewrote it with log-tail probabilities, added tests, and refitted everything.
- The InWaterSense and Weija results were **unchanged**, because their fits had never gone near the broken region.
- On UVA, the **two-type mixture** fits best (AIC 32,966 vs lognormal 33,327).
- **Lesson:** when a statistic looks too good, suspect the code before believing the data.

**Revised conclusion:**
- No single distribution fits all records.
- Every record rejects the memoryless model.
- Model the two regimes explicitly.

### 4.6 The energy model: what each strategy costs

Our code replays a real delivery record slot by slot.
- A missing slot is "link down".
- Optionally, i.i.d. radio loss is added on top (9.6%, from LoED).

For every attempt, the code charges its energy:
- LoRaWAN: Casals' measured states;
- NB-IoT: Michelinakis' measured message costs and our swept search cost;
- plus host-awake time.

It tracks every reading: on time, late (with its delay), or lost. **68 unit tests** check the accounting, including:
- every reading is counted exactly once;
- exact delays in a constructed outage;
- a hand-worked checkpoint case;
- the duty-cycle drain;
- Paper 1's energy tests, which show that the copied model still reproduces its sources.

**Worked example 1** (check it yourself; the numbers are from the code): LoRaWAN SF7, InWaterSense record, `unconf`.
- Each attempt costs 0.436 J (radio + host awake).
- 141.4 readings/day × 0.436 J = **61.6 J/day**, and 46.1% of readings are lost.
- Battery life = 87,912 / (72.0 + 61.6) / 365 = **1.80 years**.

**Worked example 2.** The same, with `arq`. A reading sent while the link is down fails all 8 attempts, with the data rate slowing every 2 attempts, for **6.45 J** in total.
- Up slots: 0.539 × 141.4 × 0.356 J = 27.1 J/day.
- Down slots: 0.461 × 141.4 × 6.45 J = 420 J/day.
- Total **447 J/day**: battery life 0.46 years, and *still 46.1% lost*.

### 4.7 The results (after the audit of 2026-10-12)

**InWaterSense record, no extra radio loss, back-off cap 6 h where it applies.** "Within 1 h" is the share of *all* readings that reached the server within an hour.

| Radio | Strategy | J/day | Life (y) | Within 1 h | Delivered |
|---|---|---|---|---|---|
| NB-IoT, 10-s search | unconf | 229.9 | 0.83 | 0.54 | 54% |
| NB-IoT, 10-s search | **unconf_backoff** (fair baseline) | **59.5** | 2.02 | 0.47 | 47% |
| NB-IoT, 10-s search | arq_buffer | 63.8 | 1.95 | 0.53 | **100%** |
| NB-IoT, 10-s search | **batch1h** | **23.6** | **2.88** | 0.52 | **100%** |
| LoRaWAN SF7 | unconf (fair baseline) | 61.6 | 1.80 | 0.54 | 54% |
| LoRaWAN SF7 | arq (8 attempts) / arq3 | 447.1 / 175.5 | 0.46 / 0.97 | 0.54 | 54% |
| LoRaWAN SF7 | arq_buffer | 52.7 | 1.93 | 0.53 | **100%** |
| LoRaWAN SF7 | **batch1h** | **18.9** | **2.65** | 0.52 | **100%** |

**The findings, over every configuration we ran:**
1. **ARQ is the wrong tool under real outages.** On LoRaWAN it costs 2.6–7.4× the energy (8 attempts) or 1.5–2.9× (3 attempts), and recovers only the short radio losses, none of the outages.
2. **On NB-IoT, back-off is where the energy is won.** Searching for the network in every slot of an outage costs 1.2–6.5× more than backing off.
3. **Buffering buys completeness cheaply.** Against the *fair* baseline, buffer + back-off delivers 100% for −15% to +26% energy, depending on the radio (cheapest at LoRaWAN SF7, dearest at SF12).
4. **Hourly batching is the efficient design for routine data.** It delivers 100% using 1.3–3.3× less energy than the fair per-reading baseline, and gets about the same share of readings to the server within an hour (−3 to +7 percentage points). Under real outages, **the outages, not the reporting scheme, cap timeliness**, as long as the batch interval is about an hour.

**What's left to trade is the timeliness of individual readings (minutes vs up to an hour). That matters only for alarms.** Hence the design the paper will build and test:
- batch routine data hourly;
- send events immediately (Paper 1's detector);
- show the site's own diel-model estimate between batches (reliable for gaps of an hour or less: Part 4.2);
- buffer and back off through outages.

### 4.8 Mistakes four, six and seven: the energy results we had to correct

**Fourth: the SF12 overclaim** (caught while first writing this tutorial).
- We first said buffering uses less energy than `unconf` "on both radios". That is false at LoRaWAN SF12.
- At SF7, part of the advantage comes from **cheap confirmed messages** (the ACK arrives in RX1, so RX2 is skipped).

**Sixth: a strawman baseline** (caught in the audit).
- On NB-IoT, `unconf` searched for the network in every slot of an outage, which no sensible node does.
- Against the fair `unconf_backoff`, buffering is *not* cheaper; it costs a little more and recovers everything.
- The big NB-IoT saving we had credited to buffering was really **back-off**.

**Seventh: two simulator bugs** (caught by checking numbers that looked odd).
- **Batching's back-off was reset by every failed probe,** so the node never really backed off. LoRaWAN batching first came out at 258 J/day. Fixed; a regression test now checks every buffering strategy.
- **End of record:** readings a node had not yet uploaded when the record *happened to end* were counted as lost. This showed up as an unexplained 1.7% loss. Now the node may finish its upload if the link is up at the end.

**Lessons:**
- Compare against the **strongest fair baseline**, not a convenient one.
- When a result looks too good or too strange, **find the mechanism** before believing it.
- Every fix gets a test that would have caught it.

---

### 4.9 Testing the design (and an honest failure)

**What was tested.** The design (hourly batches + an immediate upload when the node's event detector fires + buffer and back-off) against per-reading unconfirmed, per-reading ARQ + buffer, and plain hourly batching:
- 30 river sites, 3 real outage records, 3 radios, 6,728 injected events;
- Paper 1's detector everywhere.

**Written down first.** The plan (`docs/DESIGN_EVAL_PLAN.md`) was written *before* running: four hypotheses, each with a pass/fail rule. Two later corrections are recorded in it as deviations:
- **D1:** UVA's radio losses are now replayed per attempt;
- **D2:** a site with only 72 days of data had been wrongly included.

**Results:**
- **H1 passed.** With the link up, the design learns of events as fast as sending every reading (≈ 1 h, which is the detector's own delay). Plain batching is 30 min slower.
- **H2 passed.** The design costs only 0–2% more than plain batching, and 1.4–3.9× less than per-reading ARQ.
- **H3 (outages).** If an event starts during an outage, everyone waits for the link (12–55 h median). Unconfirmed reporting almost never finds out; buffering always does, eventually.
- **H4 FAILED** for DO and pH. Between hourly uploads, the dashboard's estimate of these fast-moving parameters leaves tolerance ~8% of the time, vs ~0% when every reading is sent.

**Lessons:**
- **A pre-registered failure is a result, not an embarrassment.** It tells us exactly what to fix: the node should upload early whenever the server's estimate would go out of tolerance. That is Paper 1's bounded-error idea, so the two papers' mechanisms fit together.
- **Check eligibility rules against their exact wording** (D2).

### 4.10 Fixing the failure: the bounded-error trigger

**The idea** (Paper 1's, reused):
- Because every upload is confirmed, the node knows exactly what the server has received. So it can compute exactly what the dashboard is showing at this moment.
- If any true reading differs from that by more than the tolerance, the node uploads now.
- While the link is up, the dashboard can therefore never be out of tolerance.

**It was pre-registered first** (`docs/DESIGN_EVAL_PLAN.md` Part 2), with three hypotheses, and all passed:
- **H5:** the picture is as good as sending every reading, for every parameter on every link and radio.
- **H6:** it still uses 1.3–2.3× less energy than per-reading ARQ. It costs 7–55% more than plain batching, because the trigger fires in fast-changing daytime hours.
- **H7:** alarms are just as fast.

**Two things found by checking numbers that looked slightly off:**
- **SF12 shortfall.** On SF12 the picture reached 99.7–99.97%, not 100%.
  - A 4-reading hourly batch needs two SF12 frames, and the newest reading, in the second frame, waits 247 s for the duty cycle. All 51 shortfall slots at the test site were exactly these.
  - The fix is to send the newest reading first.
- **Hourly sampling.** At an hourly-sampling site, an hourly batch is one reading, so batching saves nothing there.

**The reproducibility fix (D3).** Seeds had depended on each site's position in a list, so removing one site changed the others. They now come from the site ID, and everything was rerun. Every earlier verdict stayed the same.

### 4.11 Newest-first packing, a pre-registered failure, and tolerance sensitivity

**Newest-first.** In multi-frame uploads, the newest reading now rides in the first frame, so it does not wait for the duty cycle.
- **First result:** exact everywhere except 4 slots at one 5-min site. As pre-registered, that is a FAIL.
- **Two defects, found in those slots:**
  - the "newest" item was sometimes a sensor-gap placeholder;
  - the node assumed the server had a reading as soon as its upload *began*, but long uploads under the duty cycle arrive slots later. This is worst after outages, when the backlog is big, and that happens at every site.
- **After fixing both and rerunning all sites:** exact everywhere (reported as post hoc).
- **Lesson:** a node's copy of the server must model *when* data arrive, not just *whether*.

**Tolerance sensitivity.** The bound holds at Paper 1's tight L1 and loose L3 too. Its price depends on the tolerance:

| Level | Bounded design vs per-reading ARQ |
|---|---|
| L1 (tight) | 1.2–1.5× cheaper |
| L2 | 1.3–2.3× cheaper |
| L3 (loose) | 1.4–3.4× cheaper |

Without the trigger, a tight tolerance is badly missed (L1: DO −26.5 pp, pH −19.3 pp). **The operator's tolerance sets the energy, and the design is never worse than sending every reading.**

## Part 5. The paper in one page

**Working title:** *Retransmit, Backfill or Reconstruct? Loss Handling for River Water-Quality Telemetry under Real Outages*

**Problem.** Low-cost river-monitoring nodes lose data in two regimes:
- **short radio losses:** LoRaWAN ~5–10%, 84–89% single frames;
- **long system outages:** gateway, back-end, power or connectivity failures, holding about half of all lost data in outages ≥ 1 day on InWaterSense.

Protocol theory, imputation benchmarks and Paper 1 all assume the first regime. Practitioners have reported the second (Le Dinh 2007; Puluckul & Weyn 2025; Kyrgyzstan 2025), but nobody has measured it or compared remedies.

**Contributions:**
1. **Real-outage characterisation** from 4 systems (InWaterSense, Weija, LoED, UVA).
   - Two regimes; the memoryless model is rejected on every record; no single distribution fits all.
   - Gateway diversity masks gateway outages; rain has no effect on sub-GHz link loss.
2. **Energy, completeness and timeliness of the remedies** (trace-driven, measured radio energy):
   - ARQ costs 1.5–7.4× and recovers nothing of the outages;
   - back-off is where NB-IoT energy is won;
   - buffer + back-off delivers 100% for −15% to +26% energy vs the fair baseline;
   - **hourly batching delivers 100% at 1.3–3.3× less energy with about the same 1-h timeliness**.
3. **A design** (to be built and evaluated): hourly batching, immediate event reports, a diel-model real-time estimate between batches, and buffer + back-off through outages.
4. **Spatial reconstruction on rivers** (9 chains, 27 sites):
   - in real time, a site's own diel model beats neighbours for DO and pH;
   - neighbours help temperature;
   - no method keeps the bound at 24 h;
   - **naive tests overstate spatial value** (the diel confound).
5. **Open code, data pointers and tests.**

**Target:** IEEE Internet of Things Journal (to confirm with the Prof).

**Honest limitations:**
- **Node off vs network down:** the water-quality records cannot separate them, so 100% delivery is an upper bound (UVA does separate the causes).
- **NB-IoT search energy:** unmeasured; it is swept.
- **Batching's advantage** depends on the bulk-frame energy models; state them.
- **LoED** devices belong to third-party networks.
- **USGS:** one year of data.
- **Event (alarm) latency:** not yet evaluated.

---

## Part 6. Test yourself (answers below; try first)

1. A colleague says: "Our LoRaWAN nodes lose 46% of readings, so let's turn on confirmed messages." What happens to battery life and to the loss? What would you recommend instead?
2. Why can an NB-IoT node use `modem_buffer` and `unconf_backoff`, but a LoRaWAN node cannot?
3. In a geometric outage model with q = 0.9, what is the mean outage length? What fraction of outages last ≥ 10 slots? Why does this model fail on InWaterSense?
4. An outage lasts 100 slots. With back-off cap K = 8, how many probes are sent (the first failure enters outage mode at slot 0; probes after waits of 2, 4, 8, 8, …)? Without back-off?
5. Why did the neighbouring site look so useful for DO in our first test, and what control removed the illusion?
6. Why is a confirmed LoRaWAN message cheaper than an unconfirmed one at SF7, but dearer at SF12?
7. Why can't reconstruction keep Paper 1's error bound through a 24-hour outage, while backfill can?
8. The "51% of lost data in outages ≥ 1 day" has a 95% interval of [29%, 65%]. Why so wide, and how should you say it in a meeting?
9. Why was comparing buffering on NB-IoT against `unconf` unfair, and what did the fair comparison show?
10. Hourly batching sends nothing "on time", yet gets about the same share of readings to the server within an hour as sending every reading. How can that be?
11. Gateway C at UVA was down for 30 days but no frames were lost. Why, and what does it suggest for a river deployment?
12. When is ARQ the right tool?

**Answers:**
1. Battery life falls from 1.80 to 0.46 years (8 attempts; 0.97 with 3), and the loss stays at 46.1%. The losses are mostly outages, and retrying into a dead network fails. Recommend hourly batching with buffer + back-off: 100% delivered, 2.65 years at SF7, with about the same share of readings within an hour.
2. Because only the NB-IoT modem learns that the network is down (the attach fails). A LoRaWAN transmitter gets no feedback without ACKs, so it cannot know when to back off or what to buffer.
3. Mean = 1/(1 − 0.9) = 10 slots. P(k ≥ 10) = q⁹ = 0.39. It is memoryless, so it predicts almost no outages lasting days. Real outages are heavy-tailed: geometric AIC is ~3,700 worse, and it predicts 0% of lost data in ≥ 1-day outages vs 51% observed.
4. Probes at slots 1, 3, 7, then every 8 slots from 15 to 95 (11 probes): **14 probes**. Without back-off: 99 probes, one per slot. Extra delay after the link returns: under 8 slots.
5. Both sites share the day–night cycle, and the baseline ("repeat the last value") ignored it. The target's own **diel** pattern (yesterday's change over the same hours) captured the cycle, and the neighbour's apparent gain for DO and pH disappeared.
6. At SF7 the ACK arrives in RX1, so the device skips RX2; an unconfirmed message always listens in both windows. At SF12 the ACK comes in RX2, after a longer, dearer exchange.
7. Reconstruction *estimates*, and over 24 h rivers drift beyond the tolerance (≤ 25% of gaps stay within L2, whatever the method). Backfill delivers the *measured* values, so the error is zero; they are just late.
8. It rests on only 14 long outages, so a few more or fewer would move it a lot. Say "about half (between roughly 30% and 65%) of the lost data".
9. `unconf` searched for the network in every slot of an outage; no sensible node does that. The fair baseline `unconf_backoff` backs off and discards what it can't send. Against it, buffering costs slightly *more* energy (−5% to +15%) but recovers every reading. The big saving we had credited to buffering was back-off.
10. Under real outages, the readings that miss the 1-hour mark are mostly those caught in outages, and no scheme can deliver those quickly. When the link is up, a batch arrives within the hour anyway. So timeliness is capped by the outages, not by sending every reading. Bulk frames are much cheaper per reading, hence the 1.3–3.3× saving.
11. Every sensor was heard by two gateways, so the other gateway covered the outage. For rivers: if two gateways can hear a node, gateway failures stop costing data, and only back-end (system) outages and radio losses remain.
12. For **short, random losses** while the link is up (LoRaWAN's ~10% single-frame losses). Hence the design: confirm and retry briefly, but **stop and buffer** when retries fail, because that signals an outage.

---

## Part 7. Glossary

| Term | Meaning |
|---|---|
| ACK | Acknowledgement: the receiver's "got it" message |
| AIC | Akaike Information Criterion; model fit with a penalty for parameters; lower is better |
| ARQ | Automatic Repeat reQuest: retransmit until acknowledged or out of attempts |
| Backfill | Upload of buffered readings after an outage ends |
| Back-off (exponential) | Waiting 2, 4, 8, … slots (capped at K) between probes during an outage |
| Bootstrap | Resampling the data with replacement to estimate uncertainty |
| Batching | Holding readings and uploading them together every B hours in bulk frames |
| Bridging | Estimating a gap using values both before and after it |
| Checkpoint | A periodic confirmed message in an otherwise unconfirmed stream |
| Diel | Day–night (24-hour) cycle |
| Duty cycle | Maximum share of time a device may transmit (1% in the EU 868 MHz sub-band) |
| ETSI | European telecom standards body; sets the duty-cycle rule |
| Fair baseline | The strongest sensible alternative without the feature being tested (e.g. `unconf_backoff` on NB-IoT) |
| Gateway | LoRaWAN receiver that forwards frames to the network server |
| Gateway diversity | A node heard by more than one gateway, so one gateway's outage loses no data |
| Heavy tail | Long events are much more common than a memoryless model predicts |
| LoED | LoRaWAN-at-the-Edge Dataset (London; Zenodo 10.5281/zenodo.4121430) |
| LPWAN | Low-Power Wide-Area Network (LoRaWAN, NB-IoT, LTE-M) |
| Memoryless | Future duration does not depend on how long something has lasted (geometric) |
| NB-IoT | NarrowBand IoT: low-power cellular IoT on operator networks |
| Outage (system) | Path to the server down; every message fails until it is fixed |
| PSM | Power Saving Mode: NB-IoT deep sleep |
| RAI | Release Assistance Indication: lets an NB-IoT modem release the connection early |
| Radio loss | A single message lost while the path is up (collision, interference) |
| RX1 / RX2 | The two LoRaWAN Class A receive windows after an uplink |
| SF | Spreading factor (7–12): higher = longer range, slower, more energy |
| Spearman ρ | Rank correlation |
| Tolerance L2 | Paper 1's error bound: T 0.2 °C, DO 2 %sat, pH 0.1, EC 2% |
| USGS | US Geological Survey; source of the river-chain data |

---

## Part 8. Where everything is (all paths relative to `Paper2/`)

| What | Where |
|---|---|
| Full scoping report (every number, every correction) | `PAPER2_SCOPING.md` |
| Literature notes (paper cards, gap table) | `papers/LITERATURE_NOTES.md` |
| Literature files, reading order, manual-download list | `papers/README.md`, `papers/pdf/`, `papers/txt/` |
| LoRaWAN regional parameters (payload table) | `papers/standards/` |
| River-chain test | `src/scoping/chain_outage.py`, `chain_summary.py` → `results/scoping/chain_*.csv` |
| Outage models | `src/scoping/outage_models.py`, `outage_tail_check.py` → `results/scoping/outage_models.csv` |
| Real outage records | `src/scoping/weija_outages.py`; InWaterSense in `inws_two_node.py` |
| LoRaWAN loss: LoED | `src/scoping/loed_full.py` → `results/scoping/loed_full*.{log,csv}` |
| LoRaWAN loss: UVA (system / gateway / radio; rain) | `src/scoping/uva_loss.py` → `results/scoping/uva_loss*.{log,csv}` |
| Energy model (copied from Paper 1) + loss handling | `src/energy/model.py`, `params.py`, `loss_handling.py` |
| Strategy comparison | `src/energy/run_loss_handling.py` → `results/scoping/loss_handling.csv`, `loss_handling_summary.txt`, `loss_handling_fair_comparison.csv` |
| Tests | `tests/` (run `python -m pytest tests -q` from `Paper2/`; 90 pass) |
| Data | `data/clean/` (USGS, InWaterSense, Weija), `data/weija_raw/`, `data/loed_full/`, `data/uva_lorawan/` |
| Packages | `requirements.txt` |

**Still open:**
- **The Prof's sign-off on the scope**, then drafting.
- **NB-IoT no-network search energy** (a source or a measurement).
- **Read in full:** Azari et al. 2019 (NB-IoT latency–energy), and Huang/Nadeem (policy structure).
- **Download** the remaining deployment papers (`papers/README.md`).
- **Decide** the scope and venue with the Prof.
