"""
load_analysis.py
-----------------
Load-based statistical analysis for the VR network benchmark.

`analyze_data.py` (in this same folder) tests configurations by pooling every
per-frame sample of a run into one bucket and running Mann-Whitney U on that.
Frames within a run are autocorrelated (they're one continuous trajectory,
not independent draws), and a single run mixes loads from 0 to 20000
entities into one median. Both make the resulting p-values and medians
meaningless (pseudo-replication, degenerate p=0.0, incomparable medians).

This module fixes both problems by making the unit of observation ONE RUN
AT ONE LOAD LEVEL ("palier"): each run's frames are first segmented by how
many entities were instantiated at capture time (via the FinishedInstantiation
event trail), each segment is reduced to a single (median, IQR, n_frames)
row, and only then are configurations compared -- with N = number of runs,
not number of frames.

It reuses `streamlit/data_loader.py` (file discovery/pairing/subsystem
classification) and `streamlit/metrics_engine.py` (metric extraction/unit
normalization) rather than re-implementing that logic. `analyze_data.py` is
untouched and keeps working exactly as before.

Key data-driven findings this module relies on (see none of these are
guesses -- each was verified against the real CSVs under data/):

- A run's event log ends with a second ``PhaseFinished`` event (after the
  first StartedInstantiation) exactly when the harness completed the whole
  benchmark normally. Runs that are cut short (client crash/disconnect/
  timeout) simply stop logging after their last FinishedInstantiation, with
  no closing marker -- and the trailing stats-file frames after that point
  show an unrelated performance profile (e.g. FPS jumping from ~25 to
  ~300+ once a disconnected client stops receiving any network load). This
  module therefore only trusts a run's *final* palier segment when that
  closing marker is present; otherwise that palier only feeds the capacity
  metric, never the metric-vs-load curves.
- FishNet logs each wave's FinishedInstantiation event twice (same Value,
  same Frame); these are deduplicated.
- The default reference loads (2000/5000/10000/20000) are not all multiples
  of the harness's 400-entity wave step -- 2000, 10000 and 20000 land
  exactly on a wave boundary, 5000 does not. Reference loads are resolved
  to the nearest reachable wave value, and both the nominal and resolved
  values are reported.
- On Quest, two independent "stats" sources exist per subsystem: the in-app
  Unity/Godot profiler export (Frame-aligned, has RTT, sampled every
  ~0.5s) and the OVR/Android device-activity export (Time Stamp-aligned,
  no RTT, sampled roughly once per second). Per project decision, the
  OVR/Android device file is canonical for every palier it can cover.
  Its sparse sampling means the *terminal* palier of a run often has only
  0-1 raw samples in the couple of seconds between the last wave and end
  of capture -- not enough to clear the transition window, even though
  the run completed normally and genuinely reached that load (verified:
  Base-GPU on Quest reaches 20000 in 5/5 runs per the event log, but the
  OVR file has exactly one sample after the last wave in each). Per
  project decision, when this happens the superseded in-app profiler
  export is used as a fallback for that palier ONLY (never for interior
  paliers, which already have canonical-source data), tagged
  `data_source="profiler_fallback"` in the output so it stays auditable.
  `detect_coverage_gaps` still flags any (platform, load, subsystem) where
  `runs_with_observation < runs_reached_capacity` even after the
  fallback, e.g. when the profiler export is unavailable too.
- Under `--comparisons planned` (the default), every planned pair compares
  a networked tech against its non-networked local baseline. Baselines
  never carry network or PCAP observations (they never open a connection),
  so `network_*`/`pcap_*` metrics structurally have zero comparable planned
  pairs -- not a bug, an unavoidable consequence of comparing against a
  reference that has no network activity. Use `--comparisons all` to also
  test networked techs against each other, which does support those
  metrics.
"""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# The analysis script lives under ccl/, while the shared modules live in the
# top-level streamlit/ folder (same layout as analyze_data.py).
sys.path.append(str(Path(__file__).resolve().parent.parent / "streamlit"))

from data_loader import (  # noqa: E402
    _is_quest_folder,
    auto_pair_files,
    classify_subsystem,
    is_networked_subsystem,
    is_quest_server_artefact,
    load_csv_files_from_folder,
)
from metrics_engine import metric_series_from_stats, _has_pcap_columns  # noqa: E402

from metrics_catalog import METRICS as METRIC_CATALOG
from stats_common import cliffs_delta, cliffs_delta_effect_size
from subsystem_catalog import PLANNED_COMPARISONS


# ---------------------------------------------------------------------------
# Constants (nothing below is meant to be hardcoded elsewhere in this file)
# ---------------------------------------------------------------------------

DATA_ROOT_DEFAULT = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR_DEFAULT = Path(__file__).resolve().parent / "analysis_results" / "load_based"

# Entities added per completed instantiation wave (see FinishedInstantiation
# Value increments in every events CSV under data/).
WAVE_STEP_ENTITIES = 400

DEFAULT_REFERENCE_LOADS = (2000, 5000, 10000, 20000)

# Settle time excluded at the start of every palier segment, so GC/physics
# spikes right after a spawn burst don't leak into the "steady state" sample
# for that load. Time-based (not frame-count) because frame time varies by
# an order of magnitude between low and high load.
DEFAULT_TRANSITION_SECONDS = 2.0

# Minimum number of runs (values) required on each side of a comparison.
MIN_RUNS_FOR_TEST = 2

# The exact Mann-Whitney test enumerates C(n_x+n_y, n_x) arrangements; this
# caps runtime for pathological inputs. C(20, 10) ~= 184k, comfortably under
# this, matches the "N <= 10 per group" design target from the spec.
MAX_EXACT_GROUP_SIZE = 10
MAX_EXACT_ARRANGEMENTS = 200_000

ALPHA_DEFAULT = 0.05

CORRECTION_METHODS = ("holm", "bh", "none")
CORRECTION_DEFAULT = "bh"

COMPARISON_MODES = ("planned", "all")
COMPARISONS_DEFAULT = "planned"

# A run is flagged (not excluded) as a capacity outlier when it reaches
# less than this fraction of the median max-load reached by the OTHER runs
# of the same (platform, subsystem, role).
CAPACITY_OUTLIER_RATIO = 0.5
# Need at least this many runs (the flagged one + others) for "the other
# runs' median" to mean anything.
MIN_RUNS_FOR_OUTLIER_CHECK = 3

# Which configuration pairs are meaningful to test, matching how the
# benchmark is actually designed to be read: each networking solution
# against the local baseline for its own engine/framework, and each
# non-networked baseline against Base (the reference implementation).
# Restricting the family to these pairs (via --comparisons planned) keeps
# correction families small enough that the exact test's floor p-value
# (2/252 at N=5 vs 5) doesn't make every family structurally
# non-significant -- see `compare_configurations`'s docstring.
#
# Sourced from subsystem_catalog.py's `baseline_of` field. Entries are
# unordered (subsystem, reference) pairs; matching against `all_subsystems`
# combinations ignores which one comes first.
_PLANNED_PAIRS = {frozenset(pair) for pair in PLANNED_COMPARISONS}


def is_planned_comparison(subsystem_a: str, subsystem_b: str) -> bool:
    return frozenset((subsystem_a, subsystem_b)) in _PLANNED_PAIRS

# (metric_key, label, unit, lower_is_better), sourced from the shared
# metrics_catalog (short-label convention -- this module's own CSV exports
# use plain labels like "CPU", not "CPU (ms)").
METRICS_DEFAULT = [(m.key, m.short_label, m.unit, m.lower_is_better) for m in METRIC_CATALOG]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WaveEvent:
    """One completed instantiation wave: `entities` were reached at `time`."""
    frame: float
    time: float
    entities: int


@dataclass(frozen=True)
class RunKey:
    platform: str  # "PC" | "Quest"
    subsystem: str  # classify_subsystem() result, e.g. "NGO", "Base"
    role: str  # "client" | "server" | "" (role-less baselines)
    run_id: str  # folder name, e.g. "benchmarkPC#1"
    stat_name: str  # tagged stats file name, for diagnostics


@dataclass
class RunData:
    key: RunKey
    stats_df: pd.DataFrame
    events_df: pd.DataFrame
    data_source: str  # "profiler" | "ovr_device" | "pcap"
    waves: list[WaveEvent]
    run_complete: bool
    # Set only when `data_source == "ovr_device"` and an in-app profiler
    # export was superseded by it for this (subsystem, role). Never used
    # to extend interior paliers (which already have canonical-source
    # data) -- only to recover the terminal palier's observation when the
    # OVR device file's post-completion tail is too sparse to clear the
    # transition window (see `aggregate_run_metric`).
    fallback_stats_df: Optional[pd.DataFrame] = None
    fallback_stat_name: Optional[str] = None


@dataclass
class LoadIssue:
    run_id: str
    stat_name: str
    reason: str


@dataclass(frozen=True)
class SegmentWindow:
    entities: int
    time_start: float
    time_end: float
    bounded: bool  # True when closed by the following wave, not by run end


@dataclass(frozen=True)
class ObservationRow:
    platform: str
    subsystem: str
    role: str
    run_id: str
    data_source: str
    metric_key: str
    metric_label: str
    unit: str
    entities: int
    n_frames: int
    median: float
    q1: float
    q3: float
    iqr: float


@dataclass(frozen=True)
class CapacityRow:
    platform: str
    subsystem: str
    role: str
    run_id: str
    max_entities_reached: int
    run_complete: bool


@dataclass(frozen=True)
class MannWhitneyResult:
    u: float
    p_value: float
    n_x: int
    n_y: int
    n_arrangements: int
    p_floor: float


@dataclass(frozen=True)
class ComparisonRow:
    metric_key: str
    metric_label: str
    unit: str
    lower_is_better: bool
    platform: str
    target_load: int
    resolved_load: int
    subsystem_a: str
    subsystem_b: str
    n_a: int
    n_b: int
    median_a: float
    median_b: float
    median_ratio: float
    u_statistic: float
    p_value: float
    n_arrangements: int
    cliffs_delta: float
    effect_size: str
    comparable: bool
    reason: str
    planned: bool


# ---------------------------------------------------------------------------
# Statistics (no SciPy)
# ---------------------------------------------------------------------------

def _rank_average(values: list[float]) -> list[float]:
    """1-indexed ranks with mid-rank averaging for ties."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def mannwhitney_exact(x: list[float], y: list[float]) -> MannWhitneyResult:
    """Exact two-sided Mann-Whitney U test by full enumeration of arrangements.

    Ties are handled with mid-ranks; the null distribution of U is built by
    permuting the combined *observed values* across all C(n, n_x) equally
    likely group-A/group-B splits (not by resampling ranks), so a tied
    observation contributes consistently to every arrangement containing it.

    U = min(U_x, U_y) is symmetric, so counting arrangements with
    U <= observed_U captures both tails in one pass. The observed
    arrangement always satisfies U <= observed_U, so p_value is always
    >= 1/n_arrangements -- never exactly 0.

    Raises ValueError if either group is empty or the arrangement count
    exceeds MAX_EXACT_ARRANGEMENTS (not intended for large samples).
    """
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        raise ValueError("both groups must be non-empty")

    n = n_x + n_y
    n_arrangements = math.comb(n, n_x)
    if n_arrangements > MAX_EXACT_ARRANGEMENTS:
        raise ValueError(
            f"n_x={n_x}, n_y={n_y} -> {n_arrangements} arrangements exceeds "
            f"the exact-enumeration cap ({MAX_EXACT_ARRANGEMENTS}); this test "
            "is meant for small per-run sample sizes (N <= 10 per group)."
        )

    combined = list(x) + list(y)
    ranks = _rank_average(combined)
    max_u = float(n_x * n_y)

    observed_rank_sum_x = sum(ranks[:n_x])
    observed_u_x = observed_rank_sum_x - n_x * (n_x + 1) / 2.0
    observed_u = min(observed_u_x, max_u - observed_u_x)

    tolerance = 1e-9
    count_extreme = 0
    for combo in itertools.combinations(range(n), n_x):
        rank_sum_x = sum(ranks[i] for i in combo)
        u_x = rank_sum_x - n_x * (n_x + 1) / 2.0
        u = min(u_x, max_u - u_x)
        if u <= observed_u + tolerance:
            count_extreme += 1

    p_value = count_extreme / n_arrangements
    return MannWhitneyResult(
        u=observed_u, p_value=p_value, n_x=n_x, n_y=n_y,
        n_arrangements=n_arrangements, p_floor=1.0 / n_arrangements,
    )


def holm_correction(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni step-down adjustment, order-preserving.

    adjusted_p(k) = max_{j<=k} min((m - j + 1) * p_(j), 1), where p_(j) is
    the j-th smallest raw p-value (1-indexed) -- the standard step-down
    definition, guaranteeing the adjusted p-values are monotone non-
    decreasing when read in sorted order.
    """
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, idx in enumerate(order):
        candidate = min((m - rank) * p_values[idx], 1.0)
        running_max = max(running_max, candidate)
        adjusted[idx] = running_max
    return adjusted


def benjamini_hochberg_correction(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg step-up FDR control, order-preserving.

    adjusted_p(k) = min_{j>=k} min(p_(j) * m / j, 1), where p_(j) is the
    j-th smallest raw p-value (1-indexed) -- the standard step-up
    definition (cumulative minimum from the largest rank down to the
    smallest), guaranteeing the adjusted p-values are monotone non-
    decreasing when read in sorted order.

    Why this is the default correction in `compare_configurations`
    -------------------------------------------------------------
    The exact Mann-Whitney test has a hard floor: at N=5 vs 5 (the typical
    run count per configuration here), the smallest attainable two-sided
    p-value is 2/252 ~= 0.0079, however extreme the separation between
    groups. Holm's step-down procedure multiplies the smallest p-value in
    a family by the family size m; once m exceeds
    ceil(alpha / p_floor) = ceil(0.05 / 0.0079) ~= 7, Holm's floor-
    adjusted p-value exceeds alpha and *no* comparison in that family can
    ever be declared significant, regardless of effect size. Several
    (metric, platform, load) families in this dataset reach 7-8
    comparisons even after restricting to `--comparisons planned`, which
    would make Holm structurally blind there. Benjamini-Hochberg's
    divisor is p_(k) * m / k -- rank-dependent, not fixed at m -- so a
    family where every test sits exactly at the floor still resolves to
    the floor for all of them (see the tied-floor test in
    test_load_analysis.py) rather than being inflated past alpha. BH
    controls the expected proportion of false discoveries rather than the
    family-wise error rate, which is the appropriate trade-off when many
    tests are expected to be non-null: 411 of 465 comparable pairs in this
    dataset show complete separation (|Cliff's delta| = 1). Holm remains
    available via `--correction holm` for readers who need the stricter
    FWER guarantee and are willing to accept its floor-driven blind spot.
    """
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_min = 1.0
    for rank in range(m - 1, -1, -1):
        idx = order[rank]
        candidate = min(p_values[idx] * m / (rank + 1), 1.0)
        running_min = min(running_min, candidate)
        adjusted[idx] = running_min
    return adjusted


# ---------------------------------------------------------------------------
# Loading & pairing
# ---------------------------------------------------------------------------

def _is_ovr_device_stats(df: pd.DataFrame) -> bool:
    """OVR/Android device-activity exports have no engine Frame column at
    all (only Time Stamp), unlike every in-app profiler export."""
    return "Frame" not in df.columns and "Time Stamp" in df.columns


def _stats_kind(df: pd.DataFrame) -> str:
    """Classify a stats file as one of three non-overlapping metric sets.

    A single run can legitimately produce BOTH a profiler-style export
    (fps/cpu/gpu/memory/rtt) AND a PCAP-derived capture export
    (pcap_packets/pcap_bytes) for the same (subsystem, role) -- these are
    complementary, not duplicates, and must both be kept. Only within the
    same kind can two candidates be genuine duplicates (see
    `_select_stats_sources`).
    """
    if _has_pcap_columns(df):
        return "pcap"
    if _is_ovr_device_stats(df):
        return "ovr_device"
    return "profiler"


def _role_for(tagged_name: str, platform: str, subsystem: str) -> str:
    lower = tagged_name.lower()
    if "client" in lower:
        return "client"
    if "server" in lower:
        return "server"
    # Quest never hosts a server for any tech; its device-activity files
    # carry no client/server token at all but are always the client side.
    if platform == "Quest" and is_networked_subsystem(subsystem):
        return "client"
    return ""


def _select_stats_sources(
    candidates: list[tuple[str, pd.DataFrame]], platform: str
) -> tuple[list[tuple[str, pd.DataFrame, str]], list[tuple[str, str]], Optional[tuple[str, pd.DataFrame]]]:
    """Resolve every stats-file candidate for one (subsystem, role) into
    the set of sources actually used.

    PCAP-derived candidates are always kept (they feed metrics no other
    source has). Among the remaining "device metrics" candidates, the
    OVR/Android device file wins over the in-app profiler export when both
    exist for the same (subsystem, role) -- per-project decision, the
    profiler export is only used when no device file is available.
    Genuine same-kind duplicates (e.g. two pcap captures) keep the first
    and drop the rest.

    Returns (selected, dropped, fallback):
    - `dropped` is a list of (file_name, reason) pairs; every reason names
      the specific file that was kept instead, so the choice is auditable
      from issues.csv alone.
    - `fallback` is the in-app profiler candidate superseded by an OVR
      device file on Quest, if any -- it is NOT used as a full source (the
      OVR file stays canonical for every palier it can cover), only kept
      so `discover_runs` can attach it to the run for terminal-palier
      recovery (see `RunData.fallback_stats_df`).
    """
    by_kind: dict[str, list[tuple[str, pd.DataFrame]]] = {}
    for name, df in candidates:
        by_kind.setdefault(_stats_kind(df), []).append((name, df))

    selected: list[tuple[str, pd.DataFrame, str]] = []
    dropped: list[tuple[str, str]] = []
    fallback: Optional[tuple[str, pd.DataFrame]] = None

    def _keep_first(cands: list[tuple[str, pd.DataFrame]], kind: str) -> str:
        kept_name, kept_df = cands[0]
        selected.append((kept_name, kept_df, kind))
        for name, _ in cands[1:]:
            dropped.append((name, f"duplicate {kind} source for this (subsystem, role); kept '{kept_name}'"))
        return kept_name

    pcap_candidates = by_kind.get("pcap", [])
    if pcap_candidates:
        _keep_first(pcap_candidates, "pcap")

    device_candidates = by_kind.get("ovr_device", [])
    profiler_candidates = by_kind.get("profiler", [])

    if platform == "Quest" and device_candidates:
        kept_name = _keep_first(device_candidates, "ovr_device")
        if profiler_candidates:
            fallback = profiler_candidates[0]
        for name, _ in profiler_candidates:
            dropped.append((
                name,
                f"in-app profiler export not used as primary: OVR/Android device metrics "
                f"'{kept_name}' are canonical for Quest; kept in reserve as a terminal-palier "
                f"fallback (data_source=profiler_fallback) when OVR leaves the final wave's "
                f"segment empty",
            ))
    elif profiler_candidates:
        kept_name = _keep_first(profiler_candidates, "profiler")
        for name, _ in device_candidates:
            dropped.append((
                name,
                f"OVR/Android device export not used: in-app profiler '{kept_name}' was selected",
            ))
    elif device_candidates:
        # PC has no OVR device files in practice, but if one ever shows up
        # without a profiler counterpart, still use it rather than drop it.
        _keep_first(device_candidates, "ovr_device")

    return selected, dropped, fallback


def _extract_waves(events_df: pd.DataFrame) -> tuple[list[WaveEvent], bool]:
    """Return (waves, run_complete) from an events DataFrame.

    `run_complete` is True iff a `PhaseFinished` event exists at or after
    the last `FinishedInstantiation` -- see module docstring for why this
    is the reliable signal for "the benchmark elapsed normally" vs. "the
    client crashed/disconnected/timed out mid-wave".
    """
    if "Event" not in events_df.columns or "Value" not in events_df.columns:
        return [], False

    events = events_df.copy()
    events["Frame"] = pd.to_numeric(events.get("Frame"), errors="coerce")
    events["Time"] = pd.to_numeric(events.get("Time"), errors="coerce")

    finished = events.loc[
        events["Event"] == "FinishedInstantiation", ["Frame", "Time", "Value"]
    ].copy()
    finished["Value"] = pd.to_numeric(finished["Value"], errors="coerce")
    finished = finished.dropna(subset=["Value", "Frame", "Time"])
    # FishNet logs each wave's completion twice (same Value); keep one.
    finished = finished.sort_values(["Value", "Frame"]).drop_duplicates(
        subset=["Value"], keep="first"
    )
    finished = finished.sort_values("Frame").reset_index(drop=True)

    if finished.empty:
        return [], False

    waves = [
        WaveEvent(frame=float(row.Frame), time=float(row.Time), entities=int(row.Value))
        for row in finished.itertuples()
    ]

    last_frame = waves[-1].frame
    closing = events.loc[
        (events["Event"] == "PhaseFinished") & (events["Frame"] >= last_frame)
    ]
    run_complete = not closing.empty
    return waves, run_complete


def discover_runs(data_root: Path) -> tuple[list[RunData], list[LoadIssue]]:
    """Pair every stats file with its events file across all run folders.

    Every stats file that can't be paired with an events file, whose event
    log yields no usable waves, or that is a superseded duplicate stats
    source, is reported in the returned issue list rather than silently
    dropped.
    """
    if not data_root.exists():
        raise SystemExit(f"Data folder not found: {data_root}")

    runs: list[RunData] = []
    issues: list[LoadIssue] = []

    folders = sorted(
        (p for p in data_root.iterdir() if p.is_dir() and any(p.glob("*.csv"))),
        key=lambda p: p.name,
    )
    for folder in folders:
        platform = "Quest" if _is_quest_folder(folder) else "PC"
        stats_files, events_files, read_errors = load_csv_files_from_folder(folder)
        for name, err in read_errors:
            issues.append(LoadIssue(folder.name, name, f"read error: {err}"))

        if platform == "Quest":
            stats_files = [(n, df) for n, df in stats_files if not is_quest_server_artefact(n)]
            events_files = [(n, df) for n, df in events_files if not is_quest_server_artefact(n)]

        tagged_stats = [(f"[{platform}] {n}", df) for n, df in stats_files]
        tagged_events = [(f"[{platform}] {n}", df) for n, df in events_files]
        events_by_name = dict(tagged_events)

        pairings, _ = auto_pair_files(tagged_stats, tagged_events, min_score=50.0)

        grouped: dict[tuple[str, str], list[tuple[str, pd.DataFrame]]] = {}
        for name, df in tagged_stats:
            subsystem = classify_subsystem(name)
            role = _role_for(name, platform, subsystem)
            grouped.setdefault((subsystem, role), []).append((name, df))

        for (subsystem, role), candidates in grouped.items():
            selected, dropped, fallback = _select_stats_sources(candidates, platform)
            for name, reason in dropped:
                issues.append(LoadIssue(folder.name, name, reason))

            for chosen_name, chosen_df, data_source in selected:
                event_name = pairings.get(chosen_name)
                if event_name is None:
                    issues.append(LoadIssue(folder.name, chosen_name, "no events file could be paired"))
                    continue
                events_df = events_by_name.get(event_name)
                if events_df is None:
                    issues.append(LoadIssue(
                        folder.name, chosen_name, f"paired events file '{event_name}' not found"
                    ))
                    continue

                waves, run_complete = _extract_waves(events_df)
                if not waves:
                    issues.append(LoadIssue(
                        folder.name, chosen_name, "events file has no FinishedInstantiation rows"
                    ))
                    continue

                fallback_stat_name, fallback_stats_df = (None, None)
                if data_source == "ovr_device" and fallback is not None:
                    fallback_stat_name, fallback_stats_df = fallback

                key = RunKey(platform, subsystem, role, folder.name, chosen_name)
                runs.append(RunData(
                    key, chosen_df, events_df, data_source, waves, run_complete,
                    fallback_stats_df=fallback_stats_df, fallback_stat_name=fallback_stat_name,
                ))

    return runs, issues


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def build_segments(
    waves: list[WaveEvent], run_complete: bool, capture_end_time: float,
    transition_seconds: float,
) -> list[SegmentWindow]:
    """Turn a sorted wave list into steady-state time windows per palier.

    Each interior palier (reached by wave i, superseded by wave i+1)
    contributes a segment from `transition_seconds` after it was reached to
    the moment the next wave starts. The final palier is only included when
    `run_complete` -- otherwise there is no closing signal for it and its
    trailing frames may reflect a crash/disconnect artifact rather than
    genuine steady-state performance (see module docstring).
    """
    if not waves:
        return []
    segments = []
    for i, wave in enumerate(waves):
        start = wave.time + transition_seconds
        if i + 1 < len(waves):
            end = waves[i + 1].time
            bounded = True
        else:
            if not run_complete:
                continue
            end = capture_end_time
            bounded = False
        if end <= start:
            continue
        segments.append(SegmentWindow(wave.entities, start, end, bounded))
    return segments


def _time_axis_priority_column(df: pd.DataFrame) -> Optional[str]:
    """Mirror metrics_engine's x-axis column priority for x_axis_mode="time"."""
    for column in ("Time (s)", "Time", "Time Stamp", "Frame"):
        if column in df.columns:
            return column
    return None


def _seconds_divisor(column_name: str) -> float:
    # "Time Stamp" (Quest OVR/Android exports) is in milliseconds; every
    # other candidate column is already in seconds.
    return 1000.0 if column_name == "Time Stamp" else 1.0


def _terminal_fallback_row(
    run: RunData, metric_key: str, metric_label: str, unit: str,
    transition_seconds: float, top_wave: WaveEvent,
) -> Optional[ObservationRow]:
    """Try to recover the terminal palier's observation from
    `run.fallback_stats_df` (the in-app profiler export superseded by an
    OVR device file on Quest) when the canonical source left it empty.

    Only the terminal palier is ever filled this way. Interior paliers
    already have canonical-source data whenever the run reached them, and
    blending sources there would undermine the "OVR is canonical, never
    mixed" policy for Quest -- this fallback exists specifically because
    that policy has no answer for "the canonical source's post-completion
    tail is too sparse to sample," not as a general excuse to mix.

    The window matches the run's normal segmentation for that palier
    (`top_wave.time + transition_seconds` onward), evaluated against the
    fallback source's OWN valid-sample range, which is what makes this
    useful: it's the same profiler-style export used on PC, sampled far
    more densely than the OVR device file. The resulting row is tagged
    `data_source="profiler_fallback"` so it stays distinguishable and
    filterable from genuine OVR-device observations.
    """
    if run.fallback_stats_df is None or run.fallback_stat_name is None:
        return None
    time_col = _time_axis_priority_column(run.fallback_stats_df)
    if time_col is None:
        return None
    divisor = _seconds_divisor(time_col)

    series_df, ycol = metric_series_from_stats(
        run.fallback_stats_df, metric_key, run.fallback_stat_name, x_axis_mode="time"
    )
    if series_df is None or ycol is None or "Time" not in series_df.columns:
        return None

    times = pd.to_numeric(series_df["Time"], errors="coerce") / divisor
    values = pd.to_numeric(series_df[ycol], errors="coerce")
    valid = pd.DataFrame({"time": times, "value": values}).dropna()
    if valid.empty:
        return None

    start = top_wave.time + transition_seconds
    end = float(valid["time"].max())
    if end <= start:
        return None

    window = valid.loc[(valid["time"] >= start) & (valid["time"] < end), "value"]
    if window.empty:
        return None

    q1 = float(window.quantile(0.25))
    q3 = float(window.quantile(0.75))
    return ObservationRow(
        platform=run.key.platform, subsystem=run.key.subsystem, role=run.key.role,
        run_id=run.key.run_id, data_source="profiler_fallback",
        metric_key=metric_key, metric_label=metric_label, unit=unit,
        entities=top_wave.entities, n_frames=int(window.size),
        median=float(window.median()), q1=q1, q3=q3, iqr=q3 - q1,
    )


def aggregate_run_metric(
    run: RunData, metric_key: str, metric_label: str, unit: str,
    transition_seconds: float,
) -> tuple[list[ObservationRow], list[str]]:
    """Segment one run's stats file into palier windows and reduce each to
    (median, IQR, n_frames) for `metric_key`.

    Returns (rows, notes). `notes` are diagnostic strings for issues.csv
    and do NOT imply `rows` is empty -- a run can produce usable data for
    every palier except its highest one. In particular: a run whose event
    log shows it reached a palier normally (`run_complete=True`) can still
    end up with zero samples for that *final* palier if the capture stops
    only a second or two after the last wave -- common on Quest, where the
    canonical OVR/Android device file samples roughly once per second, so
    a short tail can fall entirely within the transition-exclusion window
    or simply miss every sample. That is a real data-sparsity limit, not a
    bug to paper over by shrinking the transition window -- but it must
    not be reported as "never reached", which is what a bare "no data"
    would imply. Callers (`build_observations`, `compare_configurations`)
    use this to distinguish the two.
    """
    notes: list[str] = []
    time_col = _time_axis_priority_column(run.stats_df)
    if time_col is None:
        return [], ["no usable time axis in stats file"]
    divisor = _seconds_divisor(time_col)

    series_df, ycol = metric_series_from_stats(
        run.stats_df, metric_key, run.key.stat_name, x_axis_mode="time"
    )
    if series_df is None or ycol is None or "Time" not in series_df.columns:
        return [], ["metric not present in this stats file"]

    times = pd.to_numeric(series_df["Time"], errors="coerce") / divisor
    values = pd.to_numeric(series_df[ycol], errors="coerce")
    valid = pd.DataFrame({"time": times, "value": values}).dropna()
    if valid.empty:
        return [], ["metric series empty after cleaning"]

    capture_end = float(valid["time"].max())
    segments = build_segments(run.waves, run.run_complete, capture_end, transition_seconds)

    rows: list[ObservationRow] = []
    for seg in segments:
        mask = (valid["time"] >= seg.time_start) & (valid["time"] < seg.time_end)
        window = valid.loc[mask, "value"]
        if window.empty:
            continue
        q1 = float(window.quantile(0.25))
        q3 = float(window.quantile(0.75))
        rows.append(ObservationRow(
            platform=run.key.platform, subsystem=run.key.subsystem, role=run.key.role,
            run_id=run.key.run_id, data_source=run.data_source,
            metric_key=metric_key, metric_label=metric_label, unit=unit,
            entities=seg.entities, n_frames=int(window.size),
            median=float(window.median()), q1=q1, q3=q3, iqr=q3 - q1,
        ))

    # The highest wave this run's event log reached is the one most likely
    # to be silently swallowed by a short (or negative -- see below)
    # post-completion tail; flag it by name when that happens on an
    # otherwise-normal run, distinct from the generic "nothing survived"
    # case below.
    if run.waves and run.run_complete:
        top_wave = run.waves[-1]
        produced_entities = {row.entities for row in rows}
        if top_wave.entities not in produced_entities:
            fallback_row = _terminal_fallback_row(
                run, metric_key, metric_label, unit, transition_seconds, top_wave
            )
            if fallback_row is not None:
                rows.append(fallback_row)
                notes.append(
                    f"palier {top_wave.entities}: canonical source ({run.data_source}) left no "
                    f"steady-state sample here; recovered {fallback_row.n_frames} sample(s) from "
                    f"the in-app profiler fallback (data_source=profiler_fallback)"
                )
            else:
                tail_seconds = capture_end - top_wave.time
                if tail_seconds < 0:
                    # This metric's own valid samples end BEFORE the wave was
                    # even reached -- not a near-miss on the transition
                    # window, but this source's own time range not covering
                    # the full run (e.g. a PCAP capture that was time-boxed
                    # independently of the profiler/event timeline).
                    notes.append(
                        f"palier {top_wave.entities} was reached (run completed normally) at "
                        f"t={top_wave.time:.2f}s, but this metric's own valid samples end at "
                        f"t={capture_end:.2f}s ({-tail_seconds:.2f}s earlier) -- this source's "
                        f"capture window doesn't cover the full run; no steady-state "
                        f"observation for this palier in this run/metric"
                    )
                else:
                    notes.append(
                        f"palier {top_wave.entities} was reached (run completed normally) but "
                        f"only {tail_seconds:.2f}s of capture remained after it, too little to "
                        f"clear the {transition_seconds:.2f}s transition window with a sample -- "
                        f"no steady-state observation for this palier in this run/metric"
                    )

    if not segments:
        notes.append("no usable palier segments (prep-only run or unclosed final wave)")
    elif not rows:
        notes.append("no frames landed inside any palier segment")
    return rows, notes


def build_observations(
    runs: list[RunData], metrics: list[tuple[str, str, str]], transition_seconds: float,
) -> tuple[pd.DataFrame, list[LoadIssue]]:
    """Long-format table: one row per (run, metric, palier)."""
    all_rows: list[ObservationRow] = []
    issues: list[LoadIssue] = []
    for run in runs:
        for key, label, unit in metrics:
            if key.startswith("network_") and not is_networked_subsystem(run.key.subsystem):
                continue
            rows, notes = aggregate_run_metric(run, key, label, unit, transition_seconds)
            for note in notes:
                issues.append(LoadIssue(run.key.run_id, run.key.stat_name, f"{label}: {note}"))
            all_rows.extend(rows)
    columns = list(ObservationRow.__annotations__.keys())
    if not all_rows:
        return pd.DataFrame(columns=columns), issues
    return pd.DataFrame([asdict(r) for r in all_rows], columns=columns), issues


# ---------------------------------------------------------------------------
# Capacity
# ---------------------------------------------------------------------------

def compute_capacity(runs: list[RunData]) -> pd.DataFrame:
    """One row per (platform, subsystem, role, run): the max entity count
    that run's event log reached, and whether it did so before a normal
    (non-crash) end of benchmark.

    A run can produce more than one `RunData` (e.g. a profiler export and
    a PCAP capture sharing the same events file); capacity is a property
    of the events log, not of which stats file we're looking at, so
    duplicates are collapsed to one row per (platform, subsystem, role,
    run_id).
    """
    columns = list(CapacityRow.__annotations__.keys())
    seen: dict[tuple[str, str, str, str], CapacityRow] = {}
    for run in runs:
        if not run.waves:
            continue
        dedup_key = (run.key.platform, run.key.subsystem, run.key.role, run.key.run_id)
        seen.setdefault(dedup_key, CapacityRow(
            run.key.platform, run.key.subsystem, run.key.role, run.key.run_id,
            max(w.entities for w in run.waves), run.run_complete,
        ))
    if not seen:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([asdict(r) for r in seen.values()], columns=columns)


def detect_capacity_outliers(capacity_df: pd.DataFrame) -> list[LoadIssue]:
    """Flag (never exclude) runs whose capacity looks anomalous next to
    the other runs of the same (platform, subsystem, role): reaching less
    than CAPACITY_OUTLIER_RATIO times the median of the OTHER runs' max
    entities reached.

    This is purely a visibility aid for `issues.csv` -- whether an
    outlier run should be excluded from the analysis is a judgment call
    for whoever reads the report, not something this function decides.
    """
    issues: list[LoadIssue] = []
    if capacity_df.empty:
        return issues

    for (platform, subsystem, role), group in capacity_df.groupby(["platform", "subsystem", "role"]):
        if len(group) < MIN_RUNS_FOR_OUTLIER_CHECK:
            continue
        for _, row in group.iterrows():
            others = group.loc[group["run_id"] != row["run_id"], "max_entities_reached"]
            if others.empty:
                continue
            reference_median = others.median()
            if reference_median <= 0:
                continue
            if row["max_entities_reached"] < CAPACITY_OUTLIER_RATIO * reference_median:
                issues.append(LoadIssue(
                    run_id=row["run_id"],
                    stat_name=f"{platform}/{subsystem}/{role or 'role-less'}",
                    reason=(
                        f"capacity outlier: this run reached {int(row['max_entities_reached'])} "
                        f"entities, under {CAPACITY_OUTLIER_RATIO:.0%} of the other "
                        f"{len(others)} run(s)' median ({reference_median:.0f}) for this "
                        f"configuration -- not excluded automatically, review manually"
                    ),
                ))
    return issues


def capacity_headline(capacity_df: pd.DataFrame) -> pd.DataFrame:
    """One row per (platform, subsystem, run): the client role's capacity
    when both client and server rows exist for that run (the server almost
    always reaches the max load even when the client can't keep up, so it
    would misrepresent the configuration's real ceiling); otherwise
    whichever single role is present (role-less baselines)."""
    if capacity_df.empty:
        return capacity_df.copy()

    def _pick(group: pd.DataFrame) -> pd.Series:
        client_rows = group.loc[group["role"] == "client"]
        return client_rows.iloc[0] if not client_rows.empty else group.iloc[0]

    picked = [
        _pick(group)
        for _, group in capacity_df.groupby(["platform", "subsystem", "run_id"], sort=True)
    ]
    return pd.DataFrame(picked).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Reference loads & pairwise comparisons
# ---------------------------------------------------------------------------

def resolve_reference_loads(
    target_loads: list[int], step: int = WAVE_STEP_ENTITIES
) -> dict[int, int]:
    """Map each nominal target load to the nearest value actually reachable
    in `step`-sized waves. 5000 is not a multiple of the harness's 400-
    entity wave step, so an exact match is impossible for that default;
    both the nominal and resolved values are reported downstream."""
    return {t: int(round(t / step) * step) for t in target_loads}


def load_coverage_table(
    observations: pd.DataFrame, capacity_df: pd.DataFrame, target_loads: list[int],
) -> pd.DataFrame:
    """For each (platform, target_load, subsystem): how many runs reached
    that load per the capacity/event log (`runs_reached_capacity`), how
    many of those actually produced a usable steady-state observation
    (`runs_with_observation`), out of how many runs exist at all
    (`runs_total`) for that configuration.

    `runs_reached_capacity` can be strictly greater than
    `runs_with_observation`: a run can complete normally and reach 20000
    entities, yet the capture may end only a second or two later -- too
    short for the transition-window exclusion to leave a sample (see
    `aggregate_run_metric`). Collapsing that gap into a single reached/
    not-reached boolean would make a fully-successful configuration look
    identical to one that genuinely never got there. This table is meant
    to let reference loads (and the transition window) be picked from
    evidence rather than assumption -- both numbers are reported so the
    two situations stay distinguishable.
    """
    columns = [
        "platform", "target_load", "resolved_load", "subsystem",
        "runs_total", "runs_reached_capacity", "runs_with_observation",
    ]
    if capacity_df.empty:
        return pd.DataFrame(columns=columns)

    resolved = resolve_reference_loads(target_loads)
    non_server_capacity = capacity_df[capacity_df["role"] != "server"]
    non_server_obs = (
        observations[observations["role"] != "server"] if not observations.empty else observations
    )

    rows = []
    for (platform, subsystem), group in non_server_capacity.groupby(["platform", "subsystem"]):
        runs_total = group["run_id"].nunique()
        for target, resolved_load in resolved.items():
            runs_reached_capacity = group.loc[
                group["max_entities_reached"] >= resolved_load, "run_id"
            ].nunique()

            runs_with_observation = 0
            if not non_server_obs.empty:
                obs_slice = non_server_obs[
                    (non_server_obs["platform"] == platform)
                    & (non_server_obs["subsystem"] == subsystem)
                    & (non_server_obs["entities"] == resolved_load)
                ]
                runs_with_observation = obs_slice["run_id"].nunique()

            rows.append({
                "platform": platform, "target_load": target, "resolved_load": resolved_load,
                "subsystem": subsystem, "runs_total": runs_total,
                "runs_reached_capacity": runs_reached_capacity,
                "runs_with_observation": runs_with_observation,
            })
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["platform", "target_load", "subsystem"])
        .reset_index(drop=True)
    )


def detect_coverage_gaps(coverage_df: pd.DataFrame) -> list[LoadIssue]:
    """Flag every (platform, target_load, subsystem) row of
    `load_coverage_table` where `runs_with_observation < runs_reached_capacity`
    -- a standing gap between what the event log says was reached and what
    the segmented data can actually back up.

    This is a permanent structural check, not a one-off: it will keep
    catching the Base-GPU/DOTS-on-Quest class of gap (a run completes
    normally but its final palier's capture tail is too short/sparse to
    clear the transition window) for any future data drop, without
    anyone having to eyeball load_coverage.csv by hand. Written to
    issues.csv so it survives an issues-only read.
    """
    issues: list[LoadIssue] = []
    if coverage_df.empty:
        return issues
    gaps = coverage_df[coverage_df["runs_with_observation"] < coverage_df["runs_reached_capacity"]]
    for _, row in gaps.iterrows():
        issues.append(LoadIssue(
            run_id=f"{row['platform']}/{row['subsystem']}",
            stat_name=f"target_load={row['target_load']}",
            reason=(
                f"coverage gap: {int(row['runs_with_observation'])}/{int(row['runs_reached_capacity'])} "
                f"run(s) that reached this load (of {int(row['runs_total'])} total) produced a usable "
                f"steady-state observation -- see load_coverage.csv"
            ),
        ))
    return issues


def compare_configurations(
    observations: pd.DataFrame, target_loads: list[int], lower_is_better: set[str],
    alpha: float = ALPHA_DEFAULT, comparisons: str = COMPARISONS_DEFAULT,
    correction: str = CORRECTION_DEFAULT, capacity_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Pairwise Mann-Whitney + Cliff's delta between configurations, at
    each resolved reference load, within each (metric, platform) family.

    A run contributes at most one value per (config, load): the median of
    its palier-level medians nearest that load (there's normally exactly
    one, since a run reaches each `entities` value once). Server-role rows
    are excluded from cross-configuration comparisons -- the server rarely
    fails, so its numbers describe "how hard the server worked", not the
    steady-state experience the comparison is meant to capture; client
    (or role-less baseline) rows are used instead.

    A pair is `comparable=False` (with a `reason`) whenever either side
    never reached the resolved load, has too few runs, or the exact test's
    arrangement count would be impractical -- never silently dropped. When
    `capacity_df` is given, a side with zero observations is checked
    against it: if the event log shows the load *was* reached in one or
    more runs, the reason says so explicitly (pointing to issues.csv)
    instead of the misleading "never reached" -- see
    `aggregate_run_metric` for why a fully successful run can still leave
    its highest palier with no usable observation.

    EVERY subsystem pair is always computed and exported, regardless of
    `comparisons`. `comparisons` only controls which pairs feed the
    correction families:

    - "planned" (default): only pairs in `PLANNED_COMPARISONS` (each
      networking solution vs. its local baseline, each non-networked
      baseline vs. Base) form correction families. This keeps family size
      small -- up to 8 in this dataset -- so the exact test's floor
      p-value doesn't make whole families structurally non-significant
      (see `benjamini_hochberg_correction`'s docstring). Every pair not in
      that set is still computed and appears in the output with
      `planned=False`, but its `p_value_holm`/`p_value_bh`/`significant`
      are left unset (NaN/False) -- it was never a member of any tested
      family.
    - "all": every comparable pair for a (metric, platform, target_load)
      forms one family, `planned` is informational only.

    `correction` selects which adjusted column drives `significant`
    ("holm", "bh", or "none" for raw p < alpha); both `p_value_holm` and
    `p_value_bh` are always computed for family members either way, so a
    reader can compare the two without re-running the analysis.
    """
    if comparisons not in COMPARISON_MODES:
        raise ValueError(f"comparisons must be one of {COMPARISON_MODES}, got {comparisons!r}")
    if correction not in CORRECTION_METHODS:
        raise ValueError(f"correction must be one of {CORRECTION_METHODS}, got {correction!r}")

    resolved = resolve_reference_loads(target_loads)
    rows: list[ComparisonRow] = []

    output_columns = list(ComparisonRow.__annotations__.keys()) + ["p_value_holm", "p_value_bh", "significant"]
    if observations.empty:
        return pd.DataFrame(columns=output_columns)

    capacity_by_config: dict[tuple[str, str], pd.Series] = {}
    if capacity_df is not None and not capacity_df.empty:
        non_server_capacity = capacity_df[capacity_df["role"] != "server"]
        for (cap_platform, cap_subsystem), group in non_server_capacity.groupby(["platform", "subsystem"]):
            capacity_by_config[(cap_platform, cap_subsystem)] = group.set_index("run_id")["max_entities_reached"]

    def _never_reached_reason(platform: str, subsystem: str, resolved_load: int) -> str:
        series = capacity_by_config.get((platform, subsystem))
        if series is not None:
            reached = int((series >= resolved_load).sum())
            if reached:
                return (
                    f"{subsystem} reached load {resolved_load} in {reached}/{len(series)} run(s)' "
                    f"capacity log, but none produced a usable steady-state observation there "
                    f"(see issues.csv)"
                )
        return f"{subsystem} never reached load {resolved_load} in any run"

    for metric_key, metric_obs in observations.groupby("metric_key"):
        label = metric_obs["metric_label"].iloc[0]
        unit = metric_obs["unit"].iloc[0]
        lib = metric_key in lower_is_better

        for platform, plat_obs in metric_obs.groupby("platform"):
            all_subsystems = sorted(plat_obs["subsystem"].unique())
            non_server = plat_obs[plat_obs["role"] != "server"]

            for target, resolved_load in resolved.items():
                per_config_values: dict[str, pd.Series] = {}
                for subsystem in all_subsystems:
                    sub_obs = non_server[
                        (non_server["subsystem"] == subsystem) & (non_server["entities"] == resolved_load)
                    ]
                    per_config_values[subsystem] = sub_obs.groupby("run_id")["median"].mean()

                for a, b in itertools.combinations(all_subsystems, 2):
                    va, vb = per_config_values[a], per_config_values[b]
                    n_a, n_b = len(va), len(vb)
                    planned = is_planned_comparison(a, b)

                    comparable, reason = True, ""
                    if n_a == 0:
                        comparable, reason = False, _never_reached_reason(platform, a, resolved_load)
                    elif n_b == 0:
                        comparable, reason = False, _never_reached_reason(platform, b, resolved_load)
                    elif n_a < MIN_RUNS_FOR_TEST or n_b < MIN_RUNS_FOR_TEST:
                        comparable, reason = False, f"insufficient runs at this load (n_{a}={n_a}, n_{b}={n_b})"
                    elif max(n_a, n_b) > MAX_EXACT_GROUP_SIZE:
                        comparable, reason = False, (
                            f"group too large for exact enumeration "
                            f"(n_{a}={n_a}, n_{b}={n_b} > {MAX_EXACT_GROUP_SIZE})"
                        )

                    if not comparable:
                        rows.append(ComparisonRow(
                            metric_key=metric_key, metric_label=label, unit=unit, lower_is_better=lib,
                            platform=platform, target_load=target, resolved_load=resolved_load,
                            subsystem_a=a, subsystem_b=b, n_a=n_a, n_b=n_b,
                            median_a=float(va.median()) if n_a else float("nan"),
                            median_b=float(vb.median()) if n_b else float("nan"),
                            median_ratio=float("nan"), u_statistic=float("nan"), p_value=float("nan"),
                            n_arrangements=0, cliffs_delta=float("nan"), effect_size="n/a",
                            comparable=False, reason=reason, planned=planned,
                        ))
                        continue

                    mw = mannwhitney_exact(va.tolist(), vb.tolist())
                    delta = cliffs_delta(va.tolist(), vb.tolist())
                    median_a, median_b = float(va.median()), float(vb.median())
                    rows.append(ComparisonRow(
                        metric_key=metric_key, metric_label=label, unit=unit, lower_is_better=lib,
                        platform=platform, target_load=target, resolved_load=resolved_load,
                        subsystem_a=a, subsystem_b=b, n_a=n_a, n_b=n_b,
                        median_a=median_a, median_b=median_b,
                        median_ratio=(median_a / median_b) if median_b else float("nan"),
                        u_statistic=mw.u, p_value=mw.p_value, n_arrangements=mw.n_arrangements,
                        cliffs_delta=delta, effect_size=cliffs_delta_effect_size(delta),
                        comparable=True, reason="", planned=planned,
                    ))

    df = pd.DataFrame([asdict(r) for r in rows], columns=list(ComparisonRow.__annotations__.keys()))
    df["p_value_holm"] = np.nan
    df["p_value_bh"] = np.nan
    df["significant"] = False

    family_mask = df["comparable"] & (df["planned"] if comparisons == "planned" else True)
    for _, group in df[family_mask].groupby(["metric_key", "platform", "target_load"]):
        raw_p = group["p_value"].tolist()
        df.loc[group.index, "p_value_holm"] = holm_correction(raw_p)
        df.loc[group.index, "p_value_bh"] = benjamini_hochberg_correction(raw_p)

    correction_column = {"holm": "p_value_holm", "bh": "p_value_bh"}.get(correction)
    if correction_column is not None:
        df.loc[family_mask, "significant"] = df.loc[family_mask, correction_column] < alpha
    else:  # "none": no multiple-comparison correction, raw p-value against alpha
        df.loc[family_mask, "significant"] = df.loc[family_mask, "p_value"] < alpha

    return df[output_columns]


# ---------------------------------------------------------------------------
# Figure data
# ---------------------------------------------------------------------------

def metric_vs_load_curve(observations: pd.DataFrame) -> pd.DataFrame:
    """One row per (platform, subsystem, role, metric, entities): the
    median-of-medians across runs plus the IQR of per-run medians, ready to
    drive a metric-vs-load line with an IQR band across executions."""
    group_cols = ["platform", "subsystem", "role", "metric_key", "metric_label", "unit", "entities"]
    if observations.empty:
        return pd.DataFrame(columns=group_cols + ["n_runs", "median_of_medians", "q1_of_medians", "q3_of_medians", "iqr_of_medians"])

    per_run = (
        observations.groupby(group_cols + ["run_id"])["median"].mean().reset_index()
    )
    curve = per_run.groupby(group_cols)["median"].agg(
        n_runs="count",
        median_of_medians="median",
        q1_of_medians=lambda s: s.quantile(0.25),
        q3_of_medians=lambda s: s.quantile(0.75),
    ).reset_index()
    curve["iqr_of_medians"] = curve["q3_of_medians"] - curve["q1_of_medians"]
    return curve.sort_values(["metric_key", "platform", "subsystem", "role", "entities"]).reset_index(drop=True)


def forest_plot_data(comparisons: pd.DataFrame) -> pd.DataFrame:
    """Comparable comparisons only, sorted for a Cliff's-delta forest plot."""
    if comparisons.empty:
        return comparisons.copy()
    comparable = comparisons[comparisons["comparable"]].copy()
    return comparable.sort_values(
        ["metric_key", "platform", "target_load", "cliffs_delta"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--loads", type=int, nargs="+", default=list(DEFAULT_REFERENCE_LOADS))
    parser.add_argument(
        "--metrics", nargs="+", default=[key for key, *_ in METRICS_DEFAULT],
        help="metric keys to include, e.g. fps cpu network_rtt",
    )
    parser.add_argument("--transition-seconds", type=float, default=DEFAULT_TRANSITION_SECONDS)
    parser.add_argument("--alpha", type=float, default=ALPHA_DEFAULT)
    parser.add_argument("--comparisons", choices=COMPARISON_MODES, default=COMPARISONS_DEFAULT)
    parser.add_argument("--correction", choices=CORRECTION_METHODS, default=CORRECTION_DEFAULT)
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    metrics = [(k, label, unit) for k, label, unit, _ in METRICS_DEFAULT if k in args.metrics]
    lower_is_better = {k for k, _, _, lib in METRICS_DEFAULT if lib}

    runs, issues = discover_runs(args.data_root)
    print(f"Discovered {len(runs)} usable (platform, subsystem, role) sources; {len(issues)} loading issues.")

    observations, obs_issues = build_observations(runs, metrics, args.transition_seconds)
    issues.extend(obs_issues)
    print(f"Built {len(observations)} (run, metric, palier) observations; {len(obs_issues)} extraction issues.")

    capacity = compute_capacity(runs)
    headline = capacity_headline(capacity)
    outlier_issues = detect_capacity_outliers(capacity)
    issues.extend(outlier_issues)
    if outlier_issues:
        print(f"Flagged {len(outlier_issues)} capacity outlier run(s) -- see issues.csv, not auto-excluded.")

    comparisons = compare_configurations(
        observations, args.loads, lower_is_better, args.alpha, args.comparisons, args.correction,
        capacity_df=capacity,
    )
    curve = metric_vs_load_curve(observations)
    forest = forest_plot_data(comparisons)
    coverage = load_coverage_table(observations, capacity, args.loads)
    coverage_gap_issues = detect_coverage_gaps(coverage)
    issues.extend(coverage_gap_issues)
    if coverage_gap_issues:
        print(f"Flagged {len(coverage_gap_issues)} (platform, load, subsystem) coverage gap(s) -- see issues.csv.")

    observations.to_csv(args.output_dir / "observations_long.csv", index=False)
    capacity.to_csv(args.output_dir / "capacity.csv", index=False)
    headline.to_csv(args.output_dir / "capacity_headline.csv", index=False)
    comparisons.to_csv(args.output_dir / "test_results.csv", index=False)
    curve.to_csv(args.output_dir / "metric_vs_load.csv", index=False)
    forest.to_csv(args.output_dir / "cliffs_delta_forest.csv", index=False)
    coverage.to_csv(args.output_dir / "load_coverage.csv", index=False)

    issues_df = pd.DataFrame([asdict(i) for i in issues], columns=list(LoadIssue.__annotations__.keys()))
    issues_df.to_csv(args.output_dir / "issues.csv", index=False)

    n_sig = int(comparisons["significant"].sum()) if not comparisons.empty else 0
    n_comparable = int(comparisons["comparable"].sum()) if not comparisons.empty else 0
    n_planned_comparable = int((comparisons["comparable"] & comparisons["planned"]).sum()) if not comparisons.empty else 0
    print(
        f"{n_comparable} comparable pairs ({n_planned_comparable} planned), "
        f"{n_sig} significant (correction={args.correction}, comparisons={args.comparisons}, alpha={args.alpha})."
    )
    print(f"Wrote outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
