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

DISPLAY_LIBS = ["Godot", "Unity base", "Unity GPU", "Unity DOTS"]
RAW_TO_DISPLAY = {
    "Godot": "Godot",
    "Base": "Unity base",
    "Base-GPU": "Unity GPU",
    "DOTS": "Unity DOTS",
}
BASE_RAW_LIBS = set(RAW_TO_DISPLAY.keys())
PLATFORMS = ["PC", "Quest"]

# Non-network metrics only.
METRICS_FOR_REPORT = [
    ("fps", "FPS", "frames/s", False, "sustained frame rate"),
    ("cpu", "CPU (ms)", "ms", True, "per-frame CPU work (lower = more headroom)"),
    ("gpu", "GPU (ms)", "ms", True, "per-frame GPU work"),
    ("memory", "Memory (MB)", "MB", True, "resident set / working set"),
]
METRIC_LABELS = {label for _, label, _, _, _ in METRICS_FOR_REPORT}
METRIC_KEYS = {key for key, _, _, _, _ in METRICS_FOR_REPORT}

WEIGHT = {"large": 3.0, "medium": 2.0, "small": 1.0, "negligible": 0.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_med(value, unit, digits=2):
    if pd.isna(value):
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.0f} {unit}"
    return f"{value:,.{digits}f} {unit}"


def _winners(row):
    if row["p_value"] >= 0.05:
        return set()
    verdict = str(row["verdict"])
    if verdict.startswith("A "):
        return {row["A_subsystem"]}
    if verdict.startswith("B "):
        return {row["B_subsystem"]}
    return set()


def _is_crosslib(row):
    return row["A_subsystem"] in DISPLAY_LIBS and row["B_subsystem"] in DISPLAY_LIBS


def _is_decisive(row):
    return (row["p_value"] < 0.05) and (row["effect_size"] in ("small", "medium", "large"))


def _effect_arrow(delta: float) -> str:
    if pd.isna(delta):
        return "·"
    return "↑" if delta > 0 else ("↓" if delta < 0 else "·")


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

    cross["winners"] = cross.apply(_winners, axis=1)
    cross["decisive"] = cross.apply(_is_decisive, axis=1)
    cross["crosslib"] = cross.apply(_is_crosslib, axis=1)
    cross["weight"] = cross["effect_size"].map(WEIGHT).fillna(0.0)

    return cross, cross[cross["crosslib"]].copy(), raw, summary


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


def _render_overall_ranking(cross_xl: pd.DataFrame):
    rows_out = []
    for _, r in cross_xl.iterrows():
        if not r["decisive"]:
            continue
        for winner in r["winners"]:
            rows_out.append({
                "platform": r["platform"],
                "metric": r["metric"],
                "winner": winner,
                "weight": r["weight"],
            })

    wins = pd.DataFrame(rows_out)
    if wins.empty:
        return "## Overall Ranking\n\n_No decisive cross-library pairs found._\n\n---\n"

    lines = ["## Overall Ranking", ""]
    lines.append(
        "The score below is the sum of *weighted decisive wins* per library. A win counts 3 for a large effect, 2 for medium, 1 for small (negligible effects are ignored)."
    )
    lines.append("")

    for platform in PLATFORMS:
        sub = wins[wins["platform"] == platform]
        if sub.empty:
            continue
        scores = sub.groupby("winner")["weight"].sum().reindex(DISPLAY_LIBS, fill_value=0.0)
        scores = scores.sort_values(ascending=False)
        lines.append(f"### {platform}\n")
        lines.append("| Rank | Library | Score |")
        lines.append("|:----:|:--------|------:|")
        for rank, (lib, score) in enumerate(scores.items(), 1):
            lines.append(f"| {rank} | {lib} | {score:.1f} |")
        lines.append("")

    return "\n".join(lines) + "\n---\n"


def _render_per_metric_wins(cross_xl: pd.DataFrame):
    rows = []
    for _, r in cross_xl.iterrows():
        if not r["decisive"]:
            continue
        for winner in r["winners"]:
            rows.append({"platform": r["platform"], "metric": r["metric"], "winner": winner, "weight": r["weight"]})

    wins = pd.DataFrame(rows)
    if wins.empty:
        return ""

    lines = ["## Per-metric Breakdown", ""]
    lines.append(
        "Each cell is the weighted-win score of the library in that metric. Empty cells mean the library never won that metric with a decisive effect."
    )
    lines.append("")

    for platform in PLATFORMS:
        sub = wins[wins["platform"] == platform]
        if sub.empty:
            continue
        pivot = sub.groupby(["metric", "winner"])["weight"].sum().unstack(fill_value=0.0)
        for lib in DISPLAY_LIBS:
            if lib not in pivot.columns:
                pivot[lib] = 0.0
        pivot = pivot[DISPLAY_LIBS]
        lines.append(f"### {platform}\n")
        lines.append("| Metric | " + " | ".join(DISPLAY_LIBS) + " |")
        lines.append("|:-------|" + "|".join([":----:"] * len(DISPLAY_LIBS)) + "|")
        for metric, row in pivot.iterrows():
            cells = [f"**{row[lib]:.0f}**" if row[lib] == row.max() and row[lib] > 0 else f"{row[lib]:.0f}" for lib in DISPLAY_LIBS]
            lines.append(f"| {metric} | " + " | ".join(cells) + " |")
        lines.append("")

    return "\n".join(lines) + "\n---\n"


def _render_median_table(summary_libs: pd.DataFrame):
    lines = ["## Median Values Per Library (summary medians)", ""]
    lines.append(
        "These are the summary medians aggregated per subsystem from `summary_by_subsystem.csv` (that file already collapses multiple captures into one representative value per platform and library). All values are medians in the displayed unit. Lower is better for every metric except FPS."
    )
    lines.append("")

    for platform in PLATFORMS:
        sub = summary_libs[summary_libs["platform"] == platform]
        if sub.empty:
            continue
        lines.append(f"### {platform}\n")
        pivot = sub.pivot_table(index="metric", columns="subsystem", values="median_of_medians", aggfunc="first")
        for lib in DISPLAY_LIBS:
            if lib not in pivot.columns:
                pivot[lib] = float("nan")
        pivot = pivot[DISPLAY_LIBS]

        header = "| Metric | Unit | " + " | ".join(DISPLAY_LIBS) + " |"
        sep = "|:-------|:----:|" + "|".join([":----:"] * len(DISPLAY_LIBS)) + "|"
        lines.append(header)
        lines.append(sep)

        def _is_best(metric, lib, pivot_table):
            if metric not in pivot_table.index or lib not in pivot_table.columns:
                return False
            value = pivot_table.at[metric, lib]
            if value == 0 or pd.isna(value):
                return False
            row = pivot_table.loc[metric]
            if metric == "FPS":
                return value == row.max() and value > 0
            return value == row.min() and value > 0

        for metric, row in pivot.iterrows():
            unit = sub[sub["metric"] == metric]["unit"].iloc[0] if not sub[sub["metric"] == metric].empty else ""
            cells = []
            for lib in DISPLAY_LIBS:
                value = row[lib]
                cell = "—" if pd.isna(value) else _format_med(value, unit)
                if _is_best(metric, lib, pivot):
                    cell = f"**{cell}**"
                cells.append(cell)
            lines.append(f"| {metric} | {unit} | " + " | ".join(cells) + " |")
        lines.append("")

    return "\n".join(lines) + "\n---\n"


def _collect_strengths_weaknesses(cross_xl: pd.DataFrame, lib: str):
    wins = []
    losses = []
    for _, r in cross_xl.iterrows():
        if not r["decisive"]:
            continue
        if r["A_subsystem"] == lib:
            opponent = r["B_subsystem"]
            row = {
                "platform": r["platform"],
                "metric": r["metric"],
                "opponent": opponent,
                "median_A": r["median_A"],
                "median_B": r["median_B"],
                "unit": r["unit"],
                "delta": r["cliffs_delta"],
                "p_value": r["p_value"],
                "effect_size": r["effect_size"],
                "library_side": "A",
            }
            verdict = str(r["verdict"])
            if verdict.startswith("A "):
                wins.append(row)
            elif verdict.startswith("B "):
                losses.append(row)
        elif r["B_subsystem"] == lib:
            opponent = r["A_subsystem"]
            row = {
                "platform": r["platform"],
                "metric": r["metric"],
                "opponent": opponent,
                "median_A": r["median_A"],
                "median_B": r["median_B"],
                "unit": r["unit"],
                "delta": r["cliffs_delta"],
                "p_value": r["p_value"],
                "effect_size": r["effect_size"],
                "library_side": "B",
            }
            verdict = str(r["verdict"])
            if verdict.startswith("B "):
                wins.append(row)
            elif verdict.startswith("A "):
                losses.append(row)
    return wins, losses


def _render_per_library_section(cross_xl: pd.DataFrame):
    section_lines = ["## Per-library Analysis (pairwise-test medians)", ""]
    section_lines.append(
        "Each section lists where the library wins (decisive positive effect vs at least one other library) and where it loses. The medians shown here come from the pairwise statistical-comparison rows in `statistical_comparisons.csv`, so they can differ from the summary table above because that table uses `median_of_medians` across captures. Effect sizes follow the Romano et al. (2006) thresholds."
    )
    section_lines.append("")

    for lib in DISPLAY_LIBS:
        section_lines.append(f"### {lib}\n")
        wins, losses = _collect_strengths_weaknesses(cross_xl, lib)
        if not wins and not losses:
            section_lines.append("_No decisive cross-library comparisons._\n")
            continue

        section_lines.append("**Strengths** (where it beats the others):\n")
        if wins:
            for win in sorted(wins, key=lambda x: (x["platform"], x["metric"])):
                med_a = _format_med(win["median_A"], win["unit"])
                med_b = _format_med(win["median_B"], win["unit"])
                if win["library_side"] == "A":
                    before, after = med_b, med_a
                else:
                    before, after = med_a, med_b
                section_lines.append(
                    f"- **{win['platform']} · {win['metric']}** — vs {win['opponent']} ({before} → {after}), δ = {win['delta']:+.2f} ({win['effect_size']}), p = {win['p_value']:.2e}"
                )
        else:
            section_lines.append("- _(none)_")
        section_lines.append("")

        section_lines.append("**Weaknesses** (where it loses to the others):\n")
        if losses:
            for loss in sorted(losses, key=lambda x: (x["platform"], x["metric"])):
                med_a = _format_med(loss["median_A"], loss["unit"])
                med_b = _format_med(loss["median_B"], loss["unit"])
                if loss["library_side"] == "A":
                    before, after = med_a, med_b
                else:
                    before, after = med_b, med_a
                section_lines.append(
                    f"- **{loss['platform']} · {loss['metric']}** — vs {loss['opponent']} ({before} → {after}), δ = {loss['delta']:+.2f} ({loss['effect_size']}), p = {loss['p_value']:.2e}"
                )
        else:
            section_lines.append("- _(none)_")
        section_lines.append("")

    section_lines.append("---\n")
    return "\n".join(section_lines)


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
        _render_overall_ranking(cross_xl),
        _render_per_metric_wins(cross_xl),
        _render_median_table(summary),
        _render_per_library_section(cross_xl),
        _render_takeaways(cross_xl),
        _render_caveats(raw),
    ]
    md = "\n".join(parts)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_MD} ({len(md):,} chars, {md.count(chr(10))} lines)")
    print(f"Wrote filtered CSVs to {OUT_DIR}")


if __name__ == "__main__":
    main()