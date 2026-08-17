"""Shared rendering helpers for the Markdown conclusion reports.

`render_conclusions.py` (cross-library network report) and
`render_base_conclusions.py` (base-engine report) run the same
decisive-win / per-library-strength statistical pass over a different
subsystem subset. This module holds the parts that don't vary between
them; each script keeps its own header/methodology/caveats prose and its
own subsystem list.
"""
from __future__ import annotations

import pandas as pd

WEIGHT = {"large": 3.0, "medium": 2.0, "small": 1.0, "negligible": 0.0}


def format_med(value, unit, digits=2):
    if pd.isna(value):
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.0f} {unit}"
    return f"{value:,.{digits}f} {unit}"


def winners(row):
    if row["p_value"] >= 0.05:
        return set()
    verdict = str(row["verdict"])
    if verdict.startswith("A "):
        return {row["A_subsystem"]}
    if verdict.startswith("B "):
        return {row["B_subsystem"]}
    return set()


def is_decisive(row):
    return (row["p_value"] < 0.05) and (row["effect_size"] in ("small", "medium", "large"))


def annotate_comparisons(cross: pd.DataFrame, libs: list[str]):
    """Add winners/decisive/crosslib/weight columns.

    Returns (cross, cross_xl) where cross_xl is the subset restricted to
    pairs where both sides are in `libs`.
    """
    cross = cross.copy()
    cross["winners"] = cross.apply(winners, axis=1)
    cross["decisive"] = cross.apply(is_decisive, axis=1)
    cross["crosslib"] = cross["A_subsystem"].isin(libs) & cross["B_subsystem"].isin(libs)
    cross["weight"] = cross["effect_size"].map(WEIGHT).fillna(0.0)
    return cross, cross[cross["crosslib"]].copy()


def _weighted_wins(cross_xl: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in cross_xl.iterrows():
        if not r["decisive"]:
            continue
        for w in r["winners"]:
            rows.append({"platform": r["platform"], "metric": r["metric"], "winner": w, "weight": r["weight"]})
    return pd.DataFrame(rows)


def render_overall_ranking(cross_xl: pd.DataFrame, libs: list[str], platforms: list[str], *, note: str) -> str:
    """Top-level per-platform ranking table."""
    wins = _weighted_wins(cross_xl)
    if wins.empty:
        return "## Overall Ranking\n\n_No decisive cross-library pairs found._\n\n---\n"

    lines = ["## Overall Ranking", "", note, ""]
    for platform in platforms:
        sub = wins[wins["platform"] == platform]
        if sub.empty:
            continue
        scores = sub.groupby("winner")["weight"].sum().reindex(libs, fill_value=0.0)
        scores = scores.sort_values(ascending=False)
        lines.append(f"### {platform}\n")
        lines.append("| Rank | Library | Score |")
        lines.append("|:----:|:--------|------:|")
        for rank, (lib, s) in enumerate(scores.items(), 1):
            lines.append(f"| {rank} | {lib} | {s:.1f} |")
        lines.append("")

    return "\n".join(lines) + "\n---\n"


def render_per_metric_wins(cross_xl: pd.DataFrame, libs: list[str], platforms: list[str], *, note: str) -> str:
    """Per-metric pivot of weighted wins."""
    wins = _weighted_wins(cross_xl)
    if wins.empty:
        return ""

    lines = ["## Per-metric Breakdown", "", note, ""]
    metrics_in_data = sorted(wins["metric"].unique())
    for platform in platforms:
        sub = wins[wins["platform"] == platform]
        if sub.empty:
            continue
        pivot = sub.groupby(["metric", "winner"])["weight"].sum().unstack(fill_value=0.0)
        for lib in libs:
            if lib not in pivot.columns:
                pivot[lib] = 0.0
        pivot = pivot[libs]
        pivot = pivot.loc[pivot.index.isin(metrics_in_data)]
        lines.append(f"### {platform}\n")
        lines.append("| Metric | " + " | ".join(libs) + " |")
        lines.append("|:-------|" + "|".join([":----:"] * len(libs)) + "|")
        for metric, row in pivot.iterrows():
            cells = [f"**{row[lib]:.0f}**" if row[lib] == row.max() and row[lib] > 0 else f"{row[lib]:.0f}" for lib in libs]
            lines.append(f"| {metric} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n---\n"


def render_median_table(summary_libs: pd.DataFrame, libs: list[str], platforms: list[str], *, heading: str, note: str) -> str:
    """Side-by-side median table for all libraries x metrics x platforms."""
    lines = [f"## {heading}", "", note, ""]

    def _is_best(metric, lib, pivot):
        if metric not in pivot.index or lib not in pivot.columns:
            return False
        v = pivot.at[metric, lib]
        if v == 0 or pd.isna(v):
            return False
        row = pivot.loc[metric]
        if metric == "FPS":
            return v == row.max() and v > 0
        return v == row.min() and v > 0

    for platform in platforms:
        sub = summary_libs[summary_libs["platform"] == platform]
        if sub.empty:
            continue
        lines.append(f"### {platform}\n")
        pivot = sub.pivot_table(index="metric", columns="subsystem", values="median_of_medians", aggfunc="first")
        for lib in libs:
            if lib not in pivot.columns:
                pivot[lib] = float("nan")
        pivot = pivot[libs]

        lines.append("| Metric | Unit | " + " | ".join(libs) + " |")
        lines.append("|:-------|:----:|" + "|".join([":----:"] * len(libs)) + "|")
        for metric, row in pivot.iterrows():
            unit = sub[sub["metric"] == metric]["unit"].iloc[0] if not sub[sub["metric"] == metric].empty else ""
            cells = []
            for lib in libs:
                v = row[lib]
                cell = "—" if pd.isna(v) else format_med(v, unit)
                if _is_best(metric, lib, pivot):
                    cell = f"**{cell}**"
                cells.append(cell)
            lines.append(f"| {metric} | {unit} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n---\n"


def collect_strengths_weaknesses(cross_xl: pd.DataFrame, lib: str):
    """Return (wins, losses) lists of dicts for `lib` from decisive
    cross-library pairs. Each row carries `library_side` ("A" or "B") so
    the renderer can show a correct "opponent -> lib" direction regardless
    of which side of the pair `lib` happened to land on."""
    wins, losses = [], []
    for _, r in cross_xl.iterrows():
        if not r["decisive"]:
            continue
        if r["A_subsystem"] == lib:
            side, opponent = "A", r["B_subsystem"]
        elif r["B_subsystem"] == lib:
            side, opponent = "B", r["A_subsystem"]
        else:
            continue
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
            "library_side": side,
        }
        verdict = str(r["verdict"])
        (wins if verdict.startswith(f"{side} ") else losses).append(row)
    return wins, losses


def _bullet(entry, *, is_win: bool) -> str:
    med_a = format_med(entry["median_A"], entry["unit"])
    med_b = format_med(entry["median_B"], entry["unit"])
    lib_is_a = entry["library_side"] == "A"
    if is_win:
        before, after = (med_b, med_a) if lib_is_a else (med_a, med_b)
    else:
        before, after = (med_a, med_b) if lib_is_a else (med_b, med_a)
    return (
        f"- **{entry['platform']} · {entry['metric']}** — vs "
        f"{entry['opponent']} ({before} → {after}), "
        f"δ = {entry['delta']:+.2f} ({entry['effect_size']}), "
        f"p = {entry['p_value']:.2e}"
    )


def render_per_library_section(cross_xl: pd.DataFrame, libs: list[str], *, heading: str, note: str) -> str:
    """One section per library describing its strengths and weaknesses."""
    lines = [f"## {heading}", "", note, ""]

    for lib in libs:
        lines.append(f"### {lib}\n")
        wins, losses = collect_strengths_weaknesses(cross_xl, lib)
        if not wins and not losses:
            lines.append("_No decisive cross-library comparisons._\n")
            continue

        lines.append("**Strengths** (where it beats the others):\n")
        if wins:
            for w in sorted(wins, key=lambda x: (x["platform"], x["metric"])):
                lines.append(_bullet(w, is_win=True))
        else:
            lines.append("- _(none)_")
        lines.append("")

        lines.append("**Weaknesses** (where it loses to the others):\n")
        if losses:
            for l in sorted(losses, key=lambda x: (x["platform"], x["metric"])):
                lines.append(_bullet(l, is_win=False))
        else:
            lines.append("- _(none)_")
        lines.append("")

    lines.append("---\n")
    return "\n".join(lines)
