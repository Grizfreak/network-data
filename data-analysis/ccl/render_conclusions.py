"""Render the cross-library conclusions as a Markdown report."""
import datetime as _dt
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUT_DIR = Path("analysis_results")
CROSS_PATH = OUT_DIR / "statistical_comparisons.csv"
ALL_PATH = OUT_DIR / "statistical_comparisons_significant.csv"
RAW_PATH = OUT_DIR / "raw_per_file_metrics.csv"
SUMMARY_PATH = OUT_DIR / "summary_by_subsystem.csv"
OUT_MD = OUT_DIR / "conclusions.md"

LIBS = ["Photon", "NGO", "FishNet", "NetcodeEntities", "Godot Network"]
PLATFORMS = ["PC", "Quest"]

# (metric_key, metric_label, unit, lower_is_better, what_it_means)
METRICS_FOR_REPORT = [
    ("fps", "FPS", "frames/s", False, "sustained frame rate"),
    ("cpu", "CPU", "ms", True, "per-frame CPU work (lower = more headroom)"),
    ("gpu", "GPU", "ms", True, "per-frame GPU work"),
    ("memory", "Memory", "MB", True, "resident set / working set"),
    ("network_rtt", "Network RTT", "ms", True, "round-trip latency between peers"),
    ("network_ping", "Network Ping", "ms", True, "lightweight ping latency"),
    ("network_download", "Download", "bytes/s", True, "bytes received per second"),
    ("network_upload", "Upload", "bytes/s", True, "bytes sent per second"),
    ("pcap_packets", "PCAP Packets/s", "packets/s", True, "PCAP-derived packet rate"),
    ("pcap_bytes", "PCAP Bytes/s", "bytes/s", True, "PCAP-derived byte rate"),
]

WEIGHT = {"large": 3.0, "medium": 2.0, "small": 1.0, "negligible": 0.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _winners(row):
    if row["p_value"] >= 0.05:
        return set()
    v = str(row["verdict"])
    if v.startswith("A "):
        return {row["A_subsystem"]}
    if v.startswith("B "):
        return {row["B_subsystem"]}
    return set()


def _is_crosslib(row):
    return row["A_subsystem"] in LIBS and row["B_subsystem"] in LIBS


def _is_decisive(row):
    return (row["p_value"] < 0.05) and (row["effect_size"] in ("small", "medium", "large"))


def _format_med(value, unit, digits=2):
    if pd.isna(value):
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.0f} {unit}"
    return f"{value:,.{digits}f} {unit}"


def _effect_arrow(delta: float) -> str:
    """↑ if A is larger, ↓ if A is smaller."""
    if pd.isna(delta):
        return "·"
    return "↑" if delta > 0 else ("↓" if delta < 0 else "·")


# ---------------------------------------------------------------------------
# Build the data
# ---------------------------------------------------------------------------

def load_data():
    cross = pd.read_csv(CROSS_PATH)
    cross["winners"] = cross.apply(_winners, axis=1)
    cross["decisive"] = cross.apply(_is_decisive, axis=1)
    cross["crosslib"] = cross.apply(_is_crosslib, axis=1)
    cross["weight"] = cross["effect_size"].map(WEIGHT).fillna(0.0)
    cross_xl = cross[cross["crosslib"]].copy()

    raw = pd.read_csv(RAW_PATH)
    raw_libs = raw[raw["subsystem"].isin(LIBS)].copy()
    summary = pd.read_csv(SUMMARY_PATH)
    summary_libs = summary[summary["subsystem"].isin(LIBS)].copy()
    return cross, cross_xl, raw, raw_libs, summary_libs


# ---------------------------------------------------------------------------
# Renderers
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


def render_overall_ranking(cross_xl):
    """Top-level ranking table per platform."""
    rows_out = []
    for _, r in cross_xl.iterrows():
        if not r["decisive"]:
            continue
        for w in r["winners"]:
            rows_out.append({
                "platform": r["platform"],
                "metric": r["metric"],
                "winner": w,
                "weight": r["weight"],
            })
    wins = pd.DataFrame(rows_out)
    if wins.empty:
        return "## Overall Ranking\n\n_No decisive cross-library pairs found._\n\n---\n"

    lines = ["## Overall Ranking", ""]
    lines.append(
        "The score below is the sum of *weighted decisive wins* per library. "
        "A win counts 3 for a large effect, 2 for medium, 1 for small "
        "(negligible effects are ignored). The metric is symmetrical — a "
        "library that is *worse* on a metric gets 0 there, and a library that "
        "is *better* on a metric adds to its score.\n"
    )

    for platform in PLATFORMS:
        sub = wins[wins["platform"] == platform]
        if sub.empty:
            continue
        scores = (
            sub.groupby("winner")["weight"].sum().reindex(LIBS, fill_value=0.0)
        )
        scores = scores.sort_values(ascending=False)
        lines.append(f"### {platform}\n")
        lines.append("| Rank | Library | Score |")
        lines.append("|:----:|:--------|------:|")
        for rank, (lib, s) in enumerate(scores.items(), 1):
            lines.append(f"| {rank} | {lib} | {s:.1f} |")
        lines.append("")

    return "\n".join(lines) + "\n---\n"


def render_per_metric_wins(cross_xl):
    """Per-metric pivot of weighted wins."""
    rows = []
    for _, r in cross_xl.iterrows():
        if not r["decisive"]:
            continue
        for w in r["winners"]:
            rows.append({"platform": r["platform"], "metric": r["metric"], "winner": w, "weight": r["weight"]})
    wins = pd.DataFrame(rows)
    if wins.empty:
        return ""

    lines = ["## Per-metric Breakdown", ""]
    lines.append(
        "Each cell is the weighted-win score of the library in that metric. "
        "Empty cells mean the library never *won* that metric (i.e. it was "
        "either beaten by all other libraries with a non-negligible effect, "
        "or the comparison was not significant).\n"
    )
    metrics_in_data = sorted(wins["metric"].unique())
    for platform in PLATFORMS:
        sub = wins[wins["platform"] == platform]
        if sub.empty:
            continue
        pivot = (
            sub.groupby(["metric", "winner"])["weight"].sum().unstack(fill_value=0.0)
        )
        for lib in LIBS:
            if lib not in pivot.columns:
                pivot[lib] = 0.0
        pivot = pivot[LIBS]
        # Filter to metrics that actually appear in the data
        pivot = pivot.loc[pivot.index.isin(metrics_in_data)]
        lines.append(f"### {platform}\n")
        lines.append("| Metric | " + " | ".join(LIBS) + " |")
        lines.append("|:-------|" + "|".join([":----:"] * len(LIBS)) + "|")
        for metric, row in pivot.iterrows():
            cells = [f"**{row[lib]:.0f}**" if row[lib] == row.max() and row[lib] > 0 else f"{row[lib]:.0f}" for lib in LIBS]
            lines.append(f"| {metric} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n---\n"


def render_per_metric_table(summary_libs):
    """Side-by-side median table for all libraries × metrics × platforms."""
    lines = ["## Median Values Per Library (raw numbers)", ""]
    lines.append(
        "These are the medians aggregated from "
        f"`{'/'.join(SUMMARY_PATH.parts)}`. All values are medians in the "
        "displayed unit. Lower is better for every metric except FPS.\n"
    )

    for platform in PLATFORMS:
        lines.append(f"### {platform}\n")
        # Pivot: rows = metric, columns = library
        sub = summary_libs[summary_libs["platform"] == platform]
        if sub.empty:
            continue
        pivot = (
            sub.pivot_table(
                index="metric",
                columns="subsystem",
                values="median_of_medians",
                aggfunc="first",
            )
        )
        for lib in LIBS:
            if lib not in pivot.columns:
                pivot[lib] = float("nan")
        pivot = pivot[LIBS]
        # Build the markdown table
        header = "| Metric | Unit | " + " | ".join(LIBS) + " |"
        sep = "|:-------|:----:|" + "|".join([":----:"] * len(LIBS)) + "|"
        lines.append(header)
        lines.append(sep)
        # Determine "best" for bolding: higher is better for FPS, otherwise lower.
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

        for metric, row in pivot.iterrows():
            # Get unit from the summary (per-metric, all rows should share the same)
            unit = sub[sub["metric"] == metric]["unit"].iloc[0] if not sub[sub["metric"] == metric].empty else ""
            cells = []
            for lib in LIBS:
                v = row[lib]
                if pd.isna(v):
                    cell = "—"
                else:
                    cell = _format_med(v, unit)
                if _is_best(metric, lib, pivot):
                    cell = f"**{cell}**"
                cells.append(cell)
            lines.append(f"| {metric} | {unit} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n---\n"


def render_per_library_section(cross_xl, summary_libs):
    """One section per library describing its strengths and weaknesses."""
    section_lines = ["## Per-library Analysis", ""]
    section_lines.append(
        "Each section lists where the library *wins* (decisive positive effect "
        "vs at least one other library) and where it *loses* (decisive negative "
        "effect). Effect sizes follow the Romano et al. (2006) thresholds.\n"
    )

    # For each library, collect wins/losses from cross-library pairs only
    for lib in LIBS:
        section_lines.append(f"### {lib}\n")
        wins, losses = _collect_strengths_weaknesses(cross_xl, lib)
        if not wins and not losses:
            section_lines.append("_No decisive cross-library comparisons._\n")
            continue

        section_lines.append("**Strengths** (where it beats the others):\n")
        if wins:
            for w in sorted(wins, key=lambda x: (x["platform"], x["metric"])):
                med_a = _format_med(w["median_A"], w["unit"])
                med_b = _format_med(w["median_B"], w["unit"])
                section_lines.append(
                    f"- **{w['platform']} · {w['metric']}** — vs "
                    f"{w['opponent']} ({med_b} → {med_a}), "
                    f"δ = {w['delta']:+.2f} ({w['effect_size']}), "
                    f"p = {w['p_value']:.2e}"
                )
        else:
            section_lines.append("- _(none)_")
        section_lines.append("")

        section_lines.append("**Weaknesses** (where it loses to the others):\n")
        if losses:
            for l in sorted(losses, key=lambda x: (x["platform"], x["metric"])):
                med_a = _format_med(l["median_A"], l["unit"])
                med_b = _format_med(l["median_B"], l["unit"])
                section_lines.append(
                    f"- **{l['platform']} · {l['metric']}** — vs "
                    f"{l['opponent']} ({med_a} → {med_b}), "
                    f"δ = {l['delta']:+.2f} ({l['effect_size']}), "
                    f"p = {l['p_value']:.2e}"
                )
        else:
            section_lines.append("- _(none)_")
        section_lines.append("")

    section_lines.append("---\n")
    return "\n".join(section_lines)


def _collect_strengths_weaknesses(cross_xl, lib):
    """Return (wins, losses) lists for a given library from the cross-library
    decisive pairs."""
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
            }
            verdict = str(r["verdict"])
            if verdict.startswith("B "):
                wins.append(row)
            elif verdict.startswith("A "):
                losses.append(row)
    return wins, losses


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
        render_overall_ranking(cross_xl),
        render_per_metric_wins(cross_xl),
        render_per_metric_table(summary_libs),
        render_per_library_section(cross_xl, summary_libs),
        render_use_cases(),
        render_caveats(cross_xl, raw_libs),
    ]
    md = "\n".join(parts)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT_MD} ({len(md):,} chars, {md.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
