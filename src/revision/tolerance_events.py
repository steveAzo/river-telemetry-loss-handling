"""Review M14 (tolerances in physical units) and E10/M12 (are the injected events realistic?).

M14: for every design site (2023), the L1/L2/L3 tolerances in physical units (EC: % of the site's median), next to
  * the USGS accuracy rating 'excellent' (Wagner et al. 2006, TM 1-D3, Table 18): T 0.2 degC, SC 3% of the reading,
    DO 0.3 mg/L or 5% of the reading (whichever is greater; converted to %sat at the site's median DO), pH 0.2;
  * the natural variability: median daily range (max - min within a calendar day, days with >= 80% of slots).
E10: the event amplitude kappa*sigma (sigma = the injection scale, inject.noise_scale) against the REAL largest
  3-hour changes at the same site: the share of 3-h windows whose |change| >= 5 sigma and >= 8 sigma, and the
  99.9th percentile of |3-h change| / sigma. If real 5-8 sigma excursions occur, the injected events are of a
  realistic size; physical plausibility of the injected VALUES is read from the reruns (inj_min/inj_max).
Usage (from Paper2/): python -I src/revision/tolerance_events.py results/revision/tolerance
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from design.inject import noise_scale  # noqa: E402
from design.sitedata import PARAMS, load_site  # noqa: E402
from design.run_sensitivity import LEVELS  # noqa: E402

USGS_EXCELLENT = {"T": 0.2, "pH": 0.2}          # absolute; SC 3% and DO max(0.3 mg/L, 5%) handled below


def site_rows(site):
    st = load_site(site)
    ds = st.ds
    X = pd.DataFrame(st.Xg, columns=PARAMS)
    t = pd.to_datetime(st.grid_t, unit="s")
    spd = int(round(86400 / st.step_s))
    raw = pd.read_csv(f"data/clean/usgs/{site}.csv")
    do_mgl = float(raw.DO_mgL.median()) if "DO_mgL" in raw else np.nan
    do_sat = float(np.nanmedian(st.Xg[:, PARAMS.index("DO")]))
    ec_med = float(np.nanmedian(st.Xg[:, PARAMS.index("EC")]))
    day = t.floor("D")
    cnt = X.groupby(day).count()
    rng_ = (X.groupby(day).max() - X.groupby(day).min())[cnt >= 0.8 * spd]
    rows = []
    sc = noise_scale(ds, st.res)                      # (N cycles, P): sigma of the event's month
    k3 = max(1, int(round(3 * 3600 / st.step_s)))
    for j, p in enumerate(PARAMS):
        r = {"site": site, "param": p, "step_min": st.step_s / 60, "median_daily_range": float(rng_[p].median())}
        for lv, tol in LEVELS.items():
            r[f"tol_{lv}"] = tol[p] * (ec_med if p == "EC" else 1.0)
        if p == "EC":
            r["usgs_excellent"] = 0.03 * ec_med
        elif p == "DO":                                # %sat equivalent of max(0.3 mg/L, 5% of the reading)
            r["usgs_excellent"] = max(0.3 / do_mgl * do_sat, 0.05 * do_sat) if np.isfinite(do_mgl) else np.nan
        else:
            r["usgs_excellent"] = USGS_EXCELLENT[p]
        # E10: real 3-h changes within segments, on the complete cycles, in units of the event scale
        x = ds.X[:, j]
        seg = np.cumsum(ds.seg_start)
        tt = ds.t.to_numpy().astype("datetime64[s]").astype(np.int64)
        i = np.arange(len(x) - k3)
        same = (seg[i] == seg[i + k3]) & (tt[i + k3] - tt[i] == k3 * st.step_s)
        z = np.abs(x[i + k3] - x[i])[same] / sc[i[same], j]
        r["sigma_median"] = float(np.median(sc[:, j]))
        r["amp5_median"] = 5 * r["sigma_median"]; r["amp8_median"] = 8 * r["sigma_median"]
        r["real3h_share_ge5"] = float(np.mean(z >= 5)); r["real3h_share_ge8"] = float(np.mean(z >= 8))
        r["real3h_p999_over_sigma"] = float(np.percentile(z, 99.9)); r["real3h_max_over_sigma"] = float(z.max())
        rows.append(r)
    return rows


def main(out):
    elig = pd.read_csv("results/scoping/design_site_eligibility.csv", dtype={"site": str})
    rows = []
    for s in elig[elig.status == "ok"].site:
        rows += site_rows(s)
        print(f"{s} done", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(f"{out}_sites.csv", index=False, float_format="%.6g")
    agg = d.groupby("param").agg(
        tol_L1_med=("tol_L1", "median"), tol_L2_med=("tol_L2", "median"), tol_L3_med=("tol_L3", "median"),
        usgs_exc_med=("usgs_excellent", "median"), daily_range_med=("median_daily_range", "median"),
        daily_range_p10=("median_daily_range", lambda v: np.percentile(v, 10)),
        daily_range_p90=("median_daily_range", lambda v: np.percentile(v, 90)),
        amp5_med=("amp5_median", "median"), amp8_med=("amp8_median", "median"),
        sites_with_real_ge5=("real3h_share_ge5", lambda v: np.mean(v > 0)),
        sites_with_real_ge8=("real3h_share_ge8", lambda v: np.mean(v > 0)),
        real_p999_over_sigma_med=("real3h_p999_over_sigma", "median"),
        real_max_over_sigma_med=("real3h_max_over_sigma", "median"))
    agg.to_csv(f"{out}_summary.csv", float_format="%.6g")
    print(agg.round(3).T.to_string())


if __name__ == "__main__":
    main(sys.argv[1])
