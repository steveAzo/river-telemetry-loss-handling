import sys, glob, pandas as pd, io
rows=[]
for f in glob.glob(sys.argv[1]+"/*.rdb"):
    lines=[l for l in open(f,encoding='utf-8') if not l.startswith('#')]
    d=pd.read_csv(io.StringIO(''.join(lines)),sep='\t',dtype=str).iloc[1:]
    d=d[d.data_type_cd=='uv']
    d['end']=pd.to_datetime(d.end_date,errors='coerce'); d['begin']=pd.to_datetime(d.begin_date,errors='coerce')
    rows.append(d)
d=pd.concat(rows)
need={'00010','00095','00300','00400'}
g=d.groupby(['site_no','station_nm','dec_lat_va','dec_long_va','huc_cd']).agg(params=('parm_cd',lambda s:set(s)&need),begin=('begin','max'),end=('end','min')).reset_index()
g=g[g.params.apply(len)==4]
g['yrs']=((g.end-g.begin).dt.days/365.25).round(1)
g['huc8']=g.huc_cd.str[:8]
print(len(g),"sites with all 4 params (uv)")
# rivers with >=3 such sites on same named river
g['river']=g.station_nm.str.upper().str.extract(r'^(.*?)\s+(?:AT|NEAR|NR|BL|BELOW|AB|ABOVE|@|AT\.)\s')[0]
c=g.groupby('river').size().sort_values(ascending=False)
c=c[c>=2]
for r in c.index:
    print(f"\n== {r} ({c[r]})")
    print(g[g.river==r][['site_no','station_nm','huc8','begin','end','yrs']].sort_values('site_no').to_string(index=False))
g.to_csv(sys.argv[2],index=False)
