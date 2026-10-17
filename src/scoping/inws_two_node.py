import sys, pandas as pd, numpy as np
d = pd.read_csv(sys.argv[1], parse_dates=['t'])
d = d.sort_values(['node','t'])
for n in (1,2):
    x = d[d.node==n]
    print(f"node {n}: {len(x)} cycles, {x.t.min()} -> {x.t.max()}, complete={x.complete.sum()}")
    dt = x.t.diff().dt.total_seconds()
    print("  median step s", dt.median(), " gaps>30min:", (dt>1800).sum(), " gaps>1d:", (dt>86400).sum())
# overlap period
a, b = d[d.node==1].set_index('t'), d[d.node==2].set_index('t')
lo, hi = max(a.index.min(), b.index.min()), min(a.index.max(), b.index.max())
print("overlap window", lo, hi)
# bin to 10-min grid
g = pd.date_range(lo.floor('10min'), hi.ceil('10min'), freq='10min')
def onGrid(x):
    x = x[~x.index.duplicated()]
    return x.reindex(g, method='nearest', tolerance=pd.Timedelta('5min'))
A, B = onGrid(a), onGrid(b)
pa, pb = A['T'].notna(), B['T'].notna()
print(f"grid slots {len(g)}: node1 present {pa.mean():.3f}, node2 present {pb.mean():.3f}, both {(pa&pb).mean():.3f}")
# gap co-occurrence: P(node2 missing | node1 missing) vs marginal
ma, mb = ~pa, ~pb
print(f"P(n1 miss)={ma.mean():.3f} P(n2 miss)={mb.mean():.3f} P(n2 miss|n1 miss)={(ma&mb).sum()/max(ma.sum(),1):.3f} P(n1 miss|n2 miss)={(ma&mb).sum()/max(mb.sum(),1):.3f}")
# monthly presence of node 2
print("node2 cycles by month:"); print(b.groupby(b.index.to_period('M')).size().to_string())
# fault-code prevalence on node 2
for p, bad in [('EC', lambda v: v<0), ('T', lambda v: v<0), ('DO', lambda v: v<=0)]:
    v = b[p].dropna(); print(f"node2 {p}: n={len(v)} faulty={bad(v).mean():.3f}")
# cross-node correlation where both valid (plausible values)
ok = lambda X,p: X[p].where(~X[p+'_range'].fillna(True).astype(bool) & ~X[p+'_plaus'].fillna(True).astype(bool))
for p in ['T','EC','pH','DO']:
    x, y = ok(A,p), ok(B,p)
    m = x.notna() & y.notna()
    if m.sum() < 50: print(p, "too few joint", m.sum()); continue
    r = np.corrcoef(x[m], y[m])[0,1]
    dx, dy = x.diff(), y.diff(); mm = dx.notna() & dy.notna()
    rd = np.corrcoef(dx[mm], dy[mm])[0,1] if mm.sum()>50 else np.nan
    # lagged correlation of levels, lags -6..6 slots
    lags = {L: x.corr(y.shift(-L)) for L in range(-6,7)}
    best = max(lags, key=lambda k: lags[k] if not np.isnan(lags[k]) else -9)
    print(f"{p}: joint n={m.sum()} level r={r:.3f} diff r={rd:.3f} best lag={best*10}min r={lags[best]:.3f}  mean n1={x[m].mean():.2f} n2={y[m].mean():.2f}")
