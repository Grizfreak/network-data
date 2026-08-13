import sys
from pathlib import Path
from statistics import median

import streamlit as st
import pandas as pd
import plotly.express as px

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
    classify_subsystem,
    extract_timestamp,
    get_pc_and_quest_folders,
    is_networked_subsystem,
    is_quest_server_artefact,
    list_pc_and_quest_folders,
    load_csv_files_from_folder,
    normalize_timestamp,
    _is_quest_routed_capture,
)
from metrics_engine import average_series_across_runs, build_datasets, metric_series_from_stats

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

def _split_subsystem_label(label: str):
    """Splits a subsystem label string to determine if it belongs to PC or Quest."""
    if label.startswith("[PC] "):
        return "PC", label[5:]
    if label.startswith("[Quest] "):
        return "Quest", label[8:]
    return "Unknown", label


def _is_networked_tech_label(label: str) -> bool:
    """Keep only series from an actually-networked tech for network/PCAP plots.

    Non-networked baseline scenes (Base, Base-GPU, DOTS, solo Godot) can
    still carry an RTT/Upload/Download column in their exported CSV --
    some captures had a stray network-stats provider wired into the
    ProfilerStatsToCSVExporter component on the Unity side even though
    the scene never opens a connection, so the numbers exist but are
    meaningless. `_has_network_columns` only checks column presence, so
    without this filter those baseline runs sneak into "Network - RTT"
    etc. plots as if they were real network telemetry. Delegates to
    `classify_subsystem` + `is_networked_subsystem` (shared with the
    offline analysis pipeline) instead of a filename substring check:
    a "godot client"/"godot server" (space-joined) substring check used
    to sit here, but real filenames are underscore-joined
    (`godot_client_capture`, `server_godot_...`), so it never actually
    matched anything and silently excluded every Godot PCAP series.
    """
    return is_networked_subsystem(classify_subsystem(label))


def short_label(label: str, all_labels: list[str] | None = None) -> str:
    """Return a friendly, human-readable label like 'PC · DOTS Server'.

    The label disambiguates client/server roles for both platforms and
    appends a short timestamp when several files would otherwise map to
    the same display name (e.g. multiple NetcodeEntities runs). When a
    `all_labels` collection is provided, the function also appends a
    short type tag — `(stats)`, `(events)`, or `(trace)` — so files that
    share the same capture timestamp but are different artefacts
    (events CSV, profiler stats CSV, Android trace CSV) remain
    distinguishable in the legend and dropdown.
    """
    if label.startswith("[PC]"):
        platform = "PC"
    elif label.startswith("[Quest]"):
        platform = "Quest"
    else:
        platform = "Quest"

    name = label.lower()

    if "photon" in name:
        tech = "Photon"
    elif "fishnet" in name:
        tech = "FishNet"
    elif "ngo" in name:
        tech = "NGO"
    elif "netcodeentities" in name:
        tech = "NetcodeEntities"
    elif "godot" in name:
        # Godot is a benchmark like the others, not a separate category:
        # it inherits its platform from the capture folder (PC/Quest) and
        # exposes "Godot" as the tech tag in the legend.
        tech = "Godot"
    elif "dots" in name:
        tech = "DOTS"
    elif "gpu" in name:
        tech = "Base GPU"
    elif "base" in name:
        tech = "Base"
    elif "benchmarkgo" in name:
        tech = "BenchmarkGO"
    else:
        tech = "Base"
    if platform == "Quest" and _is_quest_routed_capture(label):
        # PCAP capture of Quest-client traffic taken on the PC side while
        # it routes the headset's connection. Its filename carries a
        # literal "server" token (traffic direction, not an actual
        # server role) that the plain substring checks below would
        # otherwise misread as a server capture -- the Quest headset
        # never hosts a server, for any tech.
        tech += " Client"
    elif "client" in name:
        tech += " Client"
    elif "server" in name:
        tech += " Server"
    elif platform == "Quest" and tech == "Godot" and _type_tag_for(label) == "trace":
        # The Quest Godot Android trace (`com.IMT_Atlantique.godot_network_benchmark#GodotApp-*.csv`)
        # is emitted by the running app itself, i.e. the client. It carries
        # no `_client_` / `_server_` token in its filename, so without this
        # branch it would render as a bare `Quest · Godot` line that
        # duplicates the client view. The PCAP capture output and the
        # events/stats CSVs all already have explicit `client`/`server`
        # tokens, so they are unaffected.
        tech += " Client"
    elif platform == "Quest" and is_networked_subsystem(tech) and _type_tag_for(label) == "trace":
        # Same situation as the Godot branch above, generalized: FishNet /
        # NGO / Photon / NetcodeEntities have no non-networked baseline
        # mode, so their bare Quest trace (`com.IMT_Atlantique.<tech>#...`,
        # no `_client_`/`_server_` token) is unambiguously the client run
        # -- unlike Godot there's no unrelated baseline group it could
        # collide with. Without this branch it rendered as a separate,
        # confusingly-named `Quest · FishNet` line next to
        # `Quest · FishNet Client`, as if they were two different runs.
        tech += " Client"

    # Append a compact timestamp so files from different captures remain
    # distinguishable in the legend / dropdown. The label may carry either
    # the profiler-stats format "YYYY.MM.DD-HH.MM" or the event format
    # "YYYYMMDD_HHMMSS" (which contains seconds we want to drop).
    short_ts, _ = extract_timestamp(label)
    if short_ts:
        normalized = normalize_timestamp(short_ts)  # YYYYMMDD_HHMM
        if normalized and len(normalized) >= 13:
            time_part = normalized[9:13]
            tech = f"{tech} \u00b7 {normalized[6:8]}.{time_part}"

    base = f"{platform} \u00b7 {tech}"

    # Detect collisions: when more than one underlying label maps to the
    # same `base` string, append a type tag so the dropdown / legend lets
    # the user tell events, profiler stats, and Android trace apart.
    if all_labels:
        siblings = [lbl for lbl in all_labels if short_label(lbl) == base]
        if len(siblings) > 1 and label in siblings:
            type_tag = _type_tag_for(label)
            if type_tag:
                base = f"{base} ({type_tag})"

    return base


def _type_tag_for(label: str) -> str:
    """Classify a CSV label as stats, events or trace for disambiguation."""
    lower = label.lower()
    if "events" in lower:
        return "events"
    if "profiler_stats" in lower:
        return "stats"
    if (
        "unityplayer" in lower
        or "imt_atlantique" in lower
        or lower.endswith("#unityplayergameactivity")
        or "#godotapp" in lower
    ):
        # "#GodotApp-<timestamp>.csv" is the Android on-device trace
        # naming convention regardless of package id -- the earliest
        # Quest capture used the default "com.example" package before
        # it was renamed to "com.IMT_Atlantique", so package-name
        # matching alone misses it.
        return "trace"
    if ".pcap.csv" in lower or "_capture_" in lower:
        return "pcap"
    return ""


def _is_pc_label(label: str) -> bool:
    return label.startswith("[PC]")


def _is_quest_label(label: str) -> bool:
    return label.startswith("[Quest]")


def _is_client_label(label: str) -> bool:
    """Return True only when the label carries an explicit client marker.

    Matches both the profiler-stats naming convention (`..._client_...`)
    and the event-style naming convention (`..._client_events_...`).
    Quest Android traces (`com.IMT_Atlantique.*`) carry no role token
    and are matched separately via `_is_quest_label` — they are NOT
    treated as client by this predicate so that the "Quest clients" /
    "Client only" quick filters stay focused on network-stack captures.

    PC baseline files (dots / gpu / events / generic `profiler_stats`
    without a client/server token) are role-agnostic and intentionally
    excluded: they are still selectable via "PC only" / "Non-network"
    presets or the manual multiselect.
    """
    lowered = label.lower()
    return (
        "_client_" in lowered
        or "_client_events_" in lowered
        or "_client_profiler_" in lowered
    )


def _is_server_label(label: str) -> bool:
    """Return True only when the label belongs to a real server-side role.

    In this dataset, the Quest device never acts as a server: any
    `*_server_*` file coming from the Quest is actually a PCAP capture of
    *server-bound* traffic observed on the Quest, not a server hosted on
    the device. To avoid surfacing misleading "server" lines, this
    predicate is intentionally scoped to PC files only.
    """
    if not _is_pc_label(label):
        return False
    lowered = label.lower()
    return (
        "_server_" in lowered
        or "_server_events_" in lowered
        or "_server_profiler_" in lowered
    )


def _run_group_key(label: str) -> tuple[str, str, str]:
    """Group key identifying "the same system" across repeated run
    folders, ignoring per-run timestamps: (platform, subsystem, role).
    Used to average multiple runs of the same platform/subsystem/role
    into one line -- client and server stay distinct so a trial folder's
    client/server pair is never averaged together as if it were two
    repeats of the same measurement.

    Role uses a plain "client"/"server" substring match (same approach
    as short_label()'s tech-role suffix) rather than the stricter
    _is_client_label()/_is_server_label() predicates: those require a
    `_client_`/`_server_` token wrapped in underscores, which the Godot
    Network files (`client_godot_...csv` / `server_godot_...csv`, role
    token as a bare prefix) don't have -- using the strict predicates
    here silently merged a single run's Godot client+server pair into
    one averaged "run".
    """
    platform = "PC" if _is_pc_label(label) else "Quest"
    subsystem = classify_subsystem(label)
    lowered = label.lower()
    if platform == "Quest" and _is_quest_routed_capture(label):
        # PCAP capture of Quest-client traffic taken on the PC side
        # while it routes the headset's connection. Its filename carries
        # a literal "server" token (denoting traffic *direction*, not an
        # actual server role) that would otherwise misclassify this as
        # server data -- the Quest headset never hosts a server, for any
        # tech, so this must always be Client.
        role = "Client"
    elif "client" in lowered:
        role = "Client"
    elif "server" in lowered:
        role = "Server"
    elif platform == "Quest" and subsystem == "Godot" and _type_tag_for(label) == "trace":
        # Every Quest tech is exported twice per run: once as a
        # profiler_stats CSV and once as the on-device Android trace
        # (`com.IMT_Atlantique...#GodotApp-*.csv` / `#UnityPlayerGameActivity-*.csv`).
        # Godot is the only tech with a *legitimate* role="" group (the
        # single-player baseline) that the trace could collide with -- and
        # for the networked-run trace specifically, colliding would
        # silently mix networked-client data into the baseline average.
        # Giving the trace its own non-colliding role avoids that. (Every
        # other networked tech's trace is handled by the branch below,
        # which folds it straight into "Client" instead -- see there for
        # why that's safe for them but not for Godot.)
        role = "Trace (network run)" if "network" in lowered else "Trace"
    elif platform == "Quest" and is_networked_subsystem(subsystem) and _type_tag_for(label) == "trace":
        # FishNet / NGO / Photon / NetcodeEntities have no non-networked
        # baseline mode, so their bare Quest trace (no `_client_`/
        # `_server_` token) is unambiguously the client run -- there's no
        # unrelated role="" group it could wrongly get averaged into, so
        # unlike Godot it can just join the real "Client" group instead of
        # needing its own separate "Trace" bucket. This collapses the
        # previous `Quest · FishNet` / `Quest · FishNet Client` split
        # (same physical run, two exports) into a single line.
        role = "Client"
    else:
        role = ""
    return platform, subsystem, role


def _group_key_to_display(key: tuple[str, str, str]) -> str:
    """Render a `_run_group_key()` tuple as the display string used both
    by the averaged legend line (see create_standard_plot) and by the
    aggregated-mode Line Filter dropdown, so the two stay in sync."""
    platform, subsystem, role = key
    role_suffix = f" {role}" if role else ""
    return f"{platform} · {subsystem}{role_suffix}"


def _is_godot_label(label: str) -> bool:
    """Return True when the file name (after the platform tag) is a Godot run.

    Godot files used to be tagged with a separate `[Godot] ` prefix, but
    they are now treated like every other benchmark: they keep the
    platform tag from the capture folder (`[PC]` / `[Quest]`) and expose
    "Godot" as the tech. We detect them by their `godot` token in the
    filename instead of by an exclusive prefix.
    """
    return "godot" in label.lower()


def _is_godot_file_name(file_name: str) -> bool:
    return "godot" in file_name.lower()


STANDARD_METRIC_KEYS = ("fps", "memory", "cpu", "gpu")


def _keep_for_quest_standard_metric(label: str) -> bool:
    """For FPS/Memory/CPU/GPU on Quest, keep only the data source that
    actually ends up plotted -- see the call site in build_metric_figures
    for why. Shared with the Line Filter candidate list so the dropdown
    never offers a label (e.g. "Quest · Godot Trace") that these metrics
    silently drop later, which used to leave dead entries in the filter."""
    if not label.startswith("[Quest] "):
        return True
    if _is_godot_label(label):
        # Godot is exempted from the "trace files only" rule below so it
        # uses the same profiler_stats source as every other platform/tech.
        # But its Android trace re-export of that same run
        # (com.IMT_Atlantique...#GodotApp-*.csv) must still be dropped here
        # rather than left to _collapse_datasets: that dedupe only merges
        # siblings whose short_label() timestamps round to the same minute,
        # which is a coincidence that fails for roughly one run in five
        # (profiler_stats and the trace routinely start a couple seconds
        # apart, straddling a minute boundary) -- when it fails, the trace
        # survives as an unmerged, unaveraged singleton line instead of
        # quietly disappearing like its siblings. Dropping every Godot
        # trace file here, unconditionally, makes the outcome deterministic.
        return _type_tag_for(label) != "trace"
    return "com.IMT_Atlantique" in label


# allow importing project helpers (assemble.py)
try:
    import assemble
except Exception:
    assemble = None

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
def _load_source_files(folder: Path, source_label: str):
    """Load every CSV in `folder` and tag it with `source_label`.

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

# Verify we have data
if assemble is None:
    st.warning("Note: assemble helper not available (some features may be limited).")

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

# Detect which metrics are actually available in the loaded data
def get_available_metrics(stats_files, metric_options):
    """Scan loaded files and return only metrics that have data."""
    available = set()
    godot_present = False
    rtt_cols_present = False
    rtt_rpc_cols_present = False
    upload_cols_present = False
    download_cols_present = False
    pcap_packets_present = False
    pcap_bytes_present = False
    pcap_cumulative_packets_present = False
    pcap_cumulative_bytes_present = False
    
    for sname, df in stats_files:
        if _is_godot_label(sname):
            godot_present = True
        # Check for network columns by metric family.
        if "RTT (ms) - Calculated from RPC" in df.columns:
            rtt_rpc_cols_present = True
        if any(col in df.columns for col in ["RTT (ms)", "RTT_ms", "Ping_ms", "Ping (ns)"]):
            rtt_cols_present = True
        if any(col in df.columns for col in ["Upload (bytes/sec)", "NetOutBytesPerSec"]):
            upload_cols_present = True
        if any(col in df.columns for col in ["Download (bytes/sec)", "NetInBytesPerSec"]):
            download_cols_present = True
        if any(col in df.columns for col in ["PacketsPerSec", "Packets"]):
            pcap_packets_present = True
        if any(col in df.columns for col in ["BytesPerSec", "Bytes", "BitsPerSec"]):
            pcap_bytes_present = True
        if "CumulativePackets" in df.columns:
            pcap_cumulative_packets_present = True
        if any(col in df.columns for col in ["CumulativeBytes", "CumulativeBits"]):
            pcap_cumulative_bytes_present = True
        
        # Check for performance metrics (always available if we have stats files)
        if any(col in df.columns for col in ["FPS", "average_frame_rate", "FrameTimeMs"]):
            available.add("FPS")
        if any(col in df.columns for col in ["Total Used Memory (bytes)", "app_rss_MB", "app_pss_MB", "app_uss_MB"]):
            available.add("Memory (MB)")
        if any(col in df.columns for col in ["CPU Total Frame Time (ns)", "CPU Main Thread Frame Time (ns)", 
                                              "Main Thread (ns)", "FrameTimeMs", "cpu_utilization_percentage"]):
            available.add("CPU (ms)")
        if any(col in df.columns for col in ["GPU Frame Time (ns)", "app_gpu_time_microseconds"]):
            available.add("GPU (ms)")

    
    # Add network metrics only if the relevant columns exist.
    if rtt_rpc_cols_present:
        available.add("Network - RTT (ms) - Calculated from RPC")
    if rtt_cols_present:
        available.add("Network - RTT (ms)")
    if upload_cols_present:
        available.add("Network - Upload (bytes/sec)")
    if download_cols_present:
        available.add("Network - Download (bytes/sec)")
    if pcap_packets_present:
        available.add("PCAP - Packets/sec")
    if pcap_bytes_present:
        available.add("PCAP - Bytes/sec")
    if pcap_cumulative_packets_present:
        available.add("PCAP - Cumulative Packets")
    if pcap_cumulative_bytes_present:
        available.add("PCAP - Cumulative Bytes")
    
    return [label for label in metric_options.keys() if label in available]

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
line_filter_candidates = set()
for metric_key in selected_metric_keys:
    metric_label = [k for k, v in metric_options.items() if v == metric_key][0]
    preview_datasets, _ = build_datasets(
        stats_files=stats_files,
        events_files=events_files,
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
    line_filter_candidates.update([label for label, _ in preview_datasets])

# Collapse duplicates that share a capture timestamp: when several CSVs
# (events, profiler_stats, Android trace) map to the same display name,
# keep only the canonical "stats" file so the dropdown exposes one entry
# per capture run and avoids confusing "(events)" / "(stats)" siblings.
_TYPE_PRIORITY = {"stats": 0, "pcap": 1, "events": 2, "trace": 3, "": 4}


def _pick_canonical(siblings: list[str]) -> str:
    """Return the canonical label for a group of siblings sharing a display name."""
    return sorted(
        siblings,
        key=lambda lbl: (
            _TYPE_PRIORITY.get(_type_tag_for(lbl), 99),
            _type_tag_for(lbl),
            lbl,
        ),
    )[0]


def _dedupe_candidates(candidates: set[str]) -> list[str]:
    groups: dict[str, list[str]] = {}
    for label in candidates:
        base = short_label(label)
        groups.setdefault(base, []).append(label)
    deduped = []
    for base, siblings in groups.items():
        if len(siblings) == 1:
            deduped.append(siblings[0])
            continue
        deduped.append(_pick_canonical(siblings))
    return sorted(deduped)


def _collapse_datasets(datasets: list[tuple[str, pd.DataFrame]]) -> list[tuple[str, pd.DataFrame]]:
    """Reduce a list of (label, df) pairs to one entry per short_label().

    Keeps the same canonical label as `_dedupe_candidates` so the legend
    matches the line-filter dropdown exactly.
    """
    groups: dict[str, list[tuple[str, pd.DataFrame]]] = {}
    for entry in datasets:
        base = short_label(entry[0])
        groups.setdefault(base, []).append(entry)
    collapsed: list[tuple[str, pd.DataFrame]] = []
    for base, siblings in groups.items():
        if len(siblings) == 1:
            collapsed.append(siblings[0])
            continue
        canonical = _pick_canonical([lbl for lbl, _ in siblings])
        for lbl, df in siblings:
            if lbl == canonical:
                collapsed.append((lbl, df))
                break
    return collapsed


def _dedupe_candidates_by_group(candidates: set[str]) -> list[str]:
    """One representative raw label per (platform, subsystem, role) group.

    Used for the Line Filter dropdown in aggregated mode: once runs get
    averaged into a single line per group, listing every individual run
    (each with its own timestamp) just floods the dropdown with entries
    that all collapse into the same plotted line anyway. Picking one
    canonical representative per group keeps the options list matching
    what's actually going to be drawn -- one entry per averaged line.
    """
    groups: dict[tuple[str, str, str], list[str]] = {}
    for label in candidates:
        groups.setdefault(_run_group_key(label), []).append(label)
    representatives = [
        _pick_canonical(siblings) if len(siblings) > 1 else siblings[0]
        for siblings in groups.values()
    ]
    return sorted(representatives, key=lambda lbl: _group_key_to_display(_run_group_key(lbl)))


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
_NETWORK_TOKENS = ("photon", "fishnet", "ngo", "netcodeentities", "server", "client", "pcap", "capture")


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

# Import required plotting utilities
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def create_network_plot(net_datasets, selected_labels, per_gameobject, xcol, log_scale=False):
    """Create the network subplots figure."""
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=("RTT (ms)", "Upload (bytes/sec)", "Download (bytes/sec)"),
        shared_xaxes=True,
        vertical_spacing=0.1
    )
    
    colors = px.colors.qualitative.Plotly
    
    for i, label in enumerate(selected_labels):
        color = colors[i % len(colors)]
        
        # RTT
        if "network_rtt" in net_datasets:
            series_list = [d for d in net_datasets["network_rtt"] if d[0] == label]
            if series_list:
                df = series_list[0][1].copy()
                y_col = df["_ycol"].iloc[0]
                df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
                df = df.dropna(subset=[y_col])
                if log_scale:
                    df = df[df[y_col] > 0]
                if not df.empty:
                    fig.add_trace(go.Scatter(x=df[xcol], y=df[y_col], line=dict(color=color), name=f"{label} RTT", legendgroup=label), row=1, col=1)
        
        # Upload / Download
        for k, l_suffix, l_dash, row in [
            ("network_upload", "Upload", "solid", 2),
            ("network_download", "Download", "dash", 3),
        ]:
            if k in net_datasets:
                series_list = [d for d in net_datasets[k] if d[0] == label]

                if series_list:
                    df = series_list[0][1].copy()
                    y_col = df["_ycol"].iloc[0]
                    df[y_col] = pd.to_numeric(df[y_col], errors="coerce")
                    df = df.dropna(subset=[y_col])
                    if log_scale:
                        df = df[df[y_col] > 0]
                    if not df.empty:
                        fig.add_trace(go.Scatter(x=df[xcol], y=df[y_col], line=dict(color=color, dash=l_dash), name=f"{label} {l_suffix}", legendgroup=label), row=row, col=1)
        
    fig.update_layout(height=600, showlegend=True)
    fig.update_yaxes(title_text="RTT (ms)", row=1, col=1)
    fig.update_yaxes(title_text="Upload (bytes/sec)", row=2, col=1)
    fig.update_yaxes(title_text="Download (bytes/sec)", row=3, col=1)
    if log_scale:
        fig.update_yaxes(type="log", row=1, col=1)
        fig.update_yaxes(type="log", row=2, col=1)
        fig.update_yaxes(type="log", row=3, col=1)
    fig.update_xaxes(title_text=xcol, row=3, col=1)
    return fig


def _drop_truncated_gameobject_runs(entries, x_col_group, min_coverage=0.4, min_points=3):
    """Drop per-run per-GameObject series whose captured range is much
    shorter than its sibling runs' in the same average group.

    A Quest on-device trace that stops recording after a few seconds
    instead of covering the full multi-minute benchmark only yields a
    handful of early, still-healthy FPS samples pinned to GameObjects
    values that don't line up with the other runs' milestone grid (their
    FinishedInstantiation events keep firing off-camera while the trace
    isn't recording anymore). Averaging that alongside complete runs
    turns a smooth trend into a jagged sawtooth: at some GameObjects
    values only the complete runs contribute (showing the real decline),
    while immediately next to them a lone truncated-run sample sits at
    ~72 FPS, and the line connecting the two looks like a crash-and-recover
    cycle that never happened. Filtering on point count (rather than max
    GameObjects reached) is deliberate: a truncated run can still report a
    numerically high "GameObjects" value if its events counter kept
    incrementing quickly, but it will always have far fewer recorded
    per-GameObject segments than a run that stayed alive for the whole
    benchmark.
    """
    if x_col_group != "GameObjects" or len(entries) <= 2:
        return entries
    counts = sorted(len(df) for _, df in entries)
    mid = len(counts) // 2
    median_count = counts[mid] if len(counts) % 2 else (counts[mid - 1] + counts[mid]) / 2
    if median_count < min_points:
        return entries
    kept = [(label, df) for label, df in entries if len(df) >= median_count * min_coverage]
    return kept if kept else entries


def create_standard_plot(datasets, selected_labels, metric_label, metric_key, per_gameobject, xcol, log_scale=False, average_runs=False):
    """Create a standard line plot for non-network metrics."""
    combined = []
    plot_ycol = None
    run_groups = {}  # (platform, subsystem, role) -> [(raw_label, temp_df), ...]

    # No movement-phase-specific trimming; keep series as-is

    for label, df in datasets:
        if label not in selected_labels:
            continue
        temp = df.copy()
        if temp.empty:
            continue
        if plot_ycol is None and "_ycol" in temp.columns:
            plot_ycol = temp["_ycol"].iloc[0]
        if average_runs:
            run_groups.setdefault(_run_group_key(label), []).append((label, temp))
        else:
            temp["label"] = short_label(label, [lbl for lbl, _ in datasets])
            combined.append(temp)

    if average_runs:
        for (platform, subsystem, role), entries in run_groups.items():
            # A group with only one contributing run has nothing to
            # average -- plot it exactly like the non-averaged path.
            if len(entries) > 1:
                sample_df = entries[0][1]
                ycol_group = sample_df["_ycol"].iloc[0] if "_ycol" in sample_df.columns else plot_ycol
                x_col_group = "GameObjects" if "GameObjects" in sample_df.columns else xcol
                if ycol_group is not None and x_col_group in sample_df.columns:
                    kept_entries = _drop_truncated_gameobject_runs(entries, x_col_group)
                    avg_df = average_series_across_runs(
                        [d for _, d in kept_entries], x_col=x_col_group, y_col=ycol_group
                    )
                    if not avg_df.empty:
                        role_suffix = f" {role}" if role else ""
                        avg_df = avg_df.rename(columns={"mean": ycol_group})
                        avg_df["label"] = f"{platform} · {subsystem}{role_suffix} (avg of {len(kept_entries)} runs)"
                        avg_df["_ycol"] = ycol_group
                        combined.append(avg_df[[x_col_group, ycol_group, "label", "_ycol"]])
                        continue
                # Couldn't determine a common x/y column for this group;
                # fall back to plotting each run separately below.
            for run_label, run_df in entries:
                run_df["label"] = short_label(run_label, [lbl for lbl, _ in datasets])
                combined.append(run_df)

    if not combined:
        return None
    def _uniform_time_bins(frame: pd.DataFrame, x_column: str, y_column: str, target_points: int = 120):
        if x_column != "Time" or len(frame) <= target_points:
            return frame

        # Safety check: if y_column doesn't exist, try to find it from _ycol metadata
        if y_column not in frame.columns:
            if "_ycol" in frame.columns and len(frame) > 0:
                y_column = frame["_ycol"].iloc[0]
            else:
                # No valid metric column found, return frame unchanged
                return frame

        cols_to_keep = [x_column, y_column, "label"]
        if "_ycol" in frame.columns:
            cols_to_keep.append("_ycol")
        uniform = frame[cols_to_keep].copy()
        uniform[x_column] = pd.to_numeric(uniform[x_column], errors="coerce")
        uniform[y_column] = pd.to_numeric(uniform[y_column], errors="coerce")
        uniform = uniform.dropna(subset=[x_column, y_column]).sort_values(x_column)
        if uniform.empty:
            return frame

        x_min = float(uniform[x_column].min())
        x_max = float(uniform[x_column].max())
        if x_max <= x_min:
            return uniform

        bin_width = max((x_max - x_min) / target_points, 0.5)
        uniform["_bin"] = ((uniform[x_column] - x_min) / bin_width).floordiv(1).astype(int)
        agg_dict = {x_column: "mean", y_column: "mean"}
        if "_ycol" in uniform.columns:
            agg_dict["_ycol"] = "first"
        uniform = uniform.groupby(["label", "_bin"], as_index=False).agg(agg_dict)
        return uniform.sort_values(x_column).reset_index(drop=True)
    
    # keep combined as-is; no movement-phase resampling

    if not combined:
        return None

    all_df = pd.concat(combined, ignore_index=True)
    
    # Normalize y-column names: if Quest and PC have different column names for the same metric,
    # rename Quest's column to match PC's (e.g., "CPU Utilization (%)" -> "CPU (ms)")
    # This allows both platforms to render on the same plot
    if "_ycol" in all_df.columns:
        # Get all unique y-column names used in this dataset
        unique_ycols = set(all_df["_ycol"].dropna().unique())
        # If there are multiple column names for the same metric, pick the first one and rename all to it
        if len(unique_ycols) > 1:
            canonical_ycol = list(unique_ycols)[0]
            for alt_ycol in unique_ycols:
                if alt_ycol in all_df.columns and alt_ycol != canonical_ycol:
                    # Rename the alternative column to the canonical name
                    all_df[canonical_ycol] = all_df[canonical_ycol].fillna(all_df[alt_ycol])
                    all_df = all_df.drop(columns=[alt_ycol], errors="ignore")
            ycol = canonical_ycol
        else:
            ycol = plot_ycol if plot_ycol is not None else "FPS"
    else:
        ycol = plot_ycol if plot_ycol is not None else "FPS"
    
    all_df = all_df.drop(columns=["_ycol"], errors="ignore")
    
    plot_xcol = xcol if xcol in all_df.columns else ("GameObjects" if "GameObjects" in all_df.columns else ("Frame" if "Frame" in all_df.columns else xcol))

    # If log scale requested, remove non-positive values for the plot y-column
    all_df[ycol] = pd.to_numeric(all_df[ycol], errors="coerce")
    all_df = all_df.dropna(subset=[ycol])
    if log_scale:
        all_df = all_df[all_df[ycol] > 0]

    fig = px.line(all_df, x=plot_xcol, y=ycol, color="label", markers=True)
    
    if metric_key == "fps":
        fig.add_hline(
            y=72,
            line_dash="dash",
            line_color="gray",
            annotation_text="72 FPS",
            annotation_position="top left",
        )
    elif metric_key in ("cpu", "gpu"):
        # 1000 ms / 72 FPS ≈ 13.89 ms — the frame-time budget required to
        # sustain a 72 FPS refresh rate (Quest 3 / Pico 4 default).
        fig.add_hline(
            y=14,
            line_dash="dash",
            line_color="gray",
            annotation_text="14 ms (~72 FPS budget)",
            annotation_position="top left",
        )
    
    phase_suffix = ""
    # Use the actual y-column name for the y-axis label (in case Quest/PC differ)
    y_axis_label = metric_label if metric_key.startswith("godot_") else (ycol if ycol not in ("FPS", metric_label) else metric_label)
    figure_title = f"{metric_label}{phase_suffix} per GameObject pool" if per_gameobject and plot_xcol == "GameObjects" else f"{metric_label}{phase_suffix} vs {plot_xcol}"
    fig.update_layout(title=figure_title, xaxis_title=plot_xcol, yaxis_title=y_axis_label, height=600)
    if log_scale:
        fig.update_yaxes(type="log")
    return fig


def _capture_timestamp_key(label: str) -> str | None:
    """Return the capture timestamp used to group files from the same run.

    This is the same normalized YYYYMMDD_HHMM value produced by
    `normalize_timestamp`. Note that for the same Unity capture run, the
    Android trace file (`com.IMT_Atlantique.*#UnityPlayerGameActivity-*.csv`)
    and the corresponding stats file (`*_profiler_stats-*.csv`) often
    start within a minute or two of each other, so a strict equality
    match on this key is too narrow. Callers should use
    `_capture_date_key` when they want to allow that tolerance.
    """
    ts, _ = extract_timestamp(label)
    if not ts:
        return None
    return normalize_timestamp(ts)


def _capture_date_key(label: str) -> str | None:
    """Return the capture date (YYYYMMDD) for grouping files from the
    same Unity session. Android trace files and stats files from the same
    run usually share this date but can be minutes apart, so this key
    is broader than `_capture_timestamp_key`.
    """
    key = _capture_timestamp_key(label)
    if not key or len(key) < 8:
        return None
    return key[:8]


def _label_has_server_role(label: str) -> bool:
    """Return True when the label explicitly identifies a server-side role.

    Used to prevent the same-capture-date expansion from leaking server
    captures into a client-only filter: a Photon *client* selection on
    `20260605` must not pull in the Photon *server* capture that happens
    to share the same Unity capture date.
    """
    if _is_quest_routed_capture(label):
        # Its "_server_capture_" token describes traffic direction, not
        # an actual server role -- see _run_group_key/_is_quest_routed_capture.
        return False
    lowered = label.lower()
    return (
        "_server_" in lowered
        or "_server_events_" in lowered
        or "_server_profiler_" in lowered
        or "_server_capture_" in lowered
    )


def _expand_filter_labels(
    selected: set[str],
    candidates: list[str],
    datasets_labels: list[str],
) -> set[str]:
    """Expand each selected dropdown label to every related file in `datasets`.

    Two expansion rules are tried, in order:
    1. Same `short_label()` — covers cases where sibling files were
       kept alongside the canonical entry (e.g. PCAP stats vs trace
       with identical display names).
    2. Same capture date (YYYYMMDD) — covers cases where the trace
       file's display name differs from the stats file (no
       Client/Server suffix, different sub-minute timestamp) but the
       files belong to the same Unity capture session.

    Rule 2 is gated by role safety: a candidate that explicitly carries
    a server-side role token (`_server_`, `_server_events_`,
    `_server_profiler_`, `_server_capture_`) is never pulled in by a
    selection whose `short_label()` is client-side, even when the
    capture dates match. This avoids the "Client only" plot leaking in
    Fishnet / NetcodeEntities / NGO / Photon server traces from the
    same Unity session, which share the same capture timestamp family
    (`_capture_timestamp_key` collapses seconds to minutes).
    """
    expanded: set[str] = set()
    for label in selected:
        expanded.add(label)
        base = short_label(label)
        selection_is_client = _is_client_label(label)
        selection_type = _type_tag_for(label)
        cap_ts = _capture_timestamp_key(label)
        cap_date = cap_ts[:8] if cap_ts else None
        for candidate in candidates:
            if candidate == label or candidate in expanded:
                continue
            if short_label(candidate) == base:
                expanded.add(candidate)
                continue
            if cap_date:
                cand_date = _capture_date_key(candidate)
                if cand_date != cap_date:
                    continue
                candidate_type = _type_tag_for(candidate)
                # Only use same-date expansion to bridge the intended stats/trace
                # sibling case. Without this guard, choosing a PC Base line filter
                # also pulls in unrelated DOTS/GPU stat files that happen to share
                # the same capture date.
                if {selection_type, candidate_type} != {"stats", "trace"}:
                    continue
                # Same-date expansion: refuse to bring in any capture
                # that is explicitly labelled as a server-side role when
                # the user is filtering on a client selection. This is
                # the role-gating guarantee promised by the docstring.
                if selection_is_client and _label_has_server_role(candidate):
                    continue
                expanded.add(candidate)
    return expanded


def build_metric_figures(per_gameobject_override=None, x_axis_mode="frame", log_scale=False):
    metric_figures = {}
    skipped_by_filter = []
    for metric_key in selected_metric_keys:
        metric_label = [k for k, v in metric_options.items() if v == metric_key][0]
        use_per_gameobject = per_gameobject if per_gameobject_override is None else per_gameobject_override
        use_average_runs = average_runs and use_per_gameobject
        datasets, _ = build_datasets(
            stats_files=stats_files,
            events_files=events_files,
            user_pairings=user_pairings,
            selected_metric_key=metric_key,
            selected_metric_label=metric_label,
            per_gameobject=use_per_gameobject,
            x_axis_mode=x_axis_mode,
            include_unpaired=include_unpaired,
        )

        if metric_key.startswith(("network_", "pcap_")) and datasets:
            datasets = [
                (label, df)
                for label, df in datasets
                if _is_networked_tech_label(label)
            ]

        # Filter out non-com.IMT_Atlantique Quest files for standard metrics (FPS, Memory, CPU, GPU).
        # We want to use ONLY com.IMT_Atlantique files for these specific metrics on Quest, as requested.
        # However, we also need to include godot-quest data in the plots like godot-pc ones.
        if metric_key in STANDARD_METRIC_KEYS and datasets:
            datasets = [
                (label, df) for label, df in datasets
                if _keep_for_quest_standard_metric(label)
            ]

        if datasets:
            # Collapse datasets by short_label() so the legend stays
            # consistent with the line-filter dropdown (one entry per
            # capture run, no duplicate "(stats)" / "(trace)" siblings).
            datasets = _collapse_datasets(datasets)
            labels = [t[0] for t in datasets]
            if active_line_filters:
                if use_average_runs:
                    # Aggregated mode: the dropdown holds one
                    # representative label per (platform, subsystem,
                    # role) group (see _dedupe_candidates_by_group), so
                    # expand each selection to every run sharing that
                    # exact group key -- the same grouping
                    # create_standard_plot uses to build the averaged
                    # line, so the filter and the plot always agree.
                    wanted_keys = {_run_group_key(sel) for sel in active_line_filters}
                    labels = [
                        label for label in labels
                        if _run_group_key(label) in wanted_keys
                    ]
                else:
                    # Per-run mode: expand each selected dropdown label
                    # back to every sibling file that shares the same
                    # short_label() (or the same capture timestamp when
                    # display names diverge between stats and trace
                    # files).
                    expanded = _expand_filter_labels(
                        active_line_filters,
                        list(line_filter_candidates),
                        labels,
                    )
                    labels = [label for label in labels if label in expanded]
            if not labels:
                skipped_by_filter.append(metric_label)
                continue
            fig = create_standard_plot(
                datasets,
                labels,
                metric_label,
                metric_key,
                use_per_gameobject,
                "GameObjects" if use_per_gameobject else ("Time" if x_axis_mode == "time" else "Frame"),
                log_scale=log_scale,
                average_runs=use_average_runs,
            )
            if fig:
                metric_figures[metric_label] = fig

    return metric_figures, skipped_by_filter


def render_dashboard(metric_figures, title, skipped_by_filter=None):
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


# Generate and display the full dashboard
metric_figures, skipped_by_filter = build_metric_figures()
render_dashboard(metric_figures, "Metrics Dashboard", skipped_by_filter=skipped_by_filter)

# Generate and display the movement-phase dashboard below the main one
# movement-phase dashboard removed (data changed; movement phase logic deprecated)
