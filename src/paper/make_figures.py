"""Figures for the Paper 2 manuscript (vector PDF into draft/figs/).

fig_records        delivery timelines of the three outage records
fig_mechanism      illustrative scenario through the simulator: when each reading reaches the server
fig_outage_share   share of lost readings in outages at least x hours long: observed vs fitted geometric
fig_tradeoff       energy vs real-time picture (DO, L2 tolerance), LoRaWAN SF7, one panel per link
fig_outage_onset   events that start during an outage: share known at the server by t hours after onset
Each figure is written as vector PDF (LaTeX) and 300-dpi PNG (Word copy).

Palette: validated categorical slots 1-3 (#2a78d6, #eb6834, #1baf7a); identity also carried by
markers / line style and direct labels. Usage (from Paper2/): python -I src/paper/make_figures.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/scoping")
from outage_models import fit_geom, runs_from_times  # noqa: E402

OUT = Path("draft/figs")
C = ["#2a78d6", "#eb6834", "#1baf7a"]
INK, MUTED, GRID = "#1f1f1f", "#5c5c5c", "#d9d9d9"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "lines.linewidth": 1.5,
                     "legend.frameon": False, "pdf.fonttype": 42})
W1, W2 = 3.5, 7.16   # IEEE column / page width (in)


def lost_share_curve(outs, slot_s, xs_h):
    """Share of lost slots that fall in outages of at least x hours."""
    h = outs * slot_s / 3600
    return np.array([outs[h >= x].sum() / outs.sum() for x in xs_h])


def geom_share_curve(q, slot_s, xs_h, kmax):
    k = np.arange(1, kmax + 1, dtype=float)
    p = (1 - q) * q ** (k - 1)
    w = k * p
    hk = k * slot_s / 3600
    return np.array([w[hk >= x].sum() / w.sum() for x in xs_h])


def records():
    d = pd.read_csv("data/clean/inws_cycles.csv", parse_dates=["t"])
    _, o1 = runs_from_times(d[d.node == 1].t, 611)
    w = pd.read_csv("data/weija_raw/conductivity_cleaned_records.csv", parse_dates=["Datetime"])
    w = w[w.Was_Imputed.astype(str) != "True"]
    tw = w.Datetime.drop_duplicates().sort_values()
    slot_w = float(np.median(tw.diff().dt.total_seconds().dropna()))
    _, o2 = runs_from_times(tw, slot_w)
    o3 = pd.read_csv("results/scoping/uva_loss_runs.csv").len.to_numpy()
    return [("InWaterSense", o1, 611.0), ("Weija", o2, slot_w), ("UVA", o3, 300.0)]


def fig_outage_share():
    xs = np.logspace(np.log10(1 / 60), np.log10(24 * 40), 400)
    fig, ax = plt.subplots(figsize=(W1, 3.0))
    marks = ["o", "s", "^"]
    for i, (name, outs, slot) in enumerate(records()):
        outs = np.asarray(outs, float)
        obs = lost_share_curve(outs, slot, xs)
        q = fit_geom(outs)[0]["q"]
        mod = geom_share_curve(q, slot, xs, int(outs.sum()))
        ax.plot(xs, 100 * obs, color=C[i], label=f"{name} (observed)")
        mk = np.searchsorted(xs, [1, 6, 24])
        ax.plot(xs[mk], 100 * obs[mk], marks[i], color=C[i], ms=4.5, mec="white", mew=0.8)
        ax.plot(xs, 100 * mod, color=C[i], ls=(0, (3, 2)), lw=1.2, label=f"{name} (geometric fit)")
        print(f"{name}: observed share >=6h {lost_share_curve(outs, slot, [6])[0]:.3f}, >=24h "
              f"{lost_share_curve(outs, slot, [24])[0]:.3f}; geometric >=24h {geom_share_curve(q, slot, [24], int(outs.sum()))[0]:.2e}")
    for x, t in ((6, "6 h"), (24, "1 day")):
        ax.axvline(x, color=MUTED, lw=0.6, ls=":")
        ax.text(x * 1.08, 101, t, color=MUTED, fontsize=7, va="bottom")
    ax.set_xscale("log"); ax.set_xlim(xs[0], xs[-1]); ax.set_ylim(0, 108)
    ax.set_xticks([1 / 6, 1, 6, 24, 24 * 7]); ax.set_xticklabels(["10 min", "1 h", "6 h", "1 d", "1 wk"])
    ax.set_xlabel("Outage length at least")
    ax.set_ylabel("Share of lost readings (%)")
    ax.legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, handlelength=2.4, columnspacing=1.2)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "fig_outage_share.pdf"); fig.savefig(OUT / "fig_outage_share.png", dpi=300); plt.close(fig)


def fig_tradeoff():
    """Held-out year (2024), from the frozen analysis (results/confirm/an2024_*); one vertical scale for all panels."""
    e = pd.read_csv("results/confirm/an2024_energy.csv")
    p = pd.read_csv("results/confirm/an2024_picture.csv"); p = p[(p.level == "L2") & (p.param == "DO")]
    R = "LoRaWAN SF7"
    links = [("none", "No outage"), ("UVA", "UVA"), ("Weija", "Weija"), ("InWaterSense", "InWaterSense")]
    fig, axs = plt.subplots(1, 4, figsize=(W2, 2.2), sharey=True)
    sty = {"unconf": ("Unconfirmed", "o"), "arq": ("ARQ + buffer", "s"), "batch": ("Batch 1 h", "^"),
           "design": ("Event-driven", "v"), "bounded": ("Bounded event-driven", "D")}
    lows = []
    for ax, (tr, name) in zip(axs, links):
        ee = e[(e.trace == tr) & (e.radio == R)].iloc[0]; pp_ = p[(p.trace == tr) & (p.radio == R)].iloc[0]
        pts = {"unconf": (ee.E_unconf, pp_.within_unconf), "arq": (ee.E_arq, pp_.within_arq),
               "batch": (ee.E_batch, pp_.within_batch), "design": (ee.E_event, pp_.within_event),
               "bounded": (ee.E_bounded, pp_.within_bounded)}
        for k, (x, y) in pts.items():
            lab, mk = sty[k]
            ax.plot(x, 100 * y, mk, color=C[0] if k == "bounded" else MUTED, ms=5.5 if k == "bounded" else 4.5,
                    mec="white", mew=0.6, zorder=4 if k == "bounded" else 3, label=lab, ls="none")
            lows.append(100 * y)
        ax.set_title(name, fontsize=8, color=INK)
        ax.set_xlim(0, 75)
        ax.set_xlabel("Energy (J/day)")
    for ax in axs:
        ax.set_ylim(np.floor(min(lows) / 5) * 5 - 3, 102)
    axs[0].set_ylabel("DO within tolerance (%)")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=5, fontsize=7, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(pad=0.3, w_pad=0.8, rect=(0, 0, 1, 0.9))
    fig.savefig(OUT / "fig_tradeoff.pdf"); fig.savefig(OUT / "fig_tradeoff.png", dpi=300); plt.close(fig)


def fig_outage_onset():
    """Held-out year (2024): detected events whose onset fell in a gap (per-site files of the frozen run)."""
    el = pd.read_csv("results/confirm/eligibility_2024.csv", dtype={"site": str})
    ok = sorted(el[el.status == "ok"].site)
    ev = pd.concat((pd.read_csv(f"results/confirm/2024/{s}_events.csv", dtype={"site": str}) for s in ok), ignore_index=True)
    ev = ev[(ev.radio == "LoRaWAN SF7") & ~ev.link_up_at_onset & ev.node_detected]
    t = np.logspace(-1, np.log10(24 * 30), 300)
    strat = [("unconf", "Unconfirmed", "-"), ("arq_buffer", "ARQ + buffer", (0, (3, 2))), ("design", "Event-driven", "-")]
    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.1), sharey=True)
    for ax, tr in zip(axs, ("InWaterSense", "Weija", "UVA")):
        g0 = ev[ev.trace == tr]
        for i, (k, lab, ls) in enumerate(strat):
            lat = g0[g0.strategy == k].latency_h.to_numpy()
            y = np.array([(lat <= x).mean() for x in t])
            ax.plot(t, 100 * y, color=C[i], ls=ls, label=lab)
            j = np.searchsorted(t, 24)
            ax.plot(t[j], 100 * y[j], "osD"[i], color=C[i], ms=4, mec="white", mew=0.8)
        ax.axvline(24, color=MUTED, lw=0.6, ls=":")
        ax.set_xscale("log"); ax.set_xlim(t[0], t[-1]); ax.set_ylim(-2, 102)
        ax.set_xticks([1, 6, 24, 24 * 7]); ax.set_xticklabels(["1 h", "6 h", "1 d", "1 wk"])
        ax.set_title(f"{tr} (n = {len(g0[g0.strategy == 'design']):,})", fontsize=8, color=INK)
        ax.set_xlabel("Time since event onset")
    axs[0].set_ylabel("Events known at server (%)")
    axs[0].legend(fontsize=6.5, loc="upper left")
    fig.tight_layout(pad=0.3, w_pad=0.8)
    fig.savefig(OUT / "fig_outage_onset.pdf"); fig.savefig(OUT / "fig_outage_onset.png", dpi=300); plt.close(fig)


def fig_records():
    """Delivery timelines: each missing span drawn as a bar, on each record's own time axis."""
    sys.path.insert(0, "src")
    from design.sitedata import load_records
    recs = load_records()
    rows = [("InWaterSense", "InWaterSense node 1"), ("Weija", "Weija conductivity"), ("UVA", "UVA (system outages)")]
    fig, ax = plt.subplots(figsize=(W2, 1.5))
    for i, (key, lab) in enumerate(rows):
        t0, slot, up = recs[key]
        down = ~up
        edges = np.flatnonzero(np.diff(np.r_[0, down.astype(int), 0]))
        spans = [(a * slot / 86400, (b - a) * slot / 86400) for a, b in zip(edges[::2], edges[1::2])]
        y = len(rows) - 1 - i
        ax.broken_barh([(0, len(up) * slot / 86400)], (y - 0.3, 0.6), color=GRID, lw=0)
        ax.broken_barh(spans, (y - 0.3, 0.6), color=C[i], lw=0)
        print(f"{lab}: {len(up) * slot / 86400:.0f} days, {down.mean():.3f} of slots down, {len(spans)} down spans")
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[1] for r in rows][::-1])
    ax.set_xlabel("Days since the start of the record")
    ax.grid(False); ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, None)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "fig_records.pdf"); fig.savefig(OUT / "fig_records.png", dpi=300); plt.close(fig)


def fig_mechanism():
    """Illustrative scenario run through the real simulator: when each reading reaches the server."""
    sys.path.insert(0, "src")
    from energy.loss_handling import Radio, simulate
    n, slot = 64, 900.0                       # 16 h of 15-min slots
    link = np.ones(n, bool); link[24:40] = False          # outage 6 h - 10 h
    urg = np.zeros(n, bool); urg[9] = True; urg[30] = True  # alarms at 2.25 h (link up) and 7.5 h (outage)
    r = Radio("LoRaWAN SF7")
    runs = [("ARQ + buffer", "arq_buffer", dict(probe_cap=24), "o"),
            ("Batch 1 h", "batch", dict(M_check=4, probe_cap=24), "s"),
            ("Event-driven", "batch_events", dict(M_check=4, probe_cap=24, urgent=urg), "D")]
    t = np.arange(n) * slot / 3600
    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.2), sharey=True)
    for i, (ax, (lab, st, kw, mk)) in enumerate(zip(axs, runs)):
        v = simulate(link, r, st, slot_s=slot, **kw)
        arr = t + v.arrival_delay_s / 3600
        assert np.isfinite(arr).all()
        ax.axvspan(6, 10, color=GRID, alpha=0.6, lw=0)
        ax.text(8, 14.6, "outage", ha="center", color=MUTED, fontsize=7)
        ax.plot([0, 16], [0, 16], color=MUTED, lw=0.6, ls=":")
        ax.plot(t, arr, mk, color=C[i], ms=3.2, mec="white", mew=0.4, ls="none", zorder=3)
        if st == "batch_events":
            for a in (2.25, 7.5):
                ax.annotate("alarm", (a, -0.2), xytext=(a, -2.6), ha="center", fontsize=6.5, color=INK,
                            arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.6))
        ax.set_title(lab, fontsize=8, color=INK)
        ax.set_xlim(0, 16); ax.set_ylim(-3.2, 16); ax.set_xticks([0, 4, 8, 12, 16])
        ax.set_xlabel("Reading taken (h)")
    axs[0].set_ylabel("Reading reaches server (h)")
    fig.tight_layout(pad=0.3, w_pad=0.8)
    fig.savefig(OUT / "fig_mechanism.pdf"); fig.savefig(OUT / "fig_mechanism.png", dpi=300); plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_records(); fig_outage_share(); fig_mechanism(); fig_tradeoff(); fig_outage_onset()
    print("figures ->", OUT)
