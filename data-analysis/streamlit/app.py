import streamlit as st
import pandas as pd
import plotly.express as px
import importlib
from pathlib import Path
from statistics import median
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from data_loader import (
    auto_pair_files,
    extract_timestamp,
    get_pc_and_quest_folders,
    load_csv_files_from_folder,
    normalize_timestamp,
)
from metrics_engine import build_datasets, metric_series_from_stats
import pcap_to_csv as pcap_tools

pcap_tools = importlib.reload(pcap_tools)
cleanup_pcap_folder_csv = pcap_tools.cleanup_pcap_folder_csv
convert_pcap_folder_to_csv = pcap_tools.convert_pcap_folder_to_csv


def _split_subsystem_label(label: str):
    if label.startswith("[PC] "):
        return "PC", label[5:]
    if label.startswith("[Quest] "):
        return "Quest", label[8:]
    return "Unknown", label

# allow importing project helpers (assemble.py)
try:
    import assemble
except Exception:
    assemble = None

st.set_page_config(page_title="Benchmark Metrics Viewer", layout="wide")

st.title("Benchmark Metrics Viewer")
st.markdown("Load PC and/or Quest benchmark data. Choose a metric (FPS, Memory, CPU, GPU, Network) and the app will plot either per-frame or per-GameObject series.")

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

if pc_folder:
    with st.expander("PC capture tools", expanded=False):
        pcap_bucket_seconds = st.number_input(
            "PCAP bucket size (seconds)",
            min_value=0.1,
            value=1.0,
            step=0.1,
        )
        overwrite_pcap_csv = st.checkbox("Overwrite existing pcap CSV outputs", value=False)
        convert_col, cleanup_col = st.columns(2)
        with convert_col:
            convert_pcaps = st.button("Convert every PC pcap to CSV")
        with cleanup_col:
            cleanup_pcaps = st.button("Delete generated PC pcap CSVs")

        if convert_pcaps:
            result = convert_pcap_folder_to_csv(
                pc_folder,
                bucket_seconds=float(pcap_bucket_seconds),
                overwrite=overwrite_pcap_csv,
            )
            converted = result["converted"]
            skipped = result["skipped"]
            warnings = result.get("warnings", [])
            errors = result["errors"]

            if converted:
                st.success(f"Converted {len(converted)} pcap file(s) to CSV.")
                for pcap_path, output_path, row_count in converted:
                    st.write(f"{pcap_path.name} -> {output_path.name} ({row_count} bucket(s))")
            if skipped:
                st.info(f"Skipped {len(skipped)} existing CSV file(s).")
            if warnings:
                for pcap_path, message in warnings:
                    st.warning(f"{pcap_path.name}: {message}")
            if errors:
                for pcap_path, message in errors:
                    st.warning(f"Failed to convert {pcap_path.name}: {message}")
            if not converted and not skipped and not errors:
                st.info("No pcap or pcapng files found in the PC folder.")

        if cleanup_pcaps:
            result = cleanup_pcap_folder_csv(pc_folder)
            deleted = result["deleted"]
            missing = result["missing"]
            errors = result["errors"]

            if deleted:
                st.success(f"Deleted {len(deleted)} generated CSV file(s).")
                for output_path in deleted:
                    st.write(output_path.name)
            if missing:
                st.info(f"{len(missing)} generated CSV file(s) were already missing.")
            if errors:
                for output_path, message in errors:
                    st.warning(f"Failed to delete {output_path.name}: {message}")
            if not deleted and not missing and not errors:
                st.info("No generated pcap CSV files found in the PC folder.")

# Selector for which data to load
st.subheader("Select Data to Load")
load_options = []
if pc_folder:
    load_options.append("PC")
if quest_folder:
    load_options.append("Quest")

if not load_options:
    st.error("No data folders found in ./data")
    st.stop()

selected_data = st.multiselect(
    "Choose which data to load:",
    options=load_options,
    default=load_options  # Select all by default
)

if not selected_data:
    st.warning("Please select at least one data source to load.")
    st.stop()

# Load the selected data
for data_type in selected_data:
    if data_type == "PC" and pc_folder:
        st.info(f"Loading PC data from: {pc_folder.name}")
        pc_stats, pc_events, pc_errors = load_csv_files_from_folder(pc_folder)
        for file_name, err in pc_errors:
            st.warning(f"Failed to read {file_name}: {err}")
        stats_files.extend([(f"[PC] {name}", df) for name, df in pc_stats])
        events_files.extend([(f"[PC] {name}", df) for name, df in pc_events])
    elif data_type == "Quest" and quest_folder:
        st.info(f"Loading Quest data from: {quest_folder.name}")
        quest_stats, quest_events, quest_errors = load_csv_files_from_folder(quest_folder)
        for file_name, err in quest_errors:
            st.warning(f"Failed to read {file_name}: {err}")
        stats_files.extend([(f"[Quest] {name}", df) for name, df in quest_stats])
        events_files.extend([(f"[Quest] {name}", df) for name, df in quest_events])

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
    "Network - RTT (ms) - Calculated from RPC": "network_rtt_rpc",
    "Network - RTT (ms)": "network_rtt",
    "Network - Upload (bytes/sec)": "network_upload",
    "Network - Download (bytes/sec)": "network_download",
}

# Detect which metrics are actually available in the loaded data
def get_available_metrics(stats_files, metric_options):
    """Scan loaded files and return only metrics that have data."""
    available = set()
    rtt_cols_present = False
    rtt_rpc_cols_present = False
    upload_cols_present = False
    download_cols_present = False
    pcap_packets_present = False
    pcap_bytes_present = False
    
    for _, df in stats_files:
        # Check for network columns by metric family.
        if "RTT (ms) - Calculated from RPC" in df.columns:
            rtt_rpc_cols_present = True
        if any(col in df.columns for col in ["RTT (ms)", "RTT_ms"]):
            rtt_cols_present = True
        if any(col in df.columns for col in ["Upload (bytes/sec)", "NetOutBytesPerSec"]):
            upload_cols_present = True
        if any(col in df.columns for col in ["Download (bytes/sec)", "NetInBytesPerSec"]):
            download_cols_present = True
        if any(col in df.columns for col in ["PacketsPerSec", "Packets"]):
            pcap_packets_present = True
        if any(col in df.columns for col in ["BytesPerSec", "Bytes", "BitsPerSec"]):
            pcap_bytes_present = True
        
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
    
    return [label for label in metric_options.keys() if label in available]

available_metrics = get_available_metrics(stats_files, metric_options)
unavailable_metrics = [m for m in metric_options.keys() if m not in available_metrics]

st.subheader("Select Metrics to Display")
col1, col2 = st.columns([3, 1])
with col1:
    selected_metrics = st.multiselect(
        "Choose metrics to display (empty = show all)",
        list(metric_options.keys()),
        default=["FPS"],
        disabled=False
    )
    if unavailable_metrics:
        st.info(f"Note: {', '.join(unavailable_metrics)} are not available in your data")
with col2:
    columns_count = st.selectbox("Columns", [1, 2, 3, 4], index=1)

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
    line_filter_candidates.update([label for label, _ in preview_datasets])

line_filter_options = sorted(line_filter_candidates)
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
    )
    st.session_state.line_filter_choices = selected_line_filters
with filter_col2:
    if st.button("Apply"):
        st.session_state.active_line_filters = list(st.session_state.line_filter_choices)
with filter_col3:
    if st.button("Clear"):
        st.session_state.active_line_filters = []
        st.session_state.line_filter_choices = []

active_line_filters = set(st.session_state.active_line_filters)
if active_line_filters:
    st.info(f"Line filter active: {len(active_line_filters)} selected")

# Import required plotting utilities
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def create_network_plot(net_datasets, selected_labels, per_gameobject, xcol):
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
                df = series_list[0][1]
                y_col = df["_ycol"].iloc[0]
                fig.add_trace(go.Scatter(x=df[xcol], y=df[y_col], line=dict(color=color), name=f"{label} RTT", legendgroup=label), row=1, col=1)
        
        # Upload / Download
        for k, l_suffix, l_dash, row in [
            ("network_upload", "Upload", "solid", 2),
            ("network_download", "Download", "dash", 3),
        ]:
            if k in net_datasets:
                series_list = [d for d in net_datasets[k] if d[0] == label]

                if series_list:
                    df = series_list[0][1]
                    y_col = df["_ycol"].iloc[0]
                    fig.add_trace(go.Scatter(x=df[xcol], y=df[y_col], line=dict(color=color, dash=l_dash), name=f"{label} {l_suffix}", legendgroup=label), row=row, col=1)
        
    fig.update_layout(height=600, showlegend=True)
    fig.update_yaxes(title_text="RTT (ms)", row=1, col=1)
    fig.update_yaxes(title_text="Upload (bytes/sec)", row=2, col=1)
    fig.update_yaxes(title_text="Download (bytes/sec)", row=3, col=1)
    fig.update_xaxes(title_text=xcol, row=3, col=1)
    return fig


def create_standard_plot(datasets, selected_labels, metric_label, metric_key, per_gameobject, xcol):
    """Create a standard line plot for non-network metrics."""
    combined = []
    plot_ycol = None

    # No movement-phase-specific trimming; keep series as-is
    
    for label, df in datasets:
        if label not in selected_labels:
            continue
        temp = df.copy()
        if temp.empty:
            continue
        if plot_ycol is None and "_ycol" in temp.columns:
            plot_ycol = temp["_ycol"].iloc[0]
        temp["label"] = label
        combined.append(temp)
    
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

    fig = px.line(all_df, x=plot_xcol, y=ycol, color="label", markers=True)
    
    if metric_key == "fps":
        fig.add_hline(
            y=72,
            line_dash="dash",
            line_color="gray",
            annotation_text="72 FPS",
            annotation_position="top left",
        )
    
    phase_suffix = ""
    # Use the actual y-column name for the y-axis label (in case Quest/PC differ)
    y_axis_label = ycol if ycol not in ("FPS", metric_label) else metric_label
    figure_title = f"{metric_label}{phase_suffix} per GameObject" if per_gameobject and plot_xcol == "GameObjects" else f"{metric_label}{phase_suffix} vs {plot_xcol}"
    fig.update_layout(title=figure_title, xaxis_title=plot_xcol, yaxis_title=y_axis_label, height=600)
    return fig


def build_metric_figures(per_gameobject_override=None, x_axis_mode="frame"):
    metric_figures = {}
    for metric_key in selected_metric_keys:
        metric_label = [k for k, v in metric_options.items() if v == metric_key][0]
        use_per_gameobject = per_gameobject if per_gameobject_override is None else per_gameobject_override
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

        if datasets:
            labels = [t[0] for t in datasets]
            if active_line_filters:
                labels = [label for label in labels if label in active_line_filters]
            if not labels:
                continue
            fig = create_standard_plot(
                datasets,
                labels,
                metric_label,
                metric_key,
                use_per_gameobject,
                "GameObjects" if use_per_gameobject else ("Time" if x_axis_mode == "time" else "Frame"),
            )
            if fig:
                metric_figures[metric_label] = fig

    return metric_figures


def render_dashboard(metric_figures, title):
    if not metric_figures:
        st.info(f"No compatible datasets found for {title.lower()}.")
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
                    st.plotly_chart(fig, use_container_width=True)


# Generate and display the full dashboard
metric_figures = build_metric_figures()
render_dashboard(metric_figures, "Metrics Dashboard")

# Generate and display the movement-phase dashboard below the main one
# movement-phase dashboard removed (data changed; movement phase logic deprecated)
