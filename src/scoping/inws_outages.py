"""InWaterSense node 1 outage table (PAPER2_SCOPING.md section 2.3; previously computed inline).

A record slot is 611 s (the node's median step). A gap of k slots between consecutive delivered cycles
means k - 1 missing slots (one outage of length k - 1). Reports the loss rate, the outage-length
distribution and the share of lost slots by outage length.
Usage (from Paper2/): python -I src/scoping/inws_outages.py results/scoping/inws_outages.csv
"""
import sys

import numpy as np
import pandas as pd

SLOT_S = 611.0
BINS = [("1 slot (10 min)", 1, 1), ("2-5 slots", 2, 5), ("6-35 slots (1-6 h)", 6, 35),
        ("36-141 slots (6-24 h)", 36, 141), (">= 142 slots (>= 1 day)", 142, 10**9)]


def main(out):
    d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    t = d[d.node == 1].t.sort_values()
    k = np.rint(t.diff().dt.total_seconds().dropna().to_numpy() / SLOT_S).astype(int)
    k = np.maximum(k, 1)
    outages = k[k > 1] - 1
    delivered = len(t)
    lost = int(outages.sum())
    rows = [{"bin": "ALL", "events": len(outages), "event_share": 1.0, "lost_slots": lost, "lost_share": 1.0}]
    for lab, lo, hi in BINS:
        m = (outages >= lo) & (outages <= hi)
        rows.append({"bin": lab, "events": int(m.sum()), "event_share": m.mean(),
                     "lost_slots": int(outages[m].sum()), "lost_share": outages[m].sum() / lost})
    r = pd.DataFrame(rows)
    r.to_csv(out, index=False, float_format="%.6g")
    print(f"delivered cycles {delivered}; missing slots {lost}; loss rate {lost / (lost + delivered):.4f}; "
          f"outages {len(outages)}; median {np.median(outages):.0f}; mean {outages.mean():.2f}; max {outages.max()}")
    print(r.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
