"""Render the base-engine conclusions as a Markdown report.

This is the same statistical pass as the network report, but scoped to the
non-network engine captures only:

- Godot
- Unity base
- Unity GPU
- Unity DOTS

The report reuses the already computed CSV outputs in ``analysis_results`` and
filters them down to the base-engine subset.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pandas as pd

from metrics_catalog import BASE_ENGINE_KEYS, METRICS as METRIC_CATALOG
import report_common as rc
from subsystem_catalog import BASE_ENGINE_DISPLAY as DISPLAY_LIBS, RAW_TO_DISPLAY


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_DIR = Path("analysis_results")
OUT_DIR = SOURCE_DIR / "base"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CROSS_PATH = SOURCE_DIR / "statistical_comparisons.csv"
RAW_PATH = SOURCE_DIR / "raw_per_file_metrics.csv"
SUMMARY_PATH = SOURCE_DIR / "summary_by_subsystem.csv"

OUT_CROSS_PATH = OUT_DIR / "statistical_comparisons.csv"
OUT_SIG_PATH = OUT_DIR / "statistical_comparisons_significant.csv"
OUT_RAW_PATH = OUT_DIR / "raw_per_file_metrics.csv"
OUT_SUMMARY_PATH = OUT_DIR / "summary_by_subsystem.csv"
OUT_MD = OUT_DIR / "conclusions_base.md"

BASE_RAW_LIBS = set(RAW_TO_DISPLAY.keys())
PLATFORMS = ["PC", "Quest"]

# Non-network metrics only (FPS, CPU, GPU, Memory), sourced from the shared
# metrics_catalog. Labels use the long/unit-suffixed convention (e.g.
# "CPU (ms)") because they're matched against analyze_data.py's `metric`
# column text in raw_per_file_metrics.csv / summary_by_subsystem.csv.
METRIC_LABELS = {m.long_label for m in METRIC_CATALOG if m.key in BASE_ENGINE_KEYS}
METRIC_KEYS = BASE_ENGINE_KEYS


# ---------------------------------------------------------------------------
# Helpers specific to this report (subsystem filtering / renaming)
# ---------------------------------------------------------------------------

def _rename_subsystems(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        out[col] = out[col].map(RAW_TO_DISPLAY)
    return out


def _promote_pc_generic_base(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            continue
        mask = out["platform"].eq("PC") & out[col].eq("Other")
        if "stat_file" in out.columns:
            mask &= out["stat_file"].astype(str).str.contains(r"profiler_stats-", na=False)
        out.loc[mask, col] = "Base"
    return out


def _load_scope_data():
    cross = pd.read_csv(CROSS_PATH)
    raw = pd.read_csv(RAW_PATH)
    summary = pd.read_csv(SUMMARY_PATH)

    cross = _promote_pc_generic_base(cross, ["A_subsystem", "B_subsystem"])
    raw = _promote_pc_generic_base(raw, ["subsystem"])
    summary = _promote_pc_generic_base(summary, ["subsystem"])

    cross = cross[cross["metric_key"].isin(METRIC_KEYS)].copy()
    cross = cross[
        cross["A_subsystem"].isin(BASE_RAW_LIBS)
        & cross["B_subsystem"].isin(BASE_RAW_LIBS)
    ].copy()
    cross = _rename_subsystems(cross, ["A_subsystem", "B_subsystem"])

    raw = raw[raw["metric"].isin(METRIC_LABELS) & raw["subsystem"].isin(BASE_RAW_LIBS)].copy()
    raw = _rename_subsystems(raw, ["subsystem"])

    summary = summary[summary["metric"].isin(METRIC_LABELS) & summary["subsystem"].isin(BASE_RAW_LIBS)].copy()
    summary = _rename_subsystems(summary, ["subsystem"])

    cross, cross_xl = rc.annotate_comparisons(cross, DISPLAY_LIBS)

    return cross, cross_xl, raw, summary


# ---------------------------------------------------------------------------
# Renderers specific to this report (header, methodology, takeaways, caveats)
# ---------------------------------------------------------------------------

def _render_header():
    today = _dt.date.today().isoformat()
    return (
        "# Unity Base Engine Benchmark — Conclusions\n\n"
        f"_Generated on {today} from the base-engine subset of the analysis outputs in `{SOURCE_DIR}`._\n\n"
        "This report keeps only the non-network engine metrics (FPS, CPU, GPU, Memory). Network and PCAP metrics are excluded because this pass is specifically for the base-engine comparison.\n\n"
        "---\n"
    )


def _render_methodology():
    return (
        "## Methodology\n\n"
        "For each stat file, the report reuses the previously computed per-frame observations and compares only the base-engine libraries: Godot, Unity base, Unity GPU, and Unity DOTS. The ranking uses the six pairwise comparisons among those four systems.\n\n"
        "Statistical comparison uses:\n\n"
        "- **Mann-Whitney U** (two-sided, normal approximation with tie correction, p-value via erf),\n"
        "- **Cliff's delta** effect size with Romano et al. (2006) thresholds: negligible |δ| < 0.147, small < 0.33, medium < 0.474, large ≥ 0.474,\n"
        "- a pair is treated as **decisive** when p < 0.05 *and* the effect is at least *small*.\n\n"
        "The report ignores network and PCAP metrics entirely, so the conclusions are driven only by FPS, CPU, GPU, and Memory.\n\n"
        "---\n"
    )


def _render_takeaways(cross_xl: pd.DataFrame):
    lines = ["## Takeaways", ""]
    for platform in PLATFORMS:
        sub = cross_xl[(cross_xl["platform"] == platform) & (cross_xl["decisive"])]
        if sub.empty:
            continue
        rows = []
        for _, r in sub.iterrows():
            for winner in r["winners"]:
                rows.append({"winner": winner, "weight": r["weight"]})
        if not rows:
            continue
        scores = pd.DataFrame(rows).groupby("winner")["weight"].sum().reindex(DISPLAY_LIBS, fill_value=0.0)
        top = scores.sort_values(ascending=False)
        leader = top.index[0]
        lines.append(
            f"- On {platform}, **{leader}** has the strongest weighted decisive-win score in this base-engine subset."
        )
    lines.append(
        "- The four-library comparison is strictly non-network: any network or PCAP metric was excluded from the ranking and the narrative."
    )
    lines.append("\n---\n")
    return "\n".join(lines)


def _render_caveats(raw_libs: pd.DataFrame):
    n_pc = raw_libs[raw_libs["platform"] == "PC"]["stat_file"].nunique()
    n_quest = raw_libs[raw_libs["platform"] == "Quest"]["stat_file"].nunique()
    return (
        "## Caveats and Confidence\n\n"
        f"1. **Small number of captures.** Each library's verdict comes from a limited set of captures per platform ({n_pc} PC stat files / {n_quest} Quest stat files in the filtered base subset).\n"
        "2. **FPS comparison is load-sensitive.** Some captures were taken under different scene loads, so FPS is a useful signal but should still be read alongside CPU and GPU.\n"
        "3. **Quest numbers are noisier.** Device thermal throttling, Wi-Fi quality, and Android scheduling all influence the Quest traces.\n"
    )


def _write_filtered_csvs(cross: pd.DataFrame, cross_xl: pd.DataFrame, raw: pd.DataFrame, summary: pd.DataFrame):
    raw.to_csv(OUT_RAW_PATH, index=False)
    summary.to_csv(OUT_SUMMARY_PATH, index=False)
    cross.to_csv(OUT_CROSS_PATH, index=False)
    sig = cross[cross["p_value"] < 0.05].copy()
    sig.to_csv(OUT_SIG_PATH, index=False)
    return sig


def main():
    if not CROSS_PATH.exists() or not RAW_PATH.exists() or not SUMMARY_PATH.exists():
        raise SystemExit("Expected analysis CSVs were not found in analysis_results/")

    cross, cross_xl, raw, summary = _load_scope_data()
    _write_filtered_csvs(cross, cross_xl, raw, summary)

    parts = [
        _render_header(),
        _render_methodology(),
        rc.render_overall_ranking(
            cross_xl, DISPLAY_LIBS, PLATFORMS,
            note=(
                "The score below is the sum of *weighted decisive wins* per library. A win counts 3 for a large effect, 2 for medium, 1 for small (negligible effects are ignored)."
            ),
        ),
        rc.render_per_metric_wins(
            cross_xl, DISPLAY_LIBS, PLATFORMS,
            note=(
                "Each cell is the weighted-win score of the library in that metric. Empty cells mean the library never won that metric with a decisive effect."
            ),
        ),
        rc.render_median_table(
            summary, DISPLAY_LIBS, PLATFORMS,
            heading="Median Values Per Library (summary medians)",
            note=(
                "These are the summary medians aggregated per subsystem from `summary_by_subsystem.csv` (that file already collapses multiple captures into one representative value per platform and library). All values are medians in the displayed unit. Lower is better for every metric except FPS."
            ),
        ),
        rc.render_per_library_section(
            cross_xl, DISPLAY_LIBS,
            heading="Per-library Analysis (pairwise-test medians)",
            note=(
                "Each section lists where the library wins (decisive positive effect vs at least one other library) and where it loses. The medians shown here come from the pairwise statistical-comparison rows in `statistical_comparisons.csv`, so they can differ from the summary table above because that table uses `median_of_medians` across captures. Effect sizes follow the Romano et al. (2006) thresholds."
            ),
        ),
        _render_takeaways(cross_xl),
        _render_caveats(raw),
    ]
    md = "\n".join(parts)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_MD} ({len(md):,} chars, {md.count(chr(10))} lines)")
    print(f"Wrote filtered CSVs to {OUT_DIR}")


if __name__ == "__main__":
    main()
