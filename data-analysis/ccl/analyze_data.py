"""
analyze_data.py
---------------
Comprehensive analysis script that processes all benchmark data folders
and generates insights using the existing metrics_engine infrastructure.

Strategy:
1. Load all stat + event files from each benchmark folder
2. Reuse metrics_engine helpers for unit normalization & per-GameObject aggregation
3. Pair stat files with event files using data_loader's auto_pair_files logic
4. Compute summary statistics (mean, median, p95, p99) for each metric
5. Compare runs across dates (e.g., different networking libs, different days)
6. Detect anomalies (huge spikes, drops, out-of-range units)
7. Export everything as structured text + CSV summaries in analysis_results/
"""

import sys
from pathlib import Path
from statistics import mean, median, pstdev

import pandas as pd
import numpy as np

# Make the streamlit package importable so we reuse the existing helpers.
# The analysis script lives under ccl/, while the shared modules live in the
# top-level streamlit/ folder.
sys.path.append(str(Path(__file__).resolve().parent.parent / "streamlit"))

from data_loader import (
    _is_quest_folder,
    auto_pair_files,
    classify_subsystem as _classify_file,
    is_networked_subsystem,
    is_quest_server_artefact,
    load_csv_files_from_folder,
)
from metrics_engine import (
    _has_network_columns,
    _has_pcap_columns,
    metric_per_gameobject_series,
    metric_series_from_stats,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "analysis_results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Each metric has a friendly label, a unit string, and a list of metric_keys
# the engine supports. We compute the engine output for each key and report
# statistics from the first non-empty result.
METRICS = [
    ("FPS", "fps", "frames/s"),
    ("CPU (ms)", "cpu", "ms"),
    ("GPU (ms)", "gpu", "ms"),
    ("Memory (MB)", "memory", "MB"),
    ("Network Ping (ms)", "network_ping", "ms"),
    ("Network RTT (ms)", "network_rtt", "ms"),
    ("Network Upload (bytes/s)", "network_upload", "bytes/s"),
    ("Network Download (bytes/s)", "network_download", "bytes/s"),
    ("PCAP Packets/s", "pcap_packets", "packets/s"),
    ("PCAP Bytes/s", "pcap_bytes", "bytes/s"),
]

# A reasonable minimum number of samples to trust a series. Captures shorter
# than this are still reported, but flagged as "low confidence" in the output.
MIN_SAMPLES = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_stat(values: pd.Series, fn):
    """Run a statistic function on a cleaned pandas Series, returning None
    if there are not enough usable samples."""
    cleaned = pd.to_numeric(values, errors="coerce").dropna()
    cleaned = cleaned[np.isfinite(cleaned)]
    if cleaned.empty:
        return None
    try:
        return float(fn(cleaned))
    except Exception:
        return None


def _series_stats(series: pd.Series):
    """Return a dict of descriptive stats for a numeric series."""
    if series is None:
        return {}
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    cleaned = cleaned[np.isfinite(cleaned)]
    if cleaned.empty:
        return {}

    return {
        "samples": int(cleaned.size),
        "min": float(cleaned.min()),
        "max": float(cleaned.max()),
        "mean": float(cleaned.mean()),
        "median": float(cleaned.median()),
        "p95": float(cleaned.quantile(0.95)),
        "p99": float(cleaned.quantile(0.99)),
        "std": float(cleaned.std(ddof=0)),
    }


def _extract_metrics(stats_df: pd.DataFrame, stat_name: str, subsystem: str):
    """Try to extract each known metric from a single stat file and return
    a dict {metric_key: (dataframe, ycol, series_for_stats)}.

    `network_*` keys are skipped for a non-networked `subsystem` (Base,
    Base-GPU, DOTS, solo Godot): some of those baseline captures still
    carry an RTT/Upload/Download column (a stray network-stats provider
    left wired on the Unity side even though the scene never opens a
    connection), and without this guard that would get reported as real
    network telemetry for a tech that never talks over the network. See
    `data_loader.is_networked_subsystem`. `pcap_*` keys are unaffected --
    those only ever exist for a real capture file, no equivalent leak.
    """
    results = {}
    networked = is_networked_subsystem(subsystem)
    for label, key, unit in METRICS:
        if key.startswith("network_") and not networked:
            continue
        df, ycol = metric_series_from_stats(stats_df, key, stat_name, x_axis_mode="frame")
        if df is None or ycol is None or ycol not in df.columns:
            continue
        series = pd.to_numeric(df[ycol], errors="coerce")
        series = series[np.isfinite(series)]
        if series.empty:
            continue
        results[key] = (df, ycol, series, label, unit)
    return results


# Per-sample observations collected during the folder pass, used later
# for statistical tests between (platform, subsystem) groups.
# Layout: observations[metric_key][(platform, subsystem)] = list[float]
observations: dict = {}


def _per_gameobject_stats(stats_df: pd.DataFrame, events_df: pd.DataFrame,
                           stat_name: str, metric_key: str):
    """Run the existing per-GameObject aggregation and return descriptive
    stats for the resulting series, or None if unavailable."""
    try:
        df, ycol = metric_per_gameobject_series(
            stats_df, events_df, metric_key, stat_name
        )
    except Exception as exc:
        return None, f"per-gameobject failed: {exc}"
    if df is None or ycol is None or ycol not in df.columns:
        return None, "per-gameobject not supported for this metric"
    series = pd.to_numeric(df[ycol], errors="coerce").dropna()
    series = series[np.isfinite(series)]
    if series.empty:
        return None, "per-gameobject produced empty series"
    max_gos = pd.to_numeric(df["GameObjects"], errors="coerce").max()
    return {
        "samples": int(series.size),
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "max_gameobjects": float(max_gos) if pd.notna(max_gos) else None,
    }, None


def _platform_for(name: str) -> str:
    return "PC" if name.startswith("[PC]") else "Quest"


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_folder(folder: Path):
    """Run the full analysis for one benchmark folder."""
    print(f"\n{'='*72}\nFolder: {folder.name}\n{'='*72}")

    pc_folder, quest_folder = folder, None
    if _is_quest_folder(folder):
        pc_folder, quest_folder = None, folder

    stats_files, events_files = [], []
    if pc_folder:
        pc_stats, pc_events, pc_errors = load_csv_files_from_folder(pc_folder)
        stats_files.extend([(f"[PC] {n}", df) for n, df in pc_stats])
        events_files.extend([(f"[PC] {n}", df) for n, df in pc_events])
        for n, e in pc_errors:
            print(f"  [PC read error] {n}: {e}")
    if quest_folder:
        q_stats, q_events, q_errors = load_csv_files_from_folder(quest_folder)
        # The Quest headset never hosts a server, for any tech -- drop the
        # PC-hosted server's own profiler_stats/events CSVs that get
        # dropped into the same benchmark folder for convenience, or they
        # corrupt the per-subsystem averages below (compare_across_folders
        # deliberately blends client_/server_ files of the same subsystem
        # into one row per folder, which only makes sense when both sides
        # are genuinely part of the same platform). See
        # data_loader.is_quest_server_artefact.
        q_stats = [(n, df) for n, df in q_stats if not is_quest_server_artefact(n)]
        q_events = [(n, df) for n, df in q_events if not is_quest_server_artefact(n)]
        stats_files.extend([(f"[Quest] {n}", df) for n, df in q_stats])
        events_files.extend([(f"[Quest] {n}", df) for n, df in q_events])
        for n, e in q_errors:
            print(f"  [Quest read error] {n}: {e}")

    if not stats_files:
        print("  No stat files found, skipping folder.")
        return []

    # Auto-pair stats to events
    user_pairings, _ = auto_pair_files(stats_files, events_files, min_score=50.0)

    # Find the right events df for a given stats df
    def lookup_events(stat_name):
        event_name = user_pairings.get(stat_name)
        if not event_name:
            return None
        for ename, edf in events_files:
            if ename == event_name:
                return edf
        return None

    rows = []
    for sname, sdf in stats_files:
        subsystem = _classify_file(sname)
        platform = _platform_for(sname)
        print(f"\n  --- {sname} ---")
        print(f"      platform={platform} subsystem={subsystem}")

        per_file_metrics = _extract_metrics(sdf, sname, subsystem)
        if not per_file_metrics:
            print("      no metrics parsed")
            continue

        # Identify the best x-axis column (Frame/Time) for printing range
        x_col = "Frame" if "Frame" in sdf.columns else (
            "Time" if "Time" in sdf.columns else (
                "Time Stamp" if "Time Stamp" in sdf.columns else None
            )
        )
        if x_col:
            x_series = pd.to_numeric(sdf[x_col], errors="coerce").dropna()
            if not x_series.empty:
                print(f"      x-axis: {x_col} range {x_series.min():.2f} -> {x_series.max():.2f}")

        edf = lookup_events(sname)
        has_events = edf is not None
        print(f"      events paired: {has_events}")

        for label, key, unit in METRICS:
            if key not in per_file_metrics:
                continue
            _, ycol, series, label_name, unit_name = per_file_metrics[key]
            stats = _series_stats(series)
            if not stats:
                continue
            confidence = "high" if stats["samples"] >= MIN_SAMPLES else "low"
            print(
                f"      [{label_name:24s}] n={stats['samples']:6d}  "
                f"mean={stats['mean']:12.3f}  median={stats['median']:12.3f}  "
                f"p95={stats['p95']:12.3f}  max={stats['max']:12.3f}  ({unit_name}, {confidence})"
            )

            row = {
                "folder": folder.name,
                "platform": platform,
                "subsystem": subsystem,
                "stat_file": sname,
                "metric": label_name,
                "metric_key": key,
                "unit": unit_name,
                "has_events": has_events,
                **stats,
                "confidence": confidence,
            }

            # Accumulate per-sample observations for the statistical tests.
            observations.setdefault(key, {}).setdefault((platform, subsystem), []).extend(
                series.tolist()
            )

            # Try per-GameObject aggregation for compatible metrics
            if has_events and key in {
                "fps", "memory", "cpu", "gpu",
                "network_ping", "network_rtt", "network_rtt_rpc",
                "network_upload", "network_download",
                "pcap_packets", "pcap_bytes",
                "pcap_cumulative_packets", "pcap_cumulative_bytes",
            }:
                pg_stats, err = _per_gameobject_stats(sdf, edf, sname, key)
                if pg_stats:
                    print(
                        f"          ↳ per-GameObject n={pg_stats['samples']:4d}  "
                        f"mean={pg_stats['mean']:12.3f}  median={pg_stats['median']:12.3f}  "
                        f"max={pg_stats['max']:12.3f}  max_gos={pg_stats['max_gameobjects']}"
                    )
                    row["pergo_samples"] = pg_stats["samples"]
                    row["pergo_mean"] = pg_stats["mean"]
                    row["pergo_median"] = pg_stats["median"]
                    row["pergo_max"] = pg_stats["max"]
                    row["pergo_max_gameobjects"] = pg_stats["max_gameobjects"]
                elif err:
                    print(f"          ↳ per-GameObject unavailable: {err}")

            rows.append(row)

    return rows


def compare_across_folders(all_rows):
    """Build a per-metric comparison table aggregated across folders."""
    if not all_rows:
        return
    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_DIR / "raw_per_file_metrics.csv", index=False)
    print(f"\nWrote {OUTPUT_DIR / 'raw_per_file_metrics.csv'}")

    # Collapse to one row per (folder, platform, subsystem, metric) first.
    # A single trial folder can legitimately contribute more than one stat
    # file to the same subsystem tag -- dual-role systems (Photon, FishNet,
    # NGO, NetcodeEntities, Godot Network) ship separate client_/server_
    # stat files that classify_subsystem() folds into one label. Without
    # this collapse, "runs" below would silently double-count a single
    # trial for those subsystems while role-less subsystems (Base, DOTS,
    # Base-GPU, Godot) are counted correctly.
    per_folder_grouping = ["folder", "platform", "subsystem", "metric", "unit"]
    per_folder = (
        df.groupby(per_folder_grouping)
        .agg(
            files_in_folder=("mean", "count"),
            mean=("mean", "mean"),
            median=("median", "median"),
            min=("min", "min"),
            max=("max", "max"),
            p95=("p95", "mean"),
        )
        .reset_index()
    )
    per_folder.to_csv(OUTPUT_DIR / "per_folder_subsystem_metrics.csv", index=False)
    print(f"Wrote {OUTPUT_DIR / 'per_folder_subsystem_metrics.csv'}")

    # Aggregate: mean-of-medians per (platform, subsystem, metric) across
    # trial folders, so we compare typical behavior across repeated runs
    # of the same configuration. "runs" now consistently means "distinct
    # trial folders that contributed this subsystem/metric".
    grouping = ["platform", "subsystem", "metric", "unit"]
    summary = (
        per_folder.groupby(grouping)
        .agg(
            runs=("median", "count"),
            median_of_medians=("median", "median"),
            min_of_min=("min", "min"),
            max_of_max=("max", "max"),
            mean_of_means=("mean", "mean"),
            p95_of_p95=("p95", "median"),
        )
        .reset_index()
        .sort_values(["metric", "platform", "subsystem"])
    )
    summary.to_csv(OUTPUT_DIR / "summary_by_subsystem.csv", index=False)
    print(f"Wrote {OUTPUT_DIR / 'summary_by_subsystem.csv'}")
    return df, summary


def print_insights(df, summary):
    """Print a human-readable insight block derived from the summary."""
    if summary is None or summary.empty:
        return

    print("\n" + "=" * 72)
    print("INSIGHTS")
    print("=" * 72)

    # Highlight: which subsystem has the best/worst median for each metric
    for metric in sorted(summary["metric"].unique()):
        sub = summary[summary["metric"] == metric].copy()
        sub = sub[sub["runs"] > 0]
        if sub.empty:
            continue
        # Lower is better for latency, CPU, GPU, memory, bytes/s, packets/s
        # Higher is better for FPS
        lower_is_better = metric not in {"FPS"}
        sub = sub.sort_values("median_of_medians", ascending=lower_is_better)

        print(f"\nMetric: {metric}")
        for _, row in sub.iterrows():
            direction = "lower" if lower_is_better else "higher"
            print(
                f"  {row['platform']:6s} {row['subsystem']:14s}  "
                f"median={row['median_of_medians']:12.3f} {row['unit']:8s}  "
                f"(runs={int(row['runs'])}, {direction} is better)"
            )


# ---------------------------------------------------------------------------
# Statistical comparisons (Mann-Whitney U + Cliff's delta)
# ---------------------------------------------------------------------------

# Minimum number of samples per group required to run a test. Below this
# threshold the p-value would be meaningless, so we skip the pair.
MIN_SAMPLES_FOR_TEST = 5

# Direction that means "better" for each metric. Used to interpret the
# sign of the effect size in plain English.
LOWER_IS_BETTER = {
    "cpu", "gpu", "memory",
    "network_ping", "network_rtt", "network_rtt_rpc",
    "network_upload", "network_download",
    "pcap_packets", "pcap_bytes",
}
HIGHER_IS_BETTER = {"fps"}

# Pretty metric names keyed by metric_key, for the stat tests report.
METRIC_DISPLAY = {key: label for label, key, _ in METRICS}
METRIC_UNITS = {key: unit for label, key, unit in METRICS}


def _mann_whitney_u(x: list, y: list):
    """Compute the two-sided Mann-Whitney U statistic and a normal-
    approximation p-value without SciPy.

    Implementation: rank both samples together, then
        U_x = R_x - n_x*(n_x+1)/2
        U_y = R_y - n_y*(n_y+1)/2
        U   = min(U_x, U_y)
    The p-value uses the standard normal approximation with tie correction.
    Returns (U, p_value, n_x, n_y).
    """
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return float("nan"), float("nan"), n_x, n_y

    combined = [(v, "x") for v in x] + [(v, "y") for v in y]
    combined.sort(key=lambda t: t[0])

    # Average ranks for ties.
    ranks = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg = (i + j + 2) / 2.0  # 1-indexed average of positions i+1..j+1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1

    r_x = sum(r for r, (_, tag) in zip(ranks, combined) if tag == "x")
    r_y = sum(r for r, (_, tag) in zip(ranks, combined) if tag == "y")

    u_x = r_x - n_x * (n_x + 1) / 2.0
    u_y = r_y - n_y * (n_y + 1) / 2.0
    u = min(u_x, u_y)

    # Normal approximation with tie correction.
    n = n_x + n_y
    mean_u = n_x * n_y / 2.0
    # Ties correction term
    tie_groups: dict[float, int] = {}
    for v, _ in combined:
        tie_groups[v] = tie_groups.get(v, 0) + 1
    tie_sum = sum((t**3 - t) for t in tie_groups.values() if t > 1)
    denom = n_x * n_y
    var_u = (
        denom * (n + 1) / 12.0
        - tie_sum / (12.0 * (n - 1)) if n > 1 else 0.0
    )
    if var_u <= 0:
        return float(u), 1.0, n_x, n_y

    # Continuity correction
    z = (u - mean_u) / (var_u ** 0.5) if u >= mean_u else (u - mean_u) / (var_u ** 0.5)
    # Two-sided p-value via the error function (no SciPy needed).
    import math
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
    return float(u), float(p), n_x, n_y


def _cliffs_delta(x: list, y: list) -> float:
    """Cliff's delta effect size in [-1, 1].

    delta = (# of x>y - # of x<y) / (n_x * n_y)
    Convention: positive delta means X tends to be larger than Y.
    """
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return float("nan")
    greater = less = 0
    for xv in x:
        for yv in y:
            if xv > yv:
                greater += 1
            elif xv < yv:
                less += 1
    return (greater - less) / float(n_x * n_y)


def _effect_label(delta: float) -> str:
    """Romano et al. (2006) thresholds for |delta|."""
    a = abs(delta)
    if a < 0.147:
        return "negligible"
    if a < 0.33:
        return "small"
    if a < 0.474:
        return "medium"
    return "large"


def _verdict(metric_key: str, delta: float, p_value: float) -> str:
    """Translate delta sign + metric direction into a one-line verdict."""
    if p_value >= 0.05:
        return "no significant difference"
    if metric_key in LOWER_IS_BETTER:
        return "A better (lower)" if delta < 0 else "B better (lower)"
    if metric_key in HIGHER_IS_BETTER:
        return "A better (higher)" if delta > 0 else "B better (higher)"
    return "A larger" if delta > 0 else "B larger"


def _build_stat_tests(observations: dict) -> pd.DataFrame:
    """For every (metric, platform, A, B) tuple, run a Mann-Whitney U test
    and Cliff's delta. Returns a flat DataFrame with one row per pair."""
    rows = []
    for metric_key, groups in observations.items():
        if not groups:
            continue
        # Per-platform pairwise comparison.
        for platform in {p for p, _ in groups.keys()}:
            in_platform = {sub: vals for (p, sub), vals in groups.items() if p == platform}
            subsystems = sorted(in_platform.keys())
            for i in range(len(subsystems)):
                for j in range(i + 1, len(subsystems)):
                    a_sub, b_sub = subsystems[i], subsystems[j]
                    a_vals = in_platform[a_sub]
                    b_vals = in_platform[b_sub]
                    if (
                        len(a_vals) < MIN_SAMPLES_FOR_TEST
                        or len(b_vals) < MIN_SAMPLES_FOR_TEST
                    ):
                        continue
                    u, p, nx, ny = _mann_whitney_u(a_vals, b_vals)
                    delta = _cliffs_delta(a_vals, b_vals)
                    rows.append({
                        "metric": METRIC_DISPLAY.get(metric_key, metric_key),
                        "metric_key": metric_key,
                        "platform": platform,
                        "A_subsystem": a_sub,
                        "B_subsystem": b_sub,
                        "n_A": nx,
                        "n_B": ny,
                        "median_A": float(np.median(a_vals)),
                        "median_B": float(np.median(b_vals)),
                        "U": u,
                        "p_value": p,
                        "cliffs_delta": delta,
                        "effect_size": _effect_label(delta),
                        "verdict": _verdict(metric_key, delta, p),
                        "unit": METRIC_UNITS.get(metric_key, ""),
                    })
    df = pd.DataFrame(rows).sort_values(
        ["metric", "platform", "p_value"], na_position="last"
    ).reset_index(drop=True)
    return df


def statistical_comparisons(observations: dict, output_dir: Path):
    """Compute pairwise Mann-Whitney U + Cliff's delta tests and write
    them to disk. Returns the resulting DataFrame."""
    df = _build_stat_tests(observations)
    out_path = output_dir / "statistical_comparisons.csv"
    df.to_csv(out_path, index=False)
    if not df.empty:
        sig = df[df["p_value"] < 0.05]
        out_sig = output_dir / "statistical_comparisons_significant.csv"
        sig.to_csv(out_sig, index=False)
        print(f"\nWrote {out_path}  ({len(df)} pairs, {len(sig)} significant at p<0.05)")
        print(f"Wrote {out_sig}")
    else:
        print(f"\nWrote {out_path}  (no eligible pairs)")
    return df


def print_summary_stat_tests(observations: dict):
    """Print a condensed view: for each metric, the top significant pair
    per platform. Designed for quick decision-making in the console."""
    df = _build_stat_tests(observations)
    if df.empty:
        print("\nNo statistical comparisons (insufficient samples).")
        return
    df_sig = df[df["p_value"] < 0.05]
    print("\n" + "=" * 72)
    print("STATISTICAL COMPARISONS (Mann-Whitney U + Cliff's delta)")
    print("=" * 72)
    if df_sig.empty:
        print("No pairs reached p < 0.05.")
        return

    for metric in sorted(df_sig["metric"].unique()):
        print(f"\nMetric: {metric}")
        rows = df_sig[df_sig["metric"] == metric]
        # Show up to 5 most significant per platform
        for platform in sorted(rows["platform"].unique()):
            sub = rows[rows["platform"] == platform].head(5)
            for _, r in sub.iterrows():
                print(
                    f"  {r['platform']:6s} {r['A_subsystem']:14s} vs {r['B_subsystem']:14s}  "
                    f"med A={r['median_A']:10.3f}  med B={r['median_B']:10.3f} {r['unit']:8s}  "
                    f"p={r['p_value']:.4g}  delta={r['cliffs_delta']:+.3f} ({r['effect_size']})  "
                    f"=> {r['verdict']}"
                )


def _discover_run_folders(data_root: Path) -> list[Path]:
    """Every immediate subfolder of data_root containing at least one CSV
    file directly inside it. Empty placeholder folders (e.g. a
    benchmarkPC#N reserved for a run not captured yet) are silently
    skipped rather than causing an error."""
    if not data_root.exists():
        return []
    return sorted(
        (p for p in data_root.iterdir() if p.is_dir() and any(p.glob("*.csv"))),
        key=lambda p: p.name,
    )


def main():
    if not DATA_ROOT.exists():
        raise SystemExit(f"Data folder not found: {DATA_ROOT}")

    folders = _discover_run_folders(DATA_ROOT)
    if not folders:
        raise SystemExit(f"No run folders with CSV files found under {DATA_ROOT}")
    print(f"Analysing {len(folders)} folder(s): {[f.name for f in folders]}")

    all_rows = []
    for folder in folders:
        all_rows.extend(analyze_folder(folder))

    df, summary = compare_across_folders(all_rows)
    print_insights(df, summary)

    statistical_comparisons(observations, OUTPUT_DIR)
    print_summary_stat_tests(observations)

    print(f"\nDone. Artefacts written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
