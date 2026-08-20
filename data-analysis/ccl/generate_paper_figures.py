"""Generates the three publication figures for the paper from Pipeline B's
load-based CSV exports (`analysis_results/load_based/*.csv`):

    fig1-cpu-vs-load : CPU time vs. load, 2 panels (PC / Quest), IQR band, log y
    fig2-capacity    : client/server entity ceilings, grouped bars
    fig3-forest      : forest plot of Cliff's delta vs. baseline at 20000 entities

Pure presentation layer -- reads the CSVs `load_analysis.py` already produces,
does no statistics of its own. Run after `load_analysis.py`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from subsystem_catalog import SUBSYSTEMS

# ---------------------------------------------------------------------------
# Shared style -- validated categorical palette (see dataviz skill,
# references/palette.md), extended with a 9th neutral slot since this
# project has 9 subsystems. Ordering matches SUBSYSTEMS in subsystem_catalog.
# ---------------------------------------------------------------------------

PALETTE = {
    "Base": "#2a78d6",             # blue
    "Base-GPU": "#eb6834",         # orange
    "DOTS": "#1baf7a",             # aqua
    "Godot": "#eda100",            # yellow
    "FishNet": "#e87ba4",          # magenta
    "Godot Network": "#008300",    # green
    "NGO": "#4a3aa7",              # violet
    "NetcodeEntities": "#e34948",  # red
    "Photon": "#6e6e6e",           # neutral gray (9th slot, outside the 8-hue set)
}
MARKERS = {
    "Base": "o", "Base-GPU": "s", "DOTS": "^", "Godot": "D",
    "FishNet": "v", "Godot Network": "P", "NGO": "X",
    "NetcodeEntities": "*", "Photon": "h",
}
LINESTYLES = {name: ("--" if name == "Photon" else "-") for name in PALETTE}

SUBSYSTEM_ORDER = [s.raw_name for s in SUBSYSTEMS]
DISPLAY_NAME = {s.raw_name: s.display_name for s in SUBSYSTEMS}

PLATFORM_COLOR = {"PC": "#2a78d6", "Quest": "#eb6834"}

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_PRIMARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_SECONDARY,
    "ytick.color": INK_SECONDARY,
    "axes.grid": True,
    "grid.color": GRIDLINE,
    "grid.linewidth": 0.6,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def _strip_role_suffix(config_id: str) -> str:
    return config_id.removesuffix("-client").removesuffix("-server")


# ---------------------------------------------------------------------------
# Figure 1 -- CPU vs load
# ---------------------------------------------------------------------------

def make_fig1_cpu_vs_load(metric_vs_load: pd.DataFrame, out_path: Path) -> None:
    df = metric_vs_load[metric_vs_load["metric_key"] == "cpu"].copy()
    df = df[df["role"].isna() | (df["role"] == "client")]

    platforms = ["PC", "Quest"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)

    for ax, platform in zip(axes, platforms):
        sub = df[df["platform"] == platform]
        for name in SUBSYSTEM_ORDER:
            series = sub[sub["subsystem"] == name].sort_values("entities")
            if series.empty:
                continue
            color = PALETTE[name]
            ax.fill_between(
                series["entities"], series["q1_of_medians"], series["q3_of_medians"],
                color=color, alpha=0.15, linewidth=0,
            )
            ax.plot(
                series["entities"], series["median_of_medians"],
                color=color, linestyle=LINESTYLES[name], marker=MARKERS[name],
                markevery=4, markersize=4.5, linewidth=1.6,
                label=DISPLAY_NAME[name],
            )
        ax.set_yscale("log")
        ax.set_title(platform, fontsize=11, color=INK_PRIMARY, loc="left")
        ax.set_xlabel("Entities (load)")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_ylabel("CPU time per frame (ms, log scale)")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=5, frameon=False,
        bbox_to_anchor=(0.5, -0.06), fontsize=8.5,
    )
    fig.suptitle("CPU cost vs. entity load", fontsize=13, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 -- capacity ceilings, client vs server
# ---------------------------------------------------------------------------

def _client_capacity_table(capacity_headline: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (platform, subsystem), group in capacity_headline.groupby(["platform", "subsystem"]):
        rows.append({
            "platform": platform, "subsystem": subsystem,
            "median_max_entities": float(group["max_entities_reached"].median()),
            "min_max_entities": int(group["max_entities_reached"].min()),
            "max_max_entities": int(group["max_entities_reached"].max()),
        })
    return pd.DataFrame(rows)


def make_fig2_capacity(capacity_headline: pd.DataFrame, server_capacity: pd.DataFrame, out_path: Path) -> None:
    client_cap = _client_capacity_table(capacity_headline)
    network_libs = [s.raw_name for s in SUBSYSTEMS if s.category == "network_library"]

    platforms = ["PC", "Quest"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)

    bar_width = 0.35
    x = range(len(network_libs))

    for ax, platform in zip(axes, platforms):
        client = client_cap[client_cap["platform"] == platform].set_index("subsystem")
        server = server_capacity[server_capacity["platform"] == platform].set_index("subsystem")

        client_vals = [client.loc[s, "median_max_entities"] if s in client.index else 0 for s in network_libs]
        client_err_lo = [
            (client.loc[s, "median_max_entities"] - client.loc[s, "min_max_entities"]) if s in client.index else 0
            for s in network_libs
        ]
        client_err_hi = [
            (client.loc[s, "max_max_entities"] - client.loc[s, "median_max_entities"]) if s in client.index else 0
            for s in network_libs
        ]
        server_vals = [server.loc[s, "median_max_entities"] if s in server.index else 0 for s in network_libs]
        server_err_lo = [
            (server.loc[s, "median_max_entities"] - server.loc[s, "min_max_entities"]) if s in server.index else 0
            for s in network_libs
        ]
        server_err_hi = [
            (server.loc[s, "max_max_entities"] - server.loc[s, "median_max_entities"]) if s in server.index else 0
            for s in network_libs
        ]

        ax.bar(
            [i - bar_width / 2 for i in x], client_vals, bar_width,
            yerr=[client_err_lo, client_err_hi], capsize=2.5,
            color=PLATFORM_COLOR["PC"], label="Client ceiling", error_kw={"ecolor": INK_SECONDARY, "elinewidth": 0.8},
        )
        ax.bar(
            [i + bar_width / 2 for i in x], server_vals, bar_width,
            yerr=[server_err_lo, server_err_hi], capsize=2.5,
            color=PLATFORM_COLOR["Quest"], label="Server ceiling", error_kw={"ecolor": INK_SECONDARY, "elinewidth": 0.8},
        )
        ax.axhline(20000, color=BASELINE, linewidth=1, linestyle=":", zorder=0)
        ax.set_xticks(list(x))
        ax.set_xticklabels([DISPLAY_NAME[s] for s in network_libs], rotation=30, ha="right")
        ax.set_title(platform, fontsize=11, color=INK_PRIMARY, loc="left")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_ylabel("Max entities reached")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Client vs. server entity ceilings", fontsize=13, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0.08, 1, 0.96))
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3 -- forest plot of Cliff's delta at 20000 entities
# ---------------------------------------------------------------------------

def make_fig3_forest(forest_df: pd.DataFrame, out_path: Path) -> None:
    sub = forest_df[
        (forest_df["metric_key"] == "cpu")
        & (forest_df["resolved_load"] == 20000)
        & (forest_df["comparison_family"] == "baseline")
    ].copy()
    sub["label"] = sub.apply(
        lambda r: f"{DISPLAY_NAME.get(_strip_role_suffix(r.subsystem_b), r.subsystem_b)} vs. "
                  f"{DISPLAY_NAME.get(_strip_role_suffix(r.subsystem_a), r.subsystem_a)}",
        axis=1,
    )
    sub = sub.sort_values(["platform", "cliffs_delta"], ascending=[True, True]).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(7.5, 0.42 * len(sub) + 1.6))
    y_positions = range(len(sub))

    for y, row in zip(y_positions, sub.itertuples(index=False)):
        color = PLATFORM_COLOR[row.platform]
        filled = bool(row.significant)
        ax.plot(
            [row.cliffs_delta], [y], marker="o", markersize=7,
            markerfacecolor=color if filled else "white",
            markeredgecolor=color, markeredgewidth=1.6, linestyle="none", zorder=3,
        )
        ax.hlines(y, 0, row.cliffs_delta, color=color, linewidth=1, alpha=0.35, zorder=1)

    ax.axvline(0, color=BASELINE, linewidth=1)
    ax.set_xlim(-1.08, 1.08)
    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(sub["label"], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Cliff's delta (CPU time, subsystem vs. its baseline)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.6)
    ax.grid(axis="y", visible=False)

    legend_handles = [
        plt.Line2D([0], [0], marker="o", linestyle="none", markersize=7,
                   markerfacecolor=PLATFORM_COLOR[p], markeredgecolor=PLATFORM_COLOR[p], label=p)
        for p in ["PC", "Quest"] if p in sub["platform"].unique()
    ]
    legend_handles.append(
        plt.Line2D([0], [0], marker="o", linestyle="none", markersize=7,
                   markerfacecolor="white", markeredgecolor=INK_SECONDARY, label="Not significant (Holm)")
    )
    ax.legend(
        handles=legend_handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, fontsize=8.5, borderaxespad=0,
    )

    fig.suptitle("Cliff's delta vs. baseline at 20000 entities", fontsize=13, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 0.86, 0.96))
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path,
        default=Path(__file__).parent / "analysis_results" / "load_based",
        help="Directory containing load_analysis.py's CSV exports.",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(__file__).parent / "analysis_results" / "figures",
        help="Directory to write the figures into.",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    metric_vs_load = pd.read_csv(args.input_dir / "metric_vs_load.csv")
    capacity_headline = pd.read_csv(args.input_dir / "capacity_headline.csv")
    server_capacity = pd.read_csv(args.input_dir / "server_capacity.csv")
    forest_df = pd.read_csv(args.input_dir / "cliffs_delta_forest.csv")

    make_fig1_cpu_vs_load(metric_vs_load, args.output_dir / "fig1-cpu-vs-load.png")
    make_fig2_capacity(capacity_headline, server_capacity, args.output_dir / "fig2-capacity.png")
    make_fig3_forest(forest_df, args.output_dir / "fig3-forest.png")

    print(f"Figures written to {args.output_dir}")


if __name__ == "__main__":
    main()
