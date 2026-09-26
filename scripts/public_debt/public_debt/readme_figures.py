"""Figures shown in the README, computed from the same data and engines as the notebooks.

Run from the repository root (official data are downloaded and cached on first use):

    python -m public_debt.readme_figures              # writes docs/figures/*-light.png and *-dark.png
    python -m public_debt.readme_figures --synthetic  # offline check on placeholder data

Each figure is saved in a light and a dark variant; the README selects one with <picture>.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import accounting, data, dsa, synthetic
from .figstyle import band, end_label, header, new_figure, percent_axis, point_label, render
from .var import fit_var1

# Assumptions shared with notebook 4 (see its first cell).
REAL_GROWTH, INFLATION, REFINANCING_SHARE, EPSILON, SEED = 0.008, 0.020, 0.15, 0.5, 20250101
COMPONENTS = ["primary deficit", "interest", "real growth", "inflation", "stock-flow adjustment"]
COFOG_SHOWN = {"GF1002": "Old-age pensions", "GF0107": "Interest", "GF1003": "Survivors' pensions",
               "GF03": "Public order and safety", "GF02": "Defence", "GF04": "Economic affairs",
               "GF1005": "Unemployment", "GF1004": "Family and children", "GF07": "Health",
               "GF09": "Education", "GF1001": "Sickness and disability"}


def load(official=True, n_paths=100_000) -> dict:
    if official:
        it, peer = data.fiscal_dataset("IT"), data.fiscal_dataset("EU27_2020")
        cof, yields = data.cofog_expenditure(), data.bond_yields(("IT", "DE"))
        try:
            imf = data.imf_series("GGXWDG_NGDP", "ITA")
        except Exception:  # the projection line is optional
            imf = None
        source = "Source: Eurostat ({datasets})"
    else:
        it, peer = synthetic.fiscal_dataset(seed=5), synthetic.fiscal_dataset(seed=15)
        cof, yields, imf = synthetic.cofog_expenditure(), synthetic.bond_yields(), None
        source = "Synthetic placeholder data, not statistics about Italy ({datasets})"
    out = {"it": it, "peer": peer, "cof": cof, "yields": yields, "imf": imf, "source": source}

    dec = accounting.debt_decomposition(it)
    last = int(dec.index.max())
    periods = {"1996-99": (1996, 1999), "2000-07": (2000, 2007), "2008-13": (2008, 2013), "2014-19": (2014, 2019),
               "2020-21": (2020, 2021), f"2022-{str(last)[2:]}": (2022, last)}
    out["periods"] = 100 * accounting.by_period(dec, {k: v for k, v in periods.items() if v[0] <= last})

    d0, i0 = float(it["debt"].iloc[-1]), float(it["effective_rate"].iloc[-1])
    pb0, r0 = float(it["primary_balance"].iloc[-1]), float(yields["IT"].dropna().iloc[-1]) / 100
    base = dsa.Scenario.constant(int(it.index.max()) + 1, 10, REAL_GROWTH, INFLATION, r0, pb0)
    macro = pd.DataFrame({"real_growth": it["real_growth"], "inflation": it["inflation"],
                          "long_rate": yields["IT"].reindex(it.index) / 100}).dropna()
    var = fit_var1(macro)
    out["fans"] = {name: dsa.stochastic(d0, i0, REFINANCING_SHARE, sc, var, np.zeros(3), epsilon=EPSILON,
                                        n_paths=n_paths, seed=SEED)
                   for name, sc in (("No policy change", base),
                                    ("Primary balance +0.5 pp a year for 7 years", base.with_adjustment(0.005, 7)))}
    out["d0"], out["start_year"] = d0, int(it.index.max())
    return out


def debt_ratio(t, d):
    it, peer, imf = d["it"], d["peer"], d["imf"]
    fig, ax = new_figure(t)
    c_it, c_eu = t["series"][0], t["series"][1]
    ax.plot(it.index, 100 * it["debt"], color=c_it, label="Italy")
    ax.plot(peer.index, 100 * peer["debt"], color=c_eu, label="EU27")
    last = int(it.index.max())
    if imf is not None and imf.index.max() > last:
        proj = imf.loc[last:last + 5]
        ax.plot(proj.index, proj.values, color=c_it, ls=(0, (3, 2)), lw=1.6, label="Italy, IMF projection")
    point_label(ax, t, last, 100 * it["debt"].iloc[-1], f"{last}: {100 * it['debt'].iloc[-1]:.1f}%", c_it, dy=10)
    end_label(ax, t, int(peer.index.max()), 100 * peer["debt"].iloc[-1], f"EU27 {100 * peer['debt'].iloc[-1]:.1f}%", c_eu)
    peak = int(it["debt"].idxmax())
    point_label(ax, t, peak, 100 * it["debt"].max(), f"{peak}: {100 * it['debt'].max():.1f}%", c_it)
    low = int(it.loc[:2010, "debt"].idxmin())
    point_label(ax, t, low, 100 * it.loc[low, "debt"], f"{low}: {100 * it.loc[low, 'debt']:.1f}%", c_it, dy=-12)
    percent_axis(ax)
    ax.set_ylim(40, 170)
    ax.legend(loc="upper left", ncol=3)
    header(fig, t, "Italy's public debt is back on the rise",
           "General government gross debt, % of GDP (excessive deficit procedure definition)",
           d["source"].format(datasets="gov_10dd_edpt1") + "; IMF World Economic Outlook (projection)")
    return fig


def decomposition(t, d):
    table = d["periods"]
    fig, ax = new_figure(t)
    fig.subplots_adjust(right=0.74)
    x = np.arange(len(table))
    pos, neg = np.zeros(len(table)), np.zeros(len(table))
    for k, comp in enumerate(COMPONENTS):
        v = table[comp].to_numpy()
        up, down = np.where(v > 0, v, 0.0), np.where(v < 0, v, 0.0)
        ax.bar(x, up, 0.42, bottom=pos, color=t["series"][k], edgecolor=t["surface"], linewidth=1.5, label=comp.capitalize())
        ax.bar(x, down, 0.42, bottom=neg, color=t["series"][k], edgecolor=t["surface"], linewidth=1.5)
        pos, neg = pos + up, neg + down
    change = table["change in debt"].to_numpy()
    ax.plot(x, change, "D", ms=8, color=t["ink"], mec=t["surface"], mew=2, zorder=5, label="Change in the debt ratio")
    for xi, c in zip(x, change):
        ax.annotate(f"{c:+.1f}", (xi, c), xytext=(16, 0), textcoords="offset points", va="center", fontsize=9, color=t["ink"])
    ax.axhline(0, color=t["axis"], lw=1)
    ax.set_xticks(x, table.index)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0f}" if v else "0")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    header(fig, t, "Interest has pushed the debt up in every period",
           "Contributions to the change in the debt ratio by period, percentage points of GDP",
           d["source"].format(datasets="gov_10dd_edpt1, nama_10_gdp") + "; computations in notebook 1")
    return fig


def spending_gap(t, d):
    cof = d["cof"]
    year = int(cof.groupby("geo")["year"].max().min())
    w = cof[cof["year"] == year].pivot_table(index="cofog", columns="geo", values="value")
    gap = (w["IT"] - w["EU27_2020"]).reindex(list(COFOG_SHOWN)).dropna()
    gap.index = [COFOG_SHOWN[c] for c in gap.index]
    gap = gap.sort_values()
    fig, ax = new_figure(t, height=5.0)
    fig.subplots_adjust(left=0.26, right=0.93)
    ax.barh(np.arange(len(gap)), gap.to_numpy(), 0.55, color=t["series"][0])
    for k, v in enumerate(gap):
        ax.annotate(f"{v:+.1f}", (v, k), xytext=(5 if v >= 0 else -5, 0), textcoords="offset points",
                    ha="left" if v >= 0 else "right", va="center", fontsize=9, color=t["ink2"])
    ax.set_yticks(np.arange(len(gap)), gap.index)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.axvline(0, color=t["axis"], lw=1)
    lim = 1.25 * np.abs(gap).max()
    ax.set_xlim(-lim, lim)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}" if v else "0")
    fig.texts.clear()
    fig.text(0.26, 0.945, "More on pensions and interest, less on health, education and families",
             fontsize=13, weight="bold", color=t["ink"], va="top")
    fig.text(0.26, 0.885, f"Italy minus EU27, general government expenditure by function, {year}, percentage points of GDP",
             fontsize=10, color=t["ink2"], va="top")
    fig.text(0.26, 0.025, d["source"].format(datasets="gov_10a_exp, COFOG"), fontsize=8, color=t["muted"])
    return fig


def fan_chart(t, d):
    fig, axes = new_figure(t, ncols=2, sharey=True)
    fig.subplots_adjust(right=0.93, wspace=0.22)
    c = t["series"][0]
    for ax, (name, fan) in zip(axes, d["fans"].items()):
        p = 100 * fan["percentiles"]
        x = np.r_[d["start_year"], p.index.to_numpy()]

        def with_start(col):
            return np.r_[100 * d["d0"], p[col].to_numpy()]

        band(ax, x, with_start("p5"), with_start("p95"), c, t["band"][0])
        band(ax, x, with_start("p25"), with_start("p75"), c, t["band"][1])
        ax.plot(x, with_start("p50"), color=c)
        ax.axhline(100 * d["d0"], color=t["axis"], lw=1)
        prob = float(fan["prob_higher_than_start"].iloc[-1])
        ax.set_title(f"{name}\nP(debt in {x[-1]} above {d['start_year']}) = {prob:.0%}", loc="left", fontsize=10,
                     color=t["ink2"])
        ax.annotate(f"median\n{with_start('p50')[-1]:.0f}%", (x[-1], with_start("p50")[-1]), xytext=(6, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=9, color=t["ink2"], annotation_clip=False)
        percent_axis(ax)
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    axes[0].legend(handles=[Line2D([], [], color=c, label="median"), Patch(color=c, alpha=t["band"][1], lw=0, label="50% of paths"),
                            Patch(color=c, alpha=t["band"][0], lw=0, label="90% of paths")], loc="lower left", ncol=3)
    header(fig, t, "Without adjustment the debt ratio is as likely to rise as to fall",
           "Stochastic debt projections, % of GDP: 100,000 paths with VAR(1) shocks to growth, inflation and rates",
           d["source"].format(datasets="gov_10dd_edpt1, nama_10_gdp, irt_lt_mcby_a") + "; model in notebook 4, seed 20250101")
    fig.subplots_adjust(top=0.72)
    return fig


FIGURES = {"debt_ratio": debt_ratio, "debt_decomposition": decomposition, "spending_gap": spending_gap,
           "debt_fan_chart": fan_chart}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Draw the README figures (light and dark variants).")
    parser.add_argument("--out", default=str(data.repository_root() / "docs" / "figures"))
    parser.add_argument("--synthetic", action="store_true", help="use offline placeholder data")
    parser.add_argument("--paths", type=int, default=100_000)
    args = parser.parse_args(argv)
    import matplotlib
    matplotlib.use("Agg")
    d = load(official=not args.synthetic, n_paths=args.paths)
    for name, builder in FIGURES.items():
        for path in render(builder, name, Path(args.out), d):
            print(path)


if __name__ == "__main__":
    main()
