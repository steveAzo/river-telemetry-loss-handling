# Can an upstream/neighbour site reconstruct an outage at a target site better than the target's own data?
import sys, pandas as pd, numpy as np
tgt, nb = sys.argv[1], sys.argv[2]
def load(s):
    d = pd.read_csv(f"data/clean/usgs/{s}.csv", parse_dates=[0], index_col=0)
    d.index = d.index.tz_localize(None) if d.index.tz is not None else d.index
    return d.resample('30min').mean()
A, B = load(tgt), load(nb)
cols = [c for c in A.columns if c in B.columns and A[c].dtype != object]
print("columns", cols)
rng = np.random.default_rng(0)
for p in [c for c in cols if c in ('T','EC','pH','DO')]:
    x, y = A[p], B[p]
    best = max(range(0, 49), key=lambda L: x.corr(y.shift(L)))  # neighbour lag (15-min steps)
    yl = y.shift(best)
    for H in (2, 12, 48):  # outage length: 1 h, 6 h, 24 h
        errs = {k: [] for k in ['persist', 'interp(oracle)', 'nb_level', 'nb_delta', 'nb_delta+persist']}
        idx = np.where(x.notna() & yl.notna())[0]
        starts = rng.choice(idx[(idx > 48*8) & (idx < len(x)-H-1)], 300, replace=False)
        for s in starts:
            seg = slice(s, s+H); before = x.iloc[s-1]; after = x.iloc[s+H]
            truth = x.iloc[seg].values
            if np.isnan(truth).any() or np.isnan(before) or np.isnan(after): continue
            ynow = yl.iloc[seg].values; yb = yl.iloc[s-1]
            if np.isnan(ynow).any() or np.isnan(yb): continue
            # level regression of x on lagged y over prior 7 days
            w = slice(s-48*7, s); xx, yy = x.iloc[w], yl.iloc[w]; m = xx.notna() & yy.notna()
            if m.sum() < 100: continue
            c = np.polyfit(yy[m], xx[m], 1)
            errs['persist'].append(np.abs(truth - before).max())
            errs['interp(oracle)'].append(np.abs(truth - np.linspace(before, after, H+2)[1:-1]).max())
            errs['nb_level'].append(np.abs(truth - np.polyval(c, ynow)).max())
            errs['nb_delta'].append(np.abs(truth - (before + c[0]*(ynow - yb))).max())
            errs['nb_delta+persist'].append(np.abs(truth - (before + 0.5*c[0]*(ynow - yb))).max())
        print(f"{p:12s} lag={best*30:4d}min H={H*30/60:5.1f}h n={len(errs['persist'])} | median max-abs-error: " +
              "  ".join(f"{k}={np.median(v):.3f}" for k, v in errs.items()))
