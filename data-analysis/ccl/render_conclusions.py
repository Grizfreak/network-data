"""Render the cross-library conclusions as a Markdown report."""
import datetime as _dt
import pandas as pd
from pathlib import Path

import report_common as rc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUT_DIR = Path("analysis_results")
CROSS_PATH = OUT_DIR / "statistical_comparisons.csv"
RAW_PATH = OUT_DIR / "raw_per_file_metrics.csv"
SUMMARY_PATH = OUT_DIR / "summary_by_subsystem.csv"
OUT_MD = OUT_DIR / "conclusions.md"

LIBS = ["Photon", "NGO", "FishNet", "NetcodeEntities", "Godot Network"]
PLATFORMS = ["PC", "Quest"]


# ---------------------------------------------------------------------------
# Build the data
# ---------------------------------------------------------------------------

def load_data():
    cross = pd.read_csv(CROSS_PATH)
    cross, cross_xl = rc.annotate_comparisons(cross, LIBS)

    raw = pd.read_csv(RAW_PATH)
    raw_libs = raw[raw["subsystem"].isin(LIBS)].copy()
    summary = pd.read_csv(SUMMARY_PATH)
    summary_libs = summary[summary["subsystem"].isin(LIBS)].copy()
    return cross, cross_xl, raw, raw_libs, summary_libs


# ---------------------------------------------------------------------------
# Renderers specific to this report (header, methodology, use cases, caveats)
# ---------------------------------------------------------------------------

def render_header(raw: pd.DataFrame):
    today = _dt.date.today().isoformat()
    folder_names = sorted(raw["folder"].unique())
    if len(folder_names) <= 4:
        folders_desc = ", ".join(f"`data/{name}`" for name in folder_names)
    else:
        folders_desc = f"{len(folder_names)} run folders under `data/`"
    return (
        "# Unity Network Library Benchmark — Conclusions\n\n"
        f"_Generated on {today} from {folders_desc}._\n\n"
        "All numbers come from "
        "[analyze_data.py](../analyze_data.py) and are based on per-frame "
        "observations (not per-file medians), so the statistical tests reflect "
        "the true distribution of samples.\n\n"
        "---\n"
    )


def render_methodology():
    return (
        "## Methodology\n\n"
        "For every stat file, the analyzer reuses the Streamlit "
        "`metrics_engine` helpers to:\n\n"
        "- extract the metric time series (FPS, CPU, GPU, Memory, Network "
        "RTT/Ping, throughput, PCAP rates),\n"
        "- normalise units (ns→ms, bytes→MB, byte-rate from cumulative "
        "counters, latency sentinel removal),\n"
        "- auto-pair with the matching event file to enable per-GameObject "
        "aggregation (not used for the cross-library ranking in this report).\n\n"
        "Statistical comparison uses:\n\n"
        "- **Mann-Whitney U** (two-sided, normal approximation with tie "
        "correction, p-value via erf — implemented in pure Python so no SciPy "
        "is required),\n"
        "- **Cliff's delta** effect size with Romano et al. (2006) thresholds: "
        "negligible |δ| < 0.147, small < 0.33, medium < 0.474, large ≥ 0.474,\n"
        "- a pair is treated as **decisive** when p < 0.05 *and* the effect is "
        "at least *small*.\n\n"
        "Only the five cross-library pairs (Photon, NGO, FishNet, "
        "NetcodeEntities, Godot Network) are used for the ranking. "
        "Captures "
        "classified as `Other` / `Base*` are excluded so they do not skew "
        "the conclusions.\n\n"
        "---\n"
    )


def render_use_cases():
    return (
        "## Recommended Use Cases\n\n"
        "| Library | Best fit | Why |\n"
        "|:--------|:---------|:----|\n"
        "| **NetcodeEntities** | Default for any action / multiplayer / "
        "DOTS-style project on either platform | Lowest CPU, lowest latency, "
        "highest FPS in every cross-library comparison with a meaningful "
        "effect size. |\n"
        "| **Photon** | Slow-paced / turn-based / chatty-but-cheap networks "
        "on bandwidth-constrained links | Lowest wire traffic (Bytes/s, "
        "Packets/s) — ideal when cellular data or congested Wi-Fi is the "
        "bottleneck. Also: most mature, biggest ecosystem, Relay service for "
        "NAT traversal. |\n"
        "| **Godot Network** | Godot networked gameplay where throughput and "
        "frame pacing matter more than absolute memory savings | Stronger "
        "PC-side throughput and FPS than the baseline Godot captures, while "
        "keeping the Godot-specific workflow and content pipeline. |\n"
        "| **FishNet** | Quest / mobile titles with strict RAM budgets | "
        "Roughly half the memory of the other libraries with comparable CPU "
        "and FPS. Strong community and Predict / prediction system for "
        "competitive games if you can tolerate the higher latency. |\n"
        "| **NGO** | Small-scale prototypes or non-real-time workloads "
        "(lobbies, social features, infrequent state sync) | Fine on tiny "
        "workloads, but cost scales badly. Do not pick it for stress-tested or "
        "real-time scenes. |\n\n"
        "---\n"
    )


def render_caveats(cross_xl, raw_libs):
    n_captures_pc = raw_libs[raw_libs["platform"] == "PC"]["stat_file"].nunique()
    n_captures_quest = raw_libs[raw_libs["platform"] == "Quest"]["stat_file"].nunique()
    return (
        "## Caveats and Confidence\n\n"
        "1. **Small number of captures.** Each library's RTT verdict comes from "
        "very few captures per platform "
        f"({n_captures_pc} PC stat files / {n_captures_quest} Quest stat files "
        "in total). The p-values are tiny because the *within-capture* sample "
        "size is large, not because we have many independent runs. Adding two "
        "or three more captures per library would materially strengthen the "
        "conclusions.\n"
        "2. **FPS comparison is load-imbalanced.** Some `NetcodeEntities` "
        "captures were taken at low GameObject counts, which inflates the "
        "median FPS. Treat the FPS numbers as a hint rather than a clean "
        "comparison; CPU and RTT are the more reliable signals.\n"
        "3. **The `Other` subsystem** in the raw data contains outliers (e.g. "
        "a 55 MB/s Quest download). It is excluded from this report but worth "
        "investigating in case it is a misnamed capture.\n"
        "4. **PCAP traffic differences** are mostly real (Photon sends "
        "larger-but-rarer messages, NGO and FishNet send smaller-but-frequent "
        "ones), but a single benchmark scene is not enough to claim a "
        "universal pattern. They are useful as a trade-off signal, not as a "
        "ranking.\n"
        "5. **Quest numbers are noisier** because the device's thermal "
        "throttling, Wi-Fi link quality, and Android scheduler all show up in "
        "the data. The relative ordering of the libraries is consistent with "
        "PC, but absolute values fluctuate more between runs.\n"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cross, cross_xl, raw, raw_libs, summary_libs = load_data()

    parts = [
        render_header(raw),
        render_methodology(),
        rc.render_overall_ranking(
            cross_xl, LIBS, PLATFORMS,
            note=(
                "The score below is the sum of *weighted decisive wins* per library. "
                "A win counts 3 for a large effect, 2 for medium, 1 for small "
                "(negligible effects are ignored). The metric is symmetrical — a "
                "library that is *worse* on a metric gets 0 there, and a library that "
                "is *better* on a metric adds to its score."
            ),
        ),
        rc.render_per_metric_wins(
            cross_xl, LIBS, PLATFORMS,
            note=(
                "Each cell is the weighted-win score of the library in that metric. "
                "Empty cells mean the library never *won* that metric (i.e. it was "
                "either beaten by all other libraries with a non-negligible effect, "
                "or the comparison was not significant)."
            ),
        ),
        rc.render_median_table(
            summary_libs, LIBS, PLATFORMS,
            heading="Median Values Per Library (raw numbers)",
            note=(
                f"These are the medians aggregated from "
                f"`{'/'.join(SUMMARY_PATH.parts)}`. All values are medians in the "
                "displayed unit. Lower is better for every metric except FPS."
            ),
        ),
        rc.render_per_library_section(
            cross_xl, LIBS,
            heading="Per-library Analysis",
            note=(
                "Each section lists where the library *wins* (decisive positive effect "
                "vs at least one other library) and where it *loses* (decisive negative "
                "effect). Effect sizes follow the Romano et al. (2006) thresholds."
            ),
        ),
        render_use_cases(),
        render_caveats(cross_xl, raw_libs),
    ]
    md = "\n".join(parts)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_MD} ({len(md):,} chars, {md.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
