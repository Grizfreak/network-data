import sys
from pathlib import Path
from statistics import median

import streamlit as st
import pandas as pd

"""
Streamlit application UI for the Benchmark Metrics Viewer.

This module provides the interactive controls and layout used to
load benchmark CSV files, pair stat files with event files,
select metrics, and render Plotly figures. The code here focuses on
presentation and user interaction; data extraction and metric
construction are delegated to `metrics_engine` and `data_loader`.

Lecture note: use this file to demonstrate how a small interactive
frontend orchestrates data-processing helpers and plotting utilities.
"""

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Local application modules
from data_loader import (
    auto_pair_files,
    extract_timestamp,
    get_pc_and_quest_folders,
    is_quest_server_artefact,
    list_pc_and_quest_folders,
    load_csv_files_from_folder,
    normalize_timestamp,
    NETWORKED_TECH_KEYWORDS,
)
from metrics_engine import (
    build_datasets,
    get_available_metrics,
    metric_series_from_stats,
)
from label_formatting import (
    STANDARD_METRIC_KEYS,
    _group_key_to_display,
    _is_client_label,
    _is_godot_file_name,
    _is_godot_label,
    _is_pc_label,
    _is_quest_label,
    _keep_for_quest_standard_metric,
    _run_group_key,
    _split_subsystem_label,
    short_label,
)
from plotting import _dedupe_candidates, _dedupe_candidates_by_group, build_metric_figures

# PCAP processing tools (imported once at module level)
import pcap_to_csv as pcap_tools
import pcap_to_csv_quest as pcap_quest_tools

# Re-export key functions from PCAP tools for backward compatibility
cleanup_pcap_folder_csv = pcap_tools.cleanup_pcap_folder_csv
convert_pcap_folder_to_csv = pcap_tools.convert_pcap_folder_to_csv
find_pc_capture_files = pcap_tools.find_pc_capture_files

cleanup_quest_captures_csv = pcap_quest_tools.cleanup_quest_captures_csv
convert_quest_captures_to_csv = pcap_quest_tools.convert_quest_captures_to_csv
find_quest_capture_folders = pcap_quest_tools.find_quest_capture_folders
find_quest_capture_files = pcap_quest_tools.find_quest_capture_files
is_photon_capture_path = pcap_quest_tools.is_photon_capture_path
find_dominant_quest_conversation = pcap_quest_tools.find_dominant_quest_conversation

st.set_page_config(page_title="Benchmark Metrics Viewer", layout="wide")

st.title("Benchmark Metrics Viewer")
st.markdown("Load PC, Quest, and Godot benchmark data. Choose a metric (FPS, Memory, CPU, GPU, Network, or Godot profiler columns) and the app will plot either per-frame or per-GameObject series.")

# Initialize session state for pairings
if "pairings_state" not in st.session_state:
    st.session_state.pairings_state = {}


stats_files = []
events_files = []

# Load data from data folders
data_root = Path(__file__).resolve().parents[1] / "data"
pc_folder, quest_folder = get_pc_and_quest_folders(data_root)

# Show available folders
st.info(f"Data folder: {data_root}")
if pc_folder:
    st.success(f"✓ PC data found: {pc_folder.name}")
else:
    st.warning("✗ No PC data folder found")

if quest_folder:
    st.success(f"✓ Quest data found: {quest_folder.name}")
else:
    st.warning("✗ No Quest data folder found")

godot_present = any(
    _is_godot_file_name(csv_file.name)
    for folder in (pc_folder, quest_folder)
    if folder is not None
    for csv_file in folder.glob("*.csv")
)
if godot_present:
    st.success("✓ Godot data found in the capture folders")
    st.warning(
        "Godot profiler exports do not expose every metric used by PC/Quest captures, so some plots (for example CPU %, GPU, or network-derived views) may be unavailable depending on the CSV columns you exported."
    )

def _make_progress_tracker(total: int, verb: str):
    """Create a Streamlit progress bar + status line driven by a simple
    per-file callback, for batch pcap convert/cleanup operations that
    otherwise give no feedback until the whole multi-folder batch is done."""
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    count = [0]

    def _on_file(path: Path) -> None:
        count[0] += 1
        status_text.text(f"{verb} {count[0]}/{total}: {path.parent.name}/{path.name}")
        progress_bar.progress(min(count[0] / total, 1.0) if total else 1.0)

    def _finish() -> None:
        progress_bar.empty()
        status_text.empty()

    return _on_file, _finish


if pc_folder:
    # Per-folder pcap counts across every PC benchmark run (#1, #2, ...).
    # The convert/delete buttons below now process every one of these
    # folders, not just the most recently modified one -- lets you spot
    # a run that's missing captures at a glance, and one click handles
    # the whole dataset.
    pc_folders_all, _ = list_pc_and_quest_folders(data_root)
    pc_pcap_counts = [(folder, len(find_pc_capture_files(folder))) for folder in pc_folders_all]
    total_pc_pcap_count = sum(count for _, count in pc_pcap_counts)

    with st.expander(f"PC capture tools ({total_pc_pcap_count} pcap file(s) found across {len(pc_folders_all)} folder(s))", expanded=False):
        if pc_pcap_counts:
            st.caption("PCAP files found per PC folder (all are processed by the buttons below):")
            for folder, count in sorted(pc_pcap_counts, key=lambda item: item[0].name):
                marker = " (most recently modified)" if folder == pc_folder else ""
                st.write(f"{folder.name}{marker}: {count} pcap file(s)")

        pcap_bucket_seconds = st.number_input(
            "PCAP bucket size (seconds)",
            min_value=0.1,
            value=1.0,
            step=0.1,
        )
        overwrite_pcap_csv = st.checkbox("Overwrite existing pcap CSV outputs", value=False)
        convert_col, cleanup_col = st.columns(2)
        with convert_col:
            convert_pcaps = st.button("Convert every PC pcap to CSV (all folders)")
        with cleanup_col:
            cleanup_pcaps = st.button("Delete generated PC pcap CSVs (all folders)")

        if convert_pcaps:
            all_converted, all_skipped, all_warnings, all_errors = [], [], [], []
            on_file, finish = _make_progress_tracker(total_pc_pcap_count, "Converting")
            for folder in pc_folders_all:
                result = convert_pcap_folder_to_csv(
                    folder,
                    bucket_seconds=float(pcap_bucket_seconds),
                    overwrite=overwrite_pcap_csv,
                    progress_callback=on_file,
                )
                all_converted.extend(result["converted"])
                all_skipped.extend(result["skipped"])
                all_warnings.extend(result.get("warnings", []))
                all_errors.extend(result["errors"])
            finish()

            if all_converted:
                st.success(f"Converted {len(all_converted)} pcap file(s) to CSV across {len(pc_folders_all)} folder(s).")
                for pcap_path, output_path, row_count in all_converted:
                    st.write(f"{pcap_path.parent.name}/{pcap_path.name} -> {output_path.name} ({row_count} bucket(s))")
            if all_skipped:
                st.info(f"Skipped {len(all_skipped)} existing CSV file(s).")
            if all_warnings:
                for pcap_path, message in all_warnings:
                    st.warning(f"{pcap_path.parent.name}/{pcap_path.name}: {message}")
            if all_errors:
                for pcap_path, message in all_errors:
                    st.warning(f"Failed to convert {pcap_path.parent.name}/{pcap_path.name}: {message}")
            if not all_converted and not all_skipped and not all_errors:
                st.info("No PC pcap or pcapng files found in any PC folder.")

        if cleanup_pcaps:
            all_deleted, all_missing, all_errors = [], [], []
            on_file, finish = _make_progress_tracker(total_pc_pcap_count, "Checking")
            for folder in pc_folders_all:
                result = cleanup_pcap_folder_csv(folder, progress_callback=on_file)
                all_deleted.extend(result["deleted"])
                all_missing.extend(result["missing"])
                all_errors.extend(result["errors"])
            finish()

            if all_deleted:
                st.success(f"Deleted {len(all_deleted)} generated CSV file(s) across {len(pc_folders_all)} folder(s).")
                for output_path in all_deleted:
                    st.write(f"{output_path.parent.name}/{output_path.name}")
            if all_missing:
                st.info(f"{len(all_missing)} generated CSV file(s) were already missing.")
            if all_errors:
                for output_path, message in all_errors:
                    st.warning(f"Failed to delete {output_path.parent.name}/{output_path.name}: {message}")
            if not all_deleted and not all_missing and not all_errors:
                st.info("No generated pcap CSV files found in any PC folder.")

# Quest capture tools: same workflow as PC, but isolated to Quest captures.
if quest_folder:
    # Per-folder pcap counts across every Quest benchmark run (#1, #2, ...).
    # The convert/delete buttons below now process every one of these
    # folders, not just the most recently modified one.
    _, quest_folders_all = list_pc_and_quest_folders(data_root)
    quest_pcap_counts = [(folder, len(find_quest_capture_files(folder))) for folder in quest_folders_all]
    total_quest_pcap_count = sum(count for _, count in quest_pcap_counts)

    with st.expander(
        f"Quest capture tools ({total_quest_pcap_count} pcap file(s) found across {len(quest_folders_all)} folder(s))",
        expanded=False,
    ):
        if quest_pcap_counts:
            st.caption("PCAP files found per Quest folder (all are processed by the buttons below):")
            for folder, count in sorted(quest_pcap_counts, key=lambda item: item[0].name):
                marker = " (most recently modified)" if folder == quest_folder else ""
                st.write(f"{folder.name}{marker}: {count} pcap file(s)")

        quest_pcap_bucket_seconds = st.number_input(
            "Quest PCAP bucket size (seconds)",
            min_value=0.1,
            value=1.0,
            step=0.1,
            key="quest_pcap_bucket_seconds",
        )
        quest_overwrite_pcap_csv = st.checkbox(
            "Overwrite existing Quest pcap CSV outputs",
            value=False,
            key="quest_overwrite_pcap_csv",
        )
        # Photon-specific option: detect the conversation (IP pair) with the
        # most packets and keep only those packets in the output CSV. This is
        # useful when a Quest capture mixes Photon traffic with background
        # noise (DNS, captive portal, etc.). Counted across every folder now
        # that the buttons below process all of them.
        quest_pcap_files_all = [f for _, files in (
            (folder, find_quest_capture_files(folder)) for folder in quest_folders_all
        ) for f in files]
        photon_capture_count = sum(
            1 for f in quest_pcap_files_all if is_photon_capture_path(f)
        )
        quest_photon_filter_disabled = photon_capture_count == 0
        if quest_photon_filter_disabled:
            st.caption(
                "No Photon captures detected in any Quest folder — the "
                "conversation filter is disabled."
            )
        quest_photon_conversation_filter = st.checkbox(
            f"Photon: keep only the dominant conversation "
            f"({photon_capture_count} Photon capture(s) detected)",
            value=False,
            key="quest_photon_conversation_filter",
            disabled=quest_photon_filter_disabled,
        )
        if quest_photon_conversation_filter and not quest_photon_filter_disabled:
            with st.expander("Photon conversation preview", expanded=False):
                for capture_path in quest_pcap_files_all:
                    if not is_photon_capture_path(capture_path):
                        continue
                    try:
                        pair = find_dominant_quest_conversation(capture_path)
                    except Exception as exc:  # noqa: BLE001
                        st.warning(
                            f"{capture_path.parent.name}/{capture_path.name}: could not detect "
                            f"conversation ({exc})"
                        )
                        continue
                    if pair is None:
                        st.warning(
                            f"{capture_path.parent.name}/{capture_path.name}: no IP packets found."
                        )
                    else:
                        st.write(
                            f"{capture_path.parent.name}/{capture_path.name}: {pair[0]} <-> {pair[1]}"
                        )
        quest_convert_col, quest_cleanup_col = st.columns(2)
        with quest_convert_col:
            quest_convert_pcaps = st.button("Convert every Quest pcap to CSV (all folders)")
        with quest_cleanup_col:
            quest_cleanup_pcaps = st.button("Delete generated Quest pcap CSVs (all folders)")

        if quest_convert_pcaps:
            all_converted, all_skipped, all_warnings, all_errors = [], [], [], []
            on_file, finish = _make_progress_tracker(len(quest_pcap_files_all), "Converting")
            for folder in quest_folders_all:
                result = convert_quest_captures_to_csv(
                    folder,
                    bucket_seconds=float(quest_pcap_bucket_seconds),
                    overwrite=quest_overwrite_pcap_csv,
                    photon_conversation_filter=quest_photon_conversation_filter,
                    progress_callback=on_file,
                )
                all_converted.extend(result["converted"])
                all_skipped.extend(result["skipped"])
                all_warnings.extend(result.get("warnings", []))
                all_errors.extend(result["errors"])
            finish()

            if all_converted:
                st.success(f"Converted {len(all_converted)} Quest pcap file(s) to CSV across {len(quest_folders_all)} folder(s).")
                for pcap_path, output_path, row_count in all_converted:
                    st.write(f"{pcap_path.parent.name}/{pcap_path.name} -> {output_path.name} ({row_count} bucket(s))")
            if all_skipped:
                st.info(f"Skipped {len(all_skipped)} existing CSV file(s).")
            if all_warnings:
                for pcap_path, message in all_warnings:
                    st.warning(f"{pcap_path.parent.name}/{pcap_path.name}: {message}")
            if all_errors:
                for pcap_path, message in all_errors:
                    st.warning(f"Failed to convert {pcap_path.parent.name}/{pcap_path.name}: {message}")
            if not all_converted and not all_skipped and not all_errors:
                st.info("No Quest pcap or pcapng files found in any Quest folder.")

        if quest_cleanup_pcaps:
            all_deleted, all_missing, all_errors = [], [], []
            on_file, finish = _make_progress_tracker(len(quest_pcap_files_all), "Checking")
            for folder in quest_folders_all:
                result = cleanup_quest_captures_csv(folder, progress_callback=on_file)
                all_deleted.extend(result["deleted"])
                all_missing.extend(result["missing"])
                all_errors.extend(result["errors"])
            finish()

            if all_deleted:
                st.success(f"Deleted {len(all_deleted)} generated Quest CSV file(s) across {len(quest_folders_all)} folder(s).")
                for output_path in all_deleted:
                    st.write(f"{output_path.parent.name}/{output_path.name}")
            if all_missing:
                st.info(f"{len(all_missing)} generated Quest CSV file(s) were already missing.")
            if all_errors:
                for output_path, message in all_errors:
                    st.warning(f"Failed to delete {output_path.parent.name}/{output_path.name}: {message}")
            if not all_deleted and not all_missing and not all_errors:
                st.info("No generated Quest pcap CSV files found in any Quest folder.")

# Selector for which run(s) to load. Each folder is a full repeated trial
# of the same benchmark sweep, so selecting several PC (or Quest) runs
# lets the "Average across selected runs" option below combine them.
st.subheader("Select Data to Load")
pc_run_folders, quest_run_folders = list_pc_and_quest_folders(data_root)

if not pc_run_folders and not quest_run_folders:
    st.error("No data folders found in ./data")
    st.stop()

selected_pc_folders = []
selected_quest_folders = []
if pc_run_folders:
    selected_pc_names = st.multiselect(
        "PC runs to load:",
        options=[f.name for f in pc_run_folders],
        default=[f.name for f in pc_run_folders],
    )
    selected_pc_folders = [f for f in pc_run_folders if f.name in selected_pc_names]
if quest_run_folders:
    selected_quest_names = st.multiselect(
        "Quest runs to load:",
        options=[f.name for f in quest_run_folders],
        default=[f.name for f in quest_run_folders],
    )
    selected_quest_folders = [f for f in quest_run_folders if f.name in selected_quest_names]

if not selected_pc_folders and not selected_quest_folders:
    st.warning("Please select at least one run to load.")
    st.stop()

# Load the selected data
@st.cache_resource(show_spinner=False)
def _load_source_files(folder: Path, source_label: str):
    """Load every CSV in `folder` and tag it with `source_label`.

    Cached: this reads and parses every CSV in `folder` from disk, which
    is wasted work to repeat on every Streamlit rerun -- and Streamlit
    reruns the *entire* script on every single widget interaction,
    including ones that have nothing to do with which folders are
    selected (e.g. a quick-filter button click, which only ever changes
    `line_filter_choices`).

    `st.cache_resource`, not `st.cache_data`: nothing downstream mutates
    these DataFrames in place (see e.g. `load_csv_files_from_folder`'s
    `df = df.rename(...)`, never `inplace=True`), so it's safe to hand out
    the same objects on every cache hit instead of `cache_data`'s default
    deep-copy-on-every-retrieval. That copy isn't just overhead here: for
    the pyarrow-backed columns some of these CSVs parse into, round-
    tripping through it shifts Streamlit's content hash for the *next*
    cached call downstream (`_compute_line_filter_candidates` /
    `_cached_build_metric_figures`) just enough to cause one extra,
    otherwise-unexplained cache miss before things stabilize.

    Keyed on `(folder, source_label)`, so it's
    invalidated automatically if a different set of runs is selected.

    Godot files are treated like every other benchmark: they keep the
    platform tag from the capture folder (PC or Quest) and are detected
    as "Godot" by their filename token when the legend is built.
    """
    stats, events, errors = load_csv_files_from_folder(folder)
    stats = [(f"[{source_label}] {name}", df) for name, df in stats]
    events = [(f"[{source_label}] {name}", df) for name, df in events]

    # The Quest headset never hosts a server, for any tech -- the server
    # always runs on the PC. When a trial is recorded, the PC-hosted
    # server's own profiler_stats/events CSVs routinely get dropped into
    # the same benchmark folder as the Quest client's data for
    # convenience, so without this filter they get tagged "[Quest]" and
    # produce nonsensical "Quest · <Tech> Server" lines (RTT/Upload/
    # Download data that's actually the PC server's own telemetry, not
    # anything the headset measured).
    #
    # We deliberately KEEP `*_server_capture_quest_capture_*.pcap.csv`
    # (and every other `.pcap.csv`): these are PCAP captures of the
    # traffic the PC observed while routing the headset's connection, so
    # they genuinely describe the Quest client's network activity and
    # are the intended data source for the "PCAP" plots (Packets/sec,
    # Bytes/sec, etc.) on Quest.
    #
    # The dropped artefacts are every other "*_server_*" stats/events
    # CSV: `*_server_profiler_stats-*.csv`, `*_server_events_*.csv`,
    # `server_godot_*.csv`, etc., across every tech (Photon, FishNet,
    # NGO, NetcodeEntities, Godot). See data_loader.is_quest_server_artefact
    # -- shared with the offline analysis pipeline (ccl/analyze_data.py)
    # so both tools agree on what belongs to Quest.
    if source_label == "Quest":
        stats = [(n, df) for n, df in stats if not is_quest_server_artefact(n)]
        events = [(n, df) for n, df in events if not is_quest_server_artefact(n)]

    return stats, events, errors


for folder in selected_pc_folders:
    st.info(f"Loading PC data from: {folder.name}")
    pc_stats, pc_events, pc_errors = _load_source_files(folder, "PC")
    for file_name, err in pc_errors:
        st.warning(f"Failed to read {file_name}: {err}")
    stats_files.extend(pc_stats)
    events_files.extend(pc_events)
for folder in selected_quest_folders:
    st.info(f"Loading Quest data from: {folder.name}")
    quest_stats, quest_events, quest_errors = _load_source_files(folder, "Quest")
    for file_name, err in quest_errors:
        st.warning(f"Failed to read {file_name}: {err}")
    stats_files.extend(quest_stats)
    events_files.extend(quest_events)

st.write(f"**Loaded:** {len(stats_files)} stat file(s), {len(events_files)} event file(s)")

if not stats_files and not events_files:
    st.warning("No CSV files found in selected folder.")
    st.stop()

# Auto-pair files
st.subheader("Auto-pairing options")
use_strict_pairing = st.checkbox("Use stricter auto-pairing (require higher confidence)", value=False)
min_pair_score = 150.0 if use_strict_pairing else 50.0
user_pairings, pairing_debug = auto_pair_files(stats_files, events_files, min_score=min_pair_score)
st.session_state.pairing_debug = pairing_debug

# Show pairing results
if st.session_state.get("pairing_debug"):
    with st.expander("Debug: Pairing results"):
        for line in st.session_state.pairing_debug:
            st.write(line)

# Show loading summary
st.write(f"**Loaded:** {len(stats_files)} stat file(s), {len(events_files)} event file(s)")

# Debug: show loaded files and their timestamps
if stats_files or events_files:
    with st.expander("Debug: Loaded files and timestamps"):
        if stats_files:
            st.write("**Stat files:**")
            for sname, _ in stats_files:
                ts_str, dt = extract_timestamp(sname)
                norm_ts = normalize_timestamp(ts_str) if ts_str else None
                st.write(f"  {sname} → raw: {ts_str}, normalized: {norm_ts}")
        if events_files:
            st.write("**Event files:**")
            for ename, _ in events_files:
                ts_str, dt = extract_timestamp(ename)
                norm_ts = normalize_timestamp(ts_str) if ts_str else None
                st.write(f"  {ename} → raw: {ts_str}, normalized: {norm_ts}")
        # Diagnostic: report FPS computation stats per stat file
        st.write("**Diagnostic: FPS computation per stat file**")
        for sname, sdf in stats_files:
            try:
                series, ycol = metric_series_from_stats(sdf, "fps", sname, x_axis_mode="frame")
                if series is None or ycol is None:
                    st.write(f"{sname}: no FPS series parsed")
                    continue
                # compute simple stats
                fps_vals = pd.to_numeric(series["FPS"], errors="coerce").dropna().to_numpy(dtype=float) if "FPS" in series.columns else []
                mean = float(sum(fps_vals) / len(fps_vals)) if len(fps_vals) else None
                med = float(median(fps_vals)) if len(fps_vals) else None
                count = int(len(fps_vals))
                st.write(f"{sname}: ycol={ycol}, samples={count}, mean={mean}, median={med}")
            except Exception as e:
                st.write(f"{sname}: error computing FPS diagnostics: {e}")

per_gameobject = st.checkbox("Aggregate per GameObject using events (FinishedInstantiation/StartedInstantiation)", value=True)

average_runs = st.checkbox(
    "Average across selected runs (per system)",
    value=True,
    disabled=not per_gameobject,
    help=(
        "Combine repeated runs of the same platform/subsystem/role "
        "(e.g. multiple PC runs of Photon Client) into one averaged line. "
        "Requires per-GameObject aggregation, since runs are aligned on "
        "the shared GameObjects milestones."
    ),
)

# Show pairing UI if per-GameObject is enabled
if per_gameobject and stats_files and events_files:
    st.subheader("Match stat files to event files")
    
    event_names = ["(none)"] + [name for name, _ in events_files]
    
    with st.expander("File pairings (auto-paired by timestamp)", expanded=False):
        for sname, _ in stats_files:
            stat_subsystem, stat_file = _split_subsystem_label(sname)
            # Get the auto-paired event name
            auto_match = user_pairings.get(sname)
            
            # Find the index of the default in event_names
            default_idx = 0
            if auto_match:
                try:
                    default_idx = event_names.index(auto_match)
                except ValueError:
                    default_idx = 0
            
            # Use session state to preserve user selections
            key = f"pair_{sname}"
            if key not in st.session_state:
                st.session_state[key] = auto_match or "(none)"
            
            choice = st.selectbox(
                f"Event file for {Path(sname).stem}",
                options=event_names,
                index=default_idx,
                key=key
            )
            
            if choice != "(none)":
                user_pairings[sname] = choice
                event_subsystem, event_file = _split_subsystem_label(choice)
            else:
                user_pairings[sname] = None
                event_subsystem, event_file = "(none)", "(none)"

            st.caption(
                f"Bound: {stat_subsystem} / {stat_file} -> {event_subsystem} / {event_file}"
            )

# Metric selection belongs right before plotting so matching comes first.
metric_options = {
    "FPS": "fps",
    "Memory (MB)": "memory",
    "CPU (ms)": "cpu",
    "GPU (ms)": "gpu",
    "PCAP - Packets/sec": "pcap_packets",
    "PCAP - Bytes/sec": "pcap_bytes",
    "PCAP - Packets per GameObject (delta)": "pcap_cumulative_packets",
    "PCAP - Bytes per GameObject (delta)": "pcap_cumulative_bytes",
    "Network - RTT (ms) - Calculated from RPC": "network_rtt_rpc",
    "Network - RTT (ms)": "network_rtt",
    "Network - Upload (bytes/sec)": "network_upload",
    "Network - Download (bytes/sec)": "network_download",
}

available_metrics = get_available_metrics(stats_files, metric_options)
unavailable_metrics = [m for m in metric_options.keys() if m not in available_metrics]

st.subheader("Select Metrics to Display")
col1, col2 = st.columns([3, 1])
with col1:
    selected_metrics = st.multiselect(
        "Choose metrics to display (empty = show all)",
        list(metric_options.keys()),
        default=list(available_metrics),
        disabled=False
    )
    if unavailable_metrics:
        st.info(f"Note: {', '.join(unavailable_metrics)} are not available in your data")
with col2:
    columns_count = st.selectbox("Columns", [1, 2, 3, 4], index=1)
    log_scale = st.checkbox("Logarithmic Y axis", value=False)

# Option: include unpaired stat files by falling back to per-frame conversion
include_unpaired = st.checkbox("Include unpaired stat files (fallback to per-frame)", value=False)

if not selected_metrics:
    selected_metrics = list(available_metrics)

# Convert to metric keys
selected_metric_keys = [metric_options[label] for label in selected_metrics]

# Global line filter controls
def _dataset_cache_key(files: list) -> tuple:
    """Cheap, deterministic stand-in for a list of (label, DataFrame)
    pairs, used as the cache key for the `_`-prefixed (Streamlit-unhashed)
    `_stats_files`/`_events_files` parameters below instead of letting
    `st.cache_data` hash the DataFrames themselves.

    Nothing downstream mutates these DataFrames in place after
    `_load_source_files` loads them (see that function's docstring), so
    `(label, shape, columns)` per file is a sound proxy for "did the
    content change" here -- and it's orders of magnitude cheaper to hash
    than the DataFrames. Hashing the DataFrames directly was the reason a
    quick-filter click still redid the full per-GameObject aggregation
    instead of hitting the cache on the *second* rerun specifically (every
    rerun after that hit cache reliably) -- Streamlit's own DataFrame
    hashing turned out to be the unstable piece, not anything in this
    codebase; this sidesteps it rather than depending on its internals.
    """
    return tuple((label, df.shape, tuple(df.columns)) for label, df in files)


@st.cache_data(show_spinner=False)
def _compute_line_filter_candidates(
    _stats_files, _events_files, user_pairings, selected_metric_keys,
    metric_options, per_gameobject, include_unpaired,
    stats_key, events_key,
):
    """Every raw label that could show up in the Line Filter dropdown for
    at least one selected metric.

    Cached: this calls `build_datasets()` -- the same expensive
    per-GameObject aggregation `build_metric_figures()` below also runs --
    once per selected metric, purely to enumerate labels. Without caching,
    that work happened twice on every single rerun (once here, once in
    `build_metric_figures()`) even though neither call's inputs had
    changed, e.g. on a quick-filter button click (which only ever touches
    `line_filter_choices`, not any of this function's arguments).

    `_stats_files`/`_events_files` are underscore-prefixed (and therefore
    `stats_key`/`events_key` passed alongside them) -- see
    `_dataset_cache_key()`.
    """
    candidates = set()
    for metric_key in selected_metric_keys:
        metric_label = [k for k, v in metric_options.items() if v == metric_key][0]
        preview_datasets, _ = build_datasets(
            stats_files=_stats_files,
            events_files=_events_files,
            user_pairings=user_pairings,
            selected_metric_key=metric_key,
            selected_metric_label=metric_label,
            per_gameobject=per_gameobject,
            x_axis_mode="frame",
            include_unpaired=include_unpaired,
        )
        if metric_key in STANDARD_METRIC_KEYS:
            preview_datasets = [
                (label, df) for label, df in preview_datasets
                if _keep_for_quest_standard_metric(label)
            ]
        candidates.update([label for label, _ in preview_datasets])
    return candidates


line_filter_candidates = _compute_line_filter_candidates(
    stats_files, events_files, user_pairings, selected_metric_keys,
    metric_options, per_gameobject, include_unpaired,
    _dataset_cache_key(stats_files), _dataset_cache_key(events_files),
)


# In aggregated mode (averaging runs together), the dropdown should show
# one option per averaged line, not one per individual run -- see
# _dedupe_candidates_by_group. Non-aggregated mode keeps the original
# per-run behaviour so a specific capture can still be picked out.
aggregated_line_filter = average_runs and per_gameobject
line_filter_options = (
    _dedupe_candidates_by_group(line_filter_candidates)
    if aggregated_line_filter
    else _dedupe_candidates(line_filter_candidates)
)
if "line_filter_choices" not in st.session_state:
    st.session_state.line_filter_choices = []
if "active_line_filters" not in st.session_state:
    st.session_state.active_line_filters = []

# Keep stored selections valid when metric selection changes.
st.session_state.line_filter_choices = [
    label for label in st.session_state.line_filter_choices if label in line_filter_options
]
st.session_state.active_line_filters = [
    label for label in st.session_state.active_line_filters if label in line_filter_options
]

st.subheader("Line Filter")
filter_col1, filter_col2, filter_col3 = st.columns([3, 1, 1])
with filter_col1:
    selected_line_filters = st.multiselect(
        "Choose lines to display on all plots",
        options=line_filter_options,
        default=st.session_state.line_filter_choices,
        format_func=(
            (lambda label: _group_key_to_display(_run_group_key(label)))
            if aggregated_line_filter
            else (lambda label: short_label(label, line_filter_options))
        ),
    )
    st.session_state.line_filter_choices = selected_line_filters
with filter_col2:
    if st.button("Apply"):
        st.session_state.active_line_filters = list(st.session_state.line_filter_choices)
with filter_col3:
    if st.button("Clear"):
        st.session_state.active_line_filters = []
        st.session_state.line_filter_choices = []

# Quick filters: one-click presets that pre-fill the multiselect only.
# They mutate `line_filter_choices` so the dropdown updates immediately,
# but leave `active_line_filters` untouched -- the plots only pick up the
# preset once the user presses Apply, same as a manual multiselect edit.
#
# The tech keywords come from `data_loader.NETWORKED_TECH_KEYWORDS`
# (`_CLASSIFICATION_RULES` filtered to `is_networked=True`) instead of a
# separately hand-maintained tuple, so a new networked benchmark type
# registered there is picked up here automatically. Godot is deliberately
# NOT in that set (its rule has no `is_networked=True`, see
# `_CLASSIFICATION_RULES`'s docstring) -- it has no dedicated networking
# library on the wire, so its traffic is only ever surfaced via the
# generic "server"/"client"/"pcap"/"capture" tokens below, not a tech name.
_NETWORK_TOKENS = NETWORKED_TECH_KEYWORDS + ("server", "client", "pcap", "capture")


def _is_network_label(label: str) -> bool:
    """Return True when *label* corresponds to a network-stack capture.

    This includes every networking framework covered by the benchmark
    (Photon, FishNet, NGO, NetcodeEntities, Godot) as well as generic
    PCAP capture artefacts (`*_capture_*.pcap.csv`). The Godot stack
    does not use a dedicated networking library on the wire — it
    communicates over the engine's built-in ENet/UDP transport — so
    PCAP is the only data source for its network traffic and the
    matching Godot client/server labels (e.g. `client_godot_*`,
    `godot_server_capture_*`, `godot_events_*`) must be surfaced by
    the "Network only" preset for those plots to be visible.
    """
    lowered = label.lower()
    if "_capture_" in lowered or lowered.endswith(".pcap.csv"):
        return True
    return any(token in lowered for token in _NETWORK_TOKENS)


def _quick_filter(matcher):
    return [label for label in line_filter_options if matcher(label)]


quick_row1 = st.columns(5)
with quick_row1[0]:
    if st.button("All", use_container_width=True):
        st.session_state.line_filter_choices = list(line_filter_options)
with quick_row1[1]:
    if st.button("Non-network", use_container_width=True):
        st.session_state.line_filter_choices = _quick_filter(lambda lbl: not _is_network_label(lbl))
with quick_row1[2]:
    if st.button("Network only", use_container_width=True):
        st.session_state.line_filter_choices = _quick_filter(_is_network_label)
with quick_row1[3]:
    if st.button("PC only", use_container_width=True):
        st.session_state.line_filter_choices = _quick_filter(_is_pc_label)
with quick_row1[4]:
    if st.button("Quest only", use_container_width=True):
        st.session_state.line_filter_choices = _quick_filter(_is_quest_label)

quick_row2 = st.columns(4)
with quick_row2[0]:
    if st.button("Client only", use_container_width=True):
        # Show every client-side capture across both platforms.
        st.session_state.line_filter_choices = _quick_filter(_is_client_label)
with quick_row2[1]:
    if st.button("Quest clients", use_container_width=True):
        # Narrow the client list down to Quest-only captures.
        st.session_state.line_filter_choices = _quick_filter(
            lambda lbl: _is_quest_label(lbl) and _is_client_label(lbl)
        )
with quick_row2[2]:
    if st.button("PC clients", use_container_width=True):
        # Narrow the client list down to PC-only captures. This replaces
        # the previous "Network clients" preset, which mixed platforms
        # and duplicated what "PC clients" + "Quest clients" already
        # cover for the network stacks.
        st.session_state.line_filter_choices = _quick_filter(
            lambda lbl: _is_pc_label(lbl) and _is_client_label(lbl)
        )
with quick_row2[3]:
    if st.button("PC network", use_container_width=True):
        # Keep PC + network as a separate, non-client-scoped preset so
        # users can still inspect the full PC network stack (both client
        # and server roles) without going through the client buttons.
        st.session_state.line_filter_choices = _quick_filter(
            lambda lbl: _is_pc_label(lbl) and _is_network_label(lbl)
        )

# Godot is treated like every other benchmark (a tech, not a platform),
# so this quick filter targets every Godot run across PC and Quest.
quick_row3 = st.columns(1)
with quick_row3[0]:
    if st.button("Godot only", use_container_width=True):
        st.session_state.line_filter_choices = _quick_filter(_is_godot_label)

active_line_filters = set(st.session_state.active_line_filters)
if active_line_filters:
    st.info(f"Line filter active: {len(active_line_filters)} selected")


def render_dashboard(metric_figures, title, columns_count, active_line_filters, skipped_by_filter=None):
    if not metric_figures:
        st.info(f"No compatible datasets found for {title.lower()}.")
        if active_line_filters and skipped_by_filter:
            filter_names = ", ".join(sorted(active_line_filters))
            st.caption(
                f"The active line filter ({filter_names}) excludes every "
                f"available data source for: {', '.join(sorted(skipped_by_filter))}."
            )
            st.caption("Try a different quick filter or clear the line filter to see these metrics.")
        return

    st.subheader(title)

    metrics_list = list(metric_figures.items())
    num_plots = len(metrics_list)
    num_rows = (num_plots + columns_count - 1) // columns_count

    for row_idx in range(num_rows):
        cols = st.columns(columns_count)
        for col_idx in range(columns_count):
            plot_idx = row_idx * columns_count + col_idx
            if plot_idx < num_plots:
                _, fig = metrics_list[plot_idx]
                with cols[col_idx]:
                    st.plotly_chart(fig, width='stretch')


@st.cache_data(show_spinner=False)
def _cached_build_metric_figures(
    _stats_files, _events_files, user_pairings, selected_metric_keys,
    metric_options, per_gameobject, average_runs, include_unpaired,
    active_line_filters, line_filter_candidates, stats_key, events_key,
):
    """Cached wrapper around `plotting.build_metric_figures()`.

    That function is a pure function of exactly these arguments (see its
    docstring), which makes it cacheable as-is: a rerun where none of them
    changed -- e.g. clicking a quick-filter button, which only ever
    touches `line_filter_choices`, never `active_line_filters` (that needs
    "Apply") -- is a guaranteed cache hit, skipping the per-GameObject
    aggregation entirely instead of redoing it from scratch.

    `_stats_files`/`_events_files` are underscore-prefixed (and therefore
    `stats_key`/`events_key` passed alongside them) -- see
    `_dataset_cache_key()`.
    """
    return build_metric_figures(
        stats_files=_stats_files,
        events_files=_events_files,
        user_pairings=user_pairings,
        selected_metric_keys=selected_metric_keys,
        metric_options=metric_options,
        per_gameobject=per_gameobject,
        average_runs=average_runs,
        include_unpaired=include_unpaired,
        active_line_filters=active_line_filters,
        line_filter_candidates=line_filter_candidates,
    )


# Generate and display the full dashboard
metric_figures, skipped_by_filter = _cached_build_metric_figures(
    stats_files,
    events_files,
    user_pairings,
    selected_metric_keys,
    metric_options,
    per_gameobject,
    average_runs,
    include_unpaired,
    active_line_filters,
    line_filter_candidates,
    _dataset_cache_key(stats_files),
    _dataset_cache_key(events_files),
)
render_dashboard(
    metric_figures,
    "Metrics Dashboard",
    columns_count,
    active_line_filters,
    skipped_by_filter=skipped_by_filter,
)

# Generate and display the movement-phase dashboard below the main one
# movement-phase dashboard removed (data changed; movement phase logic deprecated)
