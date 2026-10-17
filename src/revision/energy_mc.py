"""Review C7 (no hardware) and M6: how robust are the energy RATIOS to the energy model's parameters?

There is no hardware to measure the design on. The one independent measurement in the literature we hold
(Ugwuanyi et al. 2021, a Pycom FiPy board: ~100 uAh per 44-B LoRaWAN SF7 uplink, ~1.8 mAh per NB-IoT uplink over
TCP without RAI) differs from our per-report energies by up to an order of magnitude: absolute energy depends on the
platform and stack. The paper's claims are therefore stated as within-radio ratios, and this script tests them.
Every measured component is multiplied by an independent factor drawn log-uniformly from [1/2, 2]
(LoRaWAN: unconfirmed report, confirmed success, ACK time-out; NB-IoT: unconfirmed, confirmed, bulk-size slope,
search power; host awake power), and the NB-IoT search time is drawn log-uniformly from [2.2, 60] s.
For each draw: ARQ (8 transmissions, LoRaWAN 1.0.2 stepping; NB-IoT 3) / fair baseline, buffer+back-off / fair
baseline, batch 1 h / fair baseline (fair baseline: unconfirmed; NB-IoT: unconfirmed + back-off).
Records: InWaterSense, Weija node record. Usage: python -I src/revision/energy_mc.py results/revision/energy_mc [draws]
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from energy.loss_handling import Radio, simulate, summary  # noqa: E402
from revision.run_loss_revision import traces  # noqa: E402

KEYS = {"lora": ["lora_unack", "lora_ack", "lora_timeout", "host"],
        "nb": ["nb_unack", "nb_ack", "nb_bulk", "nb_search", "host"]}


def draw(rng, keys):
    return {k: float(np.exp(rng.uniform(np.log(0.5), np.log(2.0)))) for k in keys}


def main(out, n_draws=100):
    n_draws = int(n_draws)
    rng = np.random.default_rng(20261017)
    rows = []
    recs = [(t, l, s) for t, l, s in traces() if not t.startswith("Weija (v0.1")]
    for i in range(n_draws):
        sc_l, sc_n = draw(rng, KEYS["lora"]), draw(rng, KEYS["nb"])
        t_search = float(np.exp(rng.uniform(np.log(2.2), np.log(60.0))))
        for tr, link, slot in recs:
            cap = max(1, int(round(6 * 3600 / slot))); M = max(1, int(round(3600 / slot)))
            for rl, r in (("NB-IoT", Radio("NB-IoT N211 RAI", t_search=t_search, scale=sc_n)),
                          ("LoRaWAN SF7", Radio("LoRaWAN SF7", scale=sc_l)),
                          ("LoRaWAN SF12", Radio("LoRaWAN SF12", scale=sc_l))):
                kw = dict(seed=20261011, slot_s=slot)
                e = {k: summary(simulate(link, r, s, **a, **kw), len(link), slot)["energy_j_per_day"] for k, s, a in (
                    ("unconf", "unconf", {}), ("arq", "arq", {}), ("buffer", "arq_buffer", {"probe_cap": cap}),
                    ("batch", "batch", {"probe_cap": cap, "M_check": M}))}
                if r.nb:
                    e["fair"] = summary(simulate(link, r, "unconf_backoff", probe_cap=cap, **kw), len(link), slot)["energy_j_per_day"]
                else:
                    e["fair"] = e["unconf"]
                rows.append({"draw": i, "trace": tr, "radio": rl, "t_search": t_search,
                             **{f"s_{k}": v for k, v in (sc_n if r.nb else sc_l).items()},
                             "arq_over_unconf": e["arq"] / e["unconf"], "buffer_over_fair": e["buffer"] / e["fair"],
                             "batch_over_fair": e["batch"] / e["fair"], "unconf_over_fair": e["unconf"] / e["fair"]})
        if i % 10 == 0:
            print(f"draw {i}", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(f"{out}_draws.csv", index=False, float_format="%.6g")
    cols = ["arq_over_unconf", "buffer_over_fair", "batch_over_fair", "unconf_over_fair"]
    s = d.groupby(["trace", "radio"])[cols].describe(percentiles=[0.025, 0.5, 0.975])
    keep = s.loc[:, (slice(None), ["2.5%", "50%", "97.5%"])]
    keep.to_csv(f"{out}_summary.csv", float_format="%.4g")
    print(keep.round(2).to_string())
    print("\nshare of draws: ARQ dearer than unconfirmed; batch cheaper than the fair baseline")
    print(d.groupby(["trace", "radio"]).apply(lambda g: pd.Series({
        "arq_dearer": (g.arq_over_unconf > 1).mean(), "batch_cheaper": (g.batch_over_fair < 1).mean(),
        "buffer_within_30pct": (np.abs(g.buffer_over_fair - 1) <= 0.3).mean()}), include_groups=False).round(3).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:3])
