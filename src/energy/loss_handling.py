"""Trace-driven model of loss-handling strategies: energy, delivery and delay (Paper 2).

Builds on the Paper 1 energy model (model.py, params.py, copied unchanged). Time is slotted at the
reporting cadence; the node produces one reading per slot (periodic reporting).

Inputs per run
  link[t]   True if the network path is up in slot t (system outages = False), e.g. a real record
  p_radio   probability that a single attempt is lost although the link is up (i.i.d. per attempt)
Strategies
  unconf        one unconfirmed attempt per reading; nothing else (server reconstructs gaps)
  arq           confirmed; up to R attempts per reading; give up after R (reading lost)
  arq_buffer    as arq, but a reading that fails R attempts is buffered and the node enters outage
                mode: one confirmed probe per slot (carrying the newest reading). When a probe
                succeeds, the buffer is uploaded in bulk frames (confirmed, up to R attempts each).
  unconf_backoff  NB-IoT only: unconfirmed; when the modem reports 'no network' the node backs off its
                attempts exactly as the buffering strategies do, but DISCARDS the readings it could not send
                (no buffer). Separates the energy saved by back-off from the cost and value of buffering.
  modem_buffer  NB-IoT only: unconfirmed live readings; the modem reports 'no network' when the
                link is down, so those readings are buffered and backfilled as in arq_buffer.
                Radio losses while the link is up stay undetected (as with unconf).
  batch         reference for the energy-delay trade-off: the node always buffers and uploads its buffer
                every M slots in bulk confirmed frames (M = M_check). A failed upload enters outage mode:
                single-attempt probes with back-off, then drain, exactly as arq_buffer. Late by design.
  batch_events  the proposed design: batch (as above) PLUS an urgent upload when the node's event
                detector fires (`urgent[t]` True): the whole buffer, including the alarming reading, is
                drained at once in confirmed bulk frames. During an outage, an alarm triggers an
                immediate probe regardless of the back-off schedule (which it does not reset).
  checkpoint    unconfirmed live readings + every M-th reading confirmed. If a checkpoint fails R
                attempts, the node buffers every reading since the last successful checkpoint (it
                cannot know which unconfirmed ones arrived) and enters outage mode as in arq_buffer.
                Re-sent readings that had arrived are duplicates (counted, deduplicated by the server).

Outage-mode probing (all buffering strategies): probe_cap = 1 probes every slot. With probe_cap = K > 1
the node backs off exponentially: after the n-th failed probe it waits min(2^n, K) slots before the
next one; readings in skipped slots are only buffered (no radio energy). The first probe after the
link returns ends the outage; the extra delay is at most K slots.

Energy per attempt (J), each with its source
  NB-IoT (Michelinakis 2021 + Sorensen 2021):
    success, unconfirmed: e_report (RAI-200);  success, confirmed: e_report_ack (RAI-400)
    attempt while the link is DOWN: the modem searches for a cell: P_RX * T_SEARCH,
      P_RX = 0.222 W (N211, Sorensen Table X); T_SEARCH is not measured in any source we hold:
      RANGE, swept (default 10 s; 2.2 s = Sorensen sync time is the optimistic bound)
    attempt lost to radio while the link is up: cost of a normal attempt
    bulk frame of B bytes: e(20 B) * (1 + 0.6 * (B - 20) / 492) for B <= 512 (RAI: 512 B costs
      ~60% more than 20 B, never > 100%; Michelinakis Sec. VI); frames are capped at 512 B
  LoRaWAN (Casals 2017; LoRaWAN spec via Casals Sec. 3.3.2):
    unconfirmed attempt (any outcome): e_unack, both receive windows open
    confirmed success: e_ack;  confirmed failure: e_unack + ACK_TIMEOUT (uniform 1-3 s, mean 2 s)
      at the wait current 27.0 mA (Casals: I_ACK_TO = I_w1w)
    retransmission data rate: attempts 1-2 at the configured SF, 3-4 at SF+1, ... (max SF12)
    max application payload per frame, EU868: 51 B at SF10-12 (DR0-2), 115 B at SF9 (DR3), 222 B at
      SF7-8 (DR4-5): N in LoRa Alliance RP002-1.0.3 Table 12 (repeater compatible; verified 2026-10-11,
      papers/standards/). Without a repeater Table 13 allows 242 B at SF7-8; we keep the conservative 222.
    duty cycle 1% (ETSI, sub-band 868.0-868.6 MHz; Casals Sec. 3): after a frame of airtime T,
      the next frame waits 99 T. This delays backfill; it does not add energy (node sleeps).
  Host (Waspmote) awake during every attempt: P_HOST_ON * active time (as in Paper 1).
Reading size in a backfill frame: READING_BYTES = 12 (4 parameters x 2 B + 2 B time offset +
  2 B sequence) plus FRAME_OVERHEAD = 4 B; a live report is 20 B (Paper 1 default). Design choice.
"""
from dataclasses import dataclass, field
import math

import numpy as np

from . import model as M
from . import params as P

P_RX_N211 = 0.222134          # W, Sorensen 2021 Table X
T_SEARCH_DEFAULT = 10.0       # s, RANGE (see module docstring)
ACK_TIMEOUT_MEAN = 2.0        # s, uniform 1-3 s (Casals Sec. 3.3.2)
I_WAIT_MA = 27.0              # mA during ACK_TIMEOUT (Casals: = I_w1w)
LIVE_BYTES, READING_BYTES, FRAME_OVERHEAD = 20, 12, 4
LORA_MAX_APP = {7: 222, 8: 222, 9: 115, 10: 51, 11: 51, 12: 51}
NB_MAX_FRAME = 512


@dataclass
class Radio:
    name: str
    t_search: float = T_SEARCH_DEFAULT
    # revision options (defaults reproduce v0.1 exactly):
    # scale (review C7 substitute): multipliers on measured energy components, for uncertainty propagation:
    #   'lora_unack', 'lora_ack', 'lora_timeout', 'nb_unack', 'nb_ack', 'nb_search', 'nb_bulk', 'host'
    # dr_step (review M7): False = retransmissions keep the configured spreading factor
    scale: dict = field(default_factory=dict)
    dr_step: bool = True

    def _s(self, k):
        return self.scale.get(k, 1.0)

    def _sf(self, attempt_no, confirmed):
        if confirmed and self.dr_step:
            return min(12, self.sf + (attempt_no - 1) // 2)
        return self.sf

    def __post_init__(self):
        self.nb = self.name.startswith("NB-IoT")
        self.prof = M.radio(self.name)
        if not self.nb:
            self.sf = int(self.name.split("SF")[1])

    # ---- energies (J) of one attempt, radio + host awake time
    def _host(self, seconds):
        return P.P_HOST_ON * self._s("host") * seconds

    def attempt(self, confirmed, ok, link_up, nbytes=LIVE_BYTES, attempt_no=1):
        """Energy of one transmission attempt."""
        if self.nb:
            if not link_up:                                  # cell search, then give up
                return P_RX_N211 * self._s("nb_search") * self.t_search + self._host(self.t_search)
            base = self.prof["e_report_ack"] * self._s("nb_ack") if confirmed else self.prof["e_report"] * self._s("nb_unack")
            scale = 1 + 0.6 * self._s("nb_bulk") * (min(nbytes, NB_MAX_FRAME) - 20) / 492 if nbytes > 20 else 1.0
            return base * scale + self._host(self.prof["t_conn"])
        sf = self._sf(attempt_no, confirmed)
        payload = max(1, nbytes)
        e_unack = M.lora_report_energy(sf, payload) * self._s("lora_unack")
        t_act = M.lora_active_s(sf, payload)
        if not confirmed:
            return e_unack + self._host(t_act)
        if ok:
            return M.lora_report_energy(sf, payload, confirmed=True) * self._s("lora_ack") + self._host(t_act)
        e_to = I_WAIT_MA * 1e-3 * P.V_LORA * ACK_TIMEOUT_MEAN * self._s("lora_timeout")
        return e_unack + e_to + self._host(t_act + ACK_TIMEOUT_MEAN)

    def airtime_s(self, nbytes, attempt_no=1, confirmed=True):
        if self.nb:
            return 0.0
        sf = self._sf(attempt_no, confirmed)
        return M.lora_frame_ms(sf, nbytes) / 1e3

    def retry_gap_s(self, nbytes, attempt_no):
        """Seconds from the start of a failed confirmed attempt to the start of the next one (review C2).
        LoRaWAN: the node is busy until RX2 has closed (wake-up to turn-off, Casals Table 5) and then waits
        the ACK time-out (mean 2 s); the 1% duty cycle forbids a new frame before 100 x airtime has passed.
        NB-IoT: one cell search (only reached if retries continue while there is no network)."""
        if self.nb:
            return self.t_search
        sf = self._sf(attempt_no, True)
        busy = M.lora_active_s(sf, max(1, nbytes)) + ACK_TIMEOUT_MEAN
        return max(busy, 100 * M.lora_frame_ms(sf, nbytes) / 1e3)

    def readings_per_frame(self):
        cap = NB_MAX_FRAME if self.nb else LORA_MAX_APP[self.sf]
        return max(1, (cap - FRAME_OVERHEAD) // READING_BYTES)


@dataclass
class Result:
    energy_j: float = 0.0
    attempts: int = 0
    delivered_on_time: int = 0
    delivered_late: int = 0
    duplicates: int = 0
    lost: int = 0
    delays_s: list = field(default_factory=list)
    arrival_delay_s: np.ndarray = None   # per reading: seconds from its slot start to arrival; inf = never
    # revision additions (review C1, C5, C6); all zero/empty unless the matching option is used
    not_generated: int = 0               # slots in which the node was off (node_off): no reading exists
    storage_j: float = 0.0               # energy of writing/reading buffered readings (storage=...)
    max_buffer: int = 0                  # largest number of readings held at once
    backlogs: list = field(default_factory=list)   # (first slot, slot the backlog was cleared, readings)
    ok_times: list = field(default_factory=list)   # absolute time (s from slot 0) of every successful uplink


def simulate(link, radio, strategy, p_radio=0.0, R=None, M_check=6, buffer_cap=None, seed=0, slot_s=600.0,
             probe_cap=1, flush=None, urgent=None, trigger=None, newest_first=False, valid=None,
             restore=None, down_retry_fail=None, node_off=None, storage=None, drain_max_frames=None):
    """Run one strategy over a link trace (one reading per slot). Returns Result.
    R: max attempts per reading/frame (default: 8 for LoRaWAN, as in the spec; 3 for NB-IoT).
    buffer_cap: max buffered readings (None = unlimited); oldest are dropped on overflow.
    slot_s: slot length (s); backfilled readings' delay = (t - s) * slot_s + duty-cycle drain time.
    urgent: boolean array (len(link)); for batch_events, slots whose reading must be sent at once.
    trigger: optional callable trigger(t, arrival_delay_s) -> bool, consulted by batch_events in every slot
        while the link is believed up; True = upload now (bounded-error trigger). Not consulted during
        an outage (no extra probes), by design (DESIGN_EVAL_PLAN Part 2).
    newest_first: in an upload needing more than one frame, the first frame carries the newest buffered
        reading (then the oldest others); the rest go FIFO (DESIGN_EVAL_PLAN Part 3).
    valid: optional boolean array; with newest_first, the newest VALID reading is promoted (a slot without
        a reading, i.e. a sensor gap, is never promoted) (deviation D4).
    restore, down_retry_fail (review C2, intra-slot timing; both None = the whole slot is down, as before):
        a record only shows that the reading at a slot's first instant was lost, not that the link stayed down
        for the whole slot. Attempts in slot t happen at offsets tau >= 0 (Radio.retry_gap_s); the first, at
        tau = 0, is the one the record saw fail. restore[t] (s): in a down slot, the link is back for any
        attempt at tau >= restore[t] (inf = down all slot). down_retry_fail[t]: in a down slot, a RETRY
        (tau > 0) fails with this probability instead of surely (a short gap read as a radio-loss burst).
    node_off (review C1): boolean array; in these slots the node is off: no reading is generated, nothing is
        sent or buffered, and no energy is spent (counted in Result.not_generated, not as lost).
    storage (review C5): (J per reading written, J per reading read back) for every buffered reading, added
        to the energy (and to Result.storage_j); None = 0 (RAM buffer, negligible).
    drain_max_frames (review C5): at most this many bulk frames per slot; the rest of a backlog stays
        buffered and drains in the following slots (interleaved with live traffic). None = no limit.
    A trigger with the attribute wants_ok_times is called as trigger(t, arrival_delay_s, ok_times) (C6)."""
    rng = np.random.default_rng(seed)
    link = np.asarray(link, dtype=bool)
    if flush is None:                  # grace period after the record ends (see the epilogue below)
        flush = 4 * probe_cap + M_check + 16
    if R is None:
        R = 3 if radio.nb else 8
    if strategy in ("modem_buffer", "unconf_backoff") and not radio.nb:
        raise ValueError(f"{strategy} needs a radio that reports 'no network' (NB-IoT)")
    res = Result()
    n_read = len(link)
    res.arrival_delay_s = np.full(n_read, np.inf)
    if strategy == "batch_events":
        if urgent is None:
            raise ValueError("batch_events needs the urgent mask")
        urgent = np.asarray(urgent, dtype=bool)
        assert len(urgent) == n_read
    buf = []                       # (slot of reading, already_delivered_flag)
    outage = False
    next_probe, n_fail = 0, 0      # outage-mode probe schedule (exponential back-off up to probe_cap)
    since_ckpt = []                # checkpoint strategy: readings sent unconfirmed since last good checkpoint
    backlog = None                 # drain-limited backlog in progress: [first slot, readings at the start]
    e_write, e_read = storage if storage is not None else (0.0, 0.0)
    wants_ok = trigger is not None and getattr(trigger, "wants_ok_times", False)

    def send(t, confirmed, nbytes, max_att, tau=0.0):
        """Try one frame, first attempt at offset tau (s) in slot t; returns (success, attempts used)."""
        for a in range(1, max_att + 1):
            up = bool(link[t]) or (restore is not None and tau >= restore[t])
            net = up                                   # network present (NB-IoT: no cell search)
            if up:
                ok = rng.random() >= p_radio
            elif down_retry_fail is not None and tau > 0 and down_retry_fail[t] < 1:
                ok = rng.random() >= down_retry_fail[t]    # radio-loss burst: the network is there
                net = True
            else:
                ok = False
            res.energy_j += radio.attempt(confirmed, ok, net, nbytes, a)
            res.attempts += 1
            if ok:
                res.ok_times.append(t * slot_s + tau)
                return True, a
            if not confirmed:          # unconfirmed: no feedback, a single attempt
                return False, a
            if radio.nb and not net:
                return False, a        # the modem reports no network: retrying in this slot is pointless
            if restore is not None or down_retry_fail is not None:
                tau += radio.retry_gap_s(nbytes, a)
        return False, max_att

    def on_time(t):
        res.delivered_on_time += 1
        res.arrival_delay_s[t] = 0.0

    def live(t, ok):
        """outcome of a live (non-buffered) reading: on time, or lost for good"""
        if ok:
            on_time(t)
        else:
            res.lost += 1

    def probe_now(t):
        return t >= next_probe

    def probe_failed(t):
        nonlocal next_probe, n_fail
        n_fail += 1
        next_probe = t + min(2 ** n_fail, probe_cap)

    def enter_outage(t):
        nonlocal outage, next_probe, n_fail
        outage, n_fail = True, 0
        next_probe = t + 1

    def push(item):
        buf.append(item)
        if e_write:
            res.energy_j += e_write; res.storage_j += e_write
        res.max_buffer = max(res.max_buffer, len(buf))
        if buffer_cap is not None and len(buf) > buffer_cap:
            old = buf.pop(0)
            if not old[1]:
                res.lost += 1

    def drain(t):
        """Upload the buffer in bulk frames; stops (back to outage) at the first failed frame.
        With drain_max_frames, stops after that many frames and leaves the rest as a backlog."""
        nonlocal outage, backlog
        per = radio.readings_per_frame()
        if drain_max_frames is not None and backlog is None and len(buf) > drain_max_frames * per:
            backlog = [t, len(buf)]
        clock = 0.0                # LoRaWAN duty-cycle clock within this slot, seconds after the probe
        order = list(buf)
        if newest_first and len(order) > per:
            k = len(order) - 1
            if valid is not None:
                while k > 0 and not valid[order[k][0]]:
                    k -= 1
            order = [order[k]] + order[:k] + order[k + 1:]
        sent = frames = 0
        while sent < len(order):
            if drain_max_frames is not None and frames >= drain_max_frames:
                buf[:] = sorted(order[sent:], key=lambda it: it[0])
                outage = False
                return
            frames += 1
            chunk = order[sent:sent + per]
            nbytes = FRAME_OVERHEAD + READING_BYTES * len(chunk)
            ok, a = send(t, True, nbytes, R, tau=clock)
            if not ok:
                rest = sorted(order[sent:], key=lambda it: it[0])     # undelivered, back in time order
                buf[:] = rest
                enter_outage(t)
                return
            if e_read:
                res.energy_j += e_read * len(chunk); res.storage_j += e_read * len(chunk)
            for (s, already) in chunk:
                if already:
                    res.duplicates += 1
                else:
                    res.delivered_late += 1
                    res.delays_s.append((t - s) * slot_s + clock)
                    res.arrival_delay_s[s] = (t - s) * slot_s + clock
            clock += 100 * radio.airtime_s(nbytes, a)      # 1% duty cycle: wait 99x airtime before the next frame
            sent += len(chunk)
        buf.clear()
        outage = False
        if backlog is not None:
            res.backlogs.append((backlog[0], t, backlog[1]))
            backlog = None

    for t in range(len(link)):
        if node_off is not None and node_off[t]:
            res.not_generated += 1
            continue
        if backlog is not None and not outage and buf:
            drain(t)                                     # a drain-limited backlog continues before live traffic
        if strategy == "unconf":
            ok, _ = send(t, False, LIVE_BYTES, 1)
            live(t, ok)
        elif strategy == "arq":
            ok, _ = send(t, True, LIVE_BYTES, R)
            live(t, ok)
        elif strategy == "arq_buffer":
            if outage:
                if not probe_now(t):
                    push((t, False)); continue
                ok, _ = send(t, True, LIVE_BYTES, 1)               # one confirmed probe
                if ok:
                    on_time(t)
                    drain(t)
                else:
                    push((t, False)); probe_failed(t)
            else:
                ok, _ = send(t, True, LIVE_BYTES, R)
                if ok:
                    on_time(t)
                else:
                    push((t, False)); enter_outage(t)
        elif strategy == "batch":
            push((t, False))
            if outage:
                if probe_now(t):
                    ok, _ = send(t, True, LIVE_BYTES, 1)    # one small confirmed probe, as in arq_buffer
                    if ok:
                        drain(t)                         # a failed drain starts a new outage (back-off restarts)
                    else:
                        probe_failed(t)
            elif (t + 1) % M_check == 0:
                drain(t)                                 # on failure drain() enters outage mode
        elif strategy == "batch_events":
            push((t, False))
            if outage:
                if probe_now(t) or urgent[t]:            # an alarm probes at once, outside the schedule
                    ok, _ = send(t, True, LIVE_BYTES, 1)
                    if ok:
                        drain(t)
                    elif probe_now(t):
                        probe_failed(t)                  # an off-schedule (alarm) probe leaves the back-off as is
            elif urgent[t] or (t + 1) % M_check == 0 or (trigger is not None and (
                    trigger(t, res.arrival_delay_s, res.ok_times) if wants_ok else trigger(t, res.arrival_delay_s))):
                drain(t)
        elif strategy == "unconf_backoff":
            if outage and not probe_now(t):
                res.lost += 1                            # not attempted, not buffered
                continue
            ok, _ = send(t, False, LIVE_BYTES, 1)
            live(t, ok)
            if outage:
                if link[t]:
                    outage = False                       # modem attached: back to normal operation
                else:
                    probe_failed(t)
            elif not link[t]:
                enter_outage(t)
        elif strategy == "modem_buffer":
            if outage:
                if not probe_now(t):
                    push((t, False)); continue
                ok, _ = send(t, False, LIVE_BYTES, 1)
                if link[t]:                              # modem attached: the node knows the link is back
                    live(t, ok)                          # a radio loss of this live reading stays undetected
                    drain(t)
                else:
                    push((t, False)); probe_failed(t)
            else:
                ok, _ = send(t, False, LIVE_BYTES, 1)
                if ok:
                    on_time(t)
                elif not link[t]:                       # modem knows: buffer and enter outage mode
                    push((t, False)); enter_outage(t)
                else:                                    # radio loss, undetected
                    res.lost += 1
        elif strategy == "checkpoint":
            if outage:
                if not probe_now(t):
                    push((t, False)); continue
                ok, _ = send(t, True, LIVE_BYTES, 1)
                if ok:
                    on_time(t)
                    drain(t)
                    since_ckpt = []
                else:
                    push((t, False)); probe_failed(t)
            elif (t + 1) % M_check == 0:                # confirmed checkpoint
                ok, _ = send(t, True, LIVE_BYTES, R)
                if ok:
                    on_time(t)
                    for (s, arrived) in since_ckpt:
                        if not arrived:
                            res.lost += 1              # lost unconfirmed reading, never re-sent
                    since_ckpt = []
                else:
                    for item in since_ckpt:
                        push(item)
                    push((t, False)); since_ckpt = []; enter_outage(t)
            else:
                ok, _ = send(t, False, LIVE_BYTES, 1)
                if ok:
                    on_time(t)
                since_ckpt.append((t, ok))
        else:
            raise ValueError(strategy)
    # Epilogue (flush): the record ends, but a real node would keep running. If the link is up at the end,
    # let the node finish what it has buffered: up to `flush` extra slots with the link up and NO new
    # readings; probes keep their back-off schedule, delays and energy are counted as usual. Without
    # this, readings a node has not yet uploaded when the record happens to stop would count as lost
    # (it penalised buffering strategies at random, depending on where the record ends).
    if flush and len(link) and link[-1] and buf:
        T = len(link)
        link = np.r_[link, np.ones(flush, dtype=bool)]
        for t in range(T, T + flush):
            if not buf:
                break
            if outage:
                if not probe_now(t):
                    continue
                confirmed = strategy != "modem_buffer"
                ok, _ = send(t, confirmed, LIVE_BYTES, 1)
                if ok or (strategy == "modem_buffer" and link[t]):
                    drain(t)
                else:
                    probe_failed(t)
            else:
                drain(t)
    # whatever is still buffered (or unresolved since the last checkpoint) is lost
    res.lost += sum(1 for (_, already) in buf if not already)
    res.lost += sum(1 for (_, arrived) in since_ckpt if not arrived)
    return res


def intra_slot_model(link, slot_s, model, seed=0, q_burst=0.248, short_h=1.0):
    """Arrays (restore, down_retry_fail) for simulate() under the three link-timing models of review C2.
      'full'    the link is down for the whole of every missing slot (pessimistic for ARQ; the v0.1 replay)
      'uniform' within each gap, the link comes back at a uniformly random time between the last missing
                instant and the next delivered instant (only the gap's last slot can gain from a retry)
      'burst'   as 'uniform', and gaps no longer than short_h hours are read as radio-loss bursts: every
                retry in them fails with probability q_burst (LoED: P(loss | previous loss) = 0.248) rather
                than surely (optimistic for ARQ)
    The link record itself is unchanged: the first attempt at every missing instant still fails."""
    link = np.asarray(link, bool)
    if model == "full":
        return None, None
    rng = np.random.default_rng(seed)
    restore = np.full(len(link), np.inf)
    fail = np.ones(len(link)) if model == "burst" else None
    m = np.r_[False, ~link, False]
    d = np.diff(m.astype(int))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)        # gap = slots starts..ends-1
    for a, b in zip(starts, ends):
        if b < len(link):                                                 # the link is back at slot b
            restore[b - 1] = rng.uniform(0, slot_s)
        if model == "burst" and (b - a) * slot_s <= short_h * 3600:
            fail[a:b] = q_burst
    if model not in ("uniform", "burst"):
        raise ValueError(model)
    return restore, fail


def summary(res, n_slots, slot_s):
    days = n_slots * slot_s / 86400
    d = np.array(res.delays_s, dtype=float) / 3600
    n = res.delivered_on_time + res.delivered_late + res.lost
    out_extra = {"not_generated": res.not_generated / (n + res.not_generated),
                 "delivered_of_expected": (res.delivered_on_time + res.delivered_late) / (n + res.not_generated),
                 "storage_j_per_day": res.storage_j / days, "max_buffer": res.max_buffer}
    return {**out_extra, 
        "energy_j_per_day": res.energy_j / days,
        "attempts_per_day": res.attempts / days,
        "on_time": res.delivered_on_time / n,
        "late": res.delivered_late / n,
        "lost": res.lost / n,
        "duplicates_per_day": res.duplicates / days,
        # share of ALL readings that reached the server within X hours (on-time readings count as 0 h)
        "within_1h": (res.delivered_on_time + np.sum(d <= 1)) / n,
        "within_6h": (res.delivered_on_time + np.sum(d <= 6)) / n,
        "within_24h": (res.delivered_on_time + np.sum(d <= 24)) / n,
        "delay_h_median": float(np.median(d)) if len(d) else 0.0,
        "delay_h_p95": float(np.percentile(d, 95)) if len(d) else 0.0,
        "check_n": n,
    }
