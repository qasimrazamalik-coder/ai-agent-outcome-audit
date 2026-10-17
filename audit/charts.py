"""Static charts for the report (PNG). Colors: reference categorical slots 1-2."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

BLUE = "#2a78d6"     # true resolution / firm recommendation
LIGHT_BLUE = "#9fc3ee"  # test first
ORANGE = "#eb6834"   # vendor containment
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def money(v: float) -> str:
    sign = "-" if v < 0 else ""
    v = abs(v)
    return f"{sign}${v / 1000:,.1f}k" if v >= 1000 else f"{sign}${v:,.0f}"


def money_k(v: float, _pos=None) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v) / 1000:,.0f}k" if v else "$0"


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def containment_vs_resolution_chart(df: pd.DataFrame, path: Path) -> None:
    """Dumbbell: what the vendor reports (containment) vs what happened (true resolution)."""
    d = df[df["intent_code"] != "UNCLASSIFIED"].sort_values("containment_gap")
    fig, ax = plt.subplots(figsize=(8.5, 0.42 * len(d) + 1.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    y = range(len(d))
    for i, r in enumerate(d.itertuples()):
        ax.plot([r.true_resolution, r.containment], [i, i], color=GRID, linewidth=2.5, zorder=1)
        ax.plot([r.true_resolution_low, r.true_resolution_high], [i, i], color=BLUE, linewidth=1.2, alpha=0.6, zorder=2)
    ax.scatter(d["containment"], y, s=46, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=3, label="Vendor containment")
    ax.scatter(d["true_resolution"], y, s=46, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
               label="True resolution (95% CI)")
    ax.set_yticks(list(y))
    ax.set_yticklabels([s.split(" > ")[-1] for s in d["driver"]], color=INK, fontsize=9)
    ax.set_xlim(0, 1.02)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("The bot reports containment, not resolution", loc="left", fontsize=12, color=INK, pad=24)
    ax.text(0, 1.02, "Share of bot sessions, by contact driver. Gap = contained but not actually solved.",
            transform=ax.transAxes, fontsize=9, color=MUTED)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.05), ncol=2, frameon=False, fontsize=9, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def value_by_driver_chart(df: pd.DataFrame, path: Path) -> None:
    """Annual value of routing each driver straight to an agent (negative = keep on bot)."""
    d = df[(df["recommendation"] != "insufficient volume") & (df["intent_code"] != "UNCLASSIFIED")]
    d = d.sort_values("annual_value_of_switching")
    fig, ax = plt.subplots(figsize=(8.5, 0.42 * len(d) + 1.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    colors = [
        GRID if r.recommendation != "route to agent" else (BLUE if r.robust_at_low_churn_bound else LIGHT_BLUE)
        for r in d.itertuples()
    ]
    ax.barh(range(len(d)), d["annual_value_of_switching"], color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels([s.split(" > ")[-1] for s in d["driver"]], color=INK, fontsize=9)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5000))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(money_k))
    for i, r in enumerate(d.itertuples()):
        if r.recommendation == "route to agent":
            ax.text(r.annual_value_of_switching, i, "  " + money(r.annual_value_of_switching), va="center",
                    fontsize=8.5, color=INK)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="Switch now"), Patch(color=LIGHT_BLUE, label="Test on half the traffic first"),
                       Patch(color=GRID, label="Keep on bot")],
              loc="upper left", bbox_to_anchor=(0, -0.05), ncol=3, frameon=False, fontsize=9, labelcolor=INK)
    ax.set_title("Where skipping the bot pays", loc="left", fontsize=12, color=INK, pad=24)
    ax.text(0, 1.02, "Annual value of routing each driver straight to an agent (cost to resolve + churn risk).",
            transform=ax.transAxes, fontsize=9, color=MUTED)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
