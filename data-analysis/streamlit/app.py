import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys

from data_loader import (
    auto_pair_files,
    extract_timestamp,
    get_pc_and_quest_folders,
    load_csv_files_from_folder,
    normalize_timestamp,
)
from metrics_engine import build_datasets

# allow importing project helpers (assemble.py)
sys.path.append(str(Path(__file__).resolve().parents[1]))
try:
    import assemble
except Exception:
    assemble = None

st.set_page_config(page_title="Benchmark Metrics Viewer", layout="wide")

st.title("Benchmark Metrics Viewer")
st.markdown("Load PC and/or Quest benchmark data. Choose a metric (FPS, Memory, CPU, GPU) and the app will plot either per-frame or per-GameObject series.")

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
user_pairings, pairing_debug = auto_pair_files(stats_files, events_files)
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

per_gameobject = st.checkbox("Aggregate per GameObject using events (FinishedInstantiation)", value=True)
norm_option = st.checkbox("Normalize metric to first sample (per series)", value=False)

# Show pairing UI if per-GameObject is enabled
if per_gameobject and stats_files and events_files:
    st.subheader("Match stat files to event files")
    
    event_names = ["(none)"] + [name for name, _ in events_files]
    
    with st.expander("File pairings (auto-paired by timestamp)", expanded=False):
        for sname, _ in stats_files:
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
            else:
                user_pairings[sname] = None

# Metric selection belongs right before plotting so matching comes first.
metric_options = {
    "FPS": "fps",
    "Memory (MB)": "memory",
    "CPU (ms)": "cpu",
    "GPU (ms)": "gpu",
}
selected_metric_label = st.selectbox("Metric", list(metric_options.keys()), index=0)
selected_metric_key = metric_options[selected_metric_label]

datasets, metric_warnings = build_datasets(
    stats_files=stats_files,
    events_files=events_files,
    user_pairings=user_pairings,
    selected_metric_key=selected_metric_key,
    selected_metric_label=selected_metric_label,
    per_gameobject=per_gameobject,
)

for warning in metric_warnings:
    st.warning(warning)

if not datasets:
    st.info("No compatible datasets found after parsing.")
else:
    labels = [t[0] for t in datasets]
    selected = st.multiselect("Select series to show", labels, default=labels)

    combined = []
    plot_ycol = None
    for label, df in datasets:
        if label not in selected:
            continue
        temp = df.copy()
        if norm_option:
            ycol = temp["_ycol"].iloc[0]
            if not temp[ycol].empty:
                first = pd.to_numeric(temp[ycol].iloc[0], errors="coerce")
                if pd.notna(first) and first != 0:
                    temp[ycol] = temp[ycol] / first
        if plot_ycol is None:
            plot_ycol = temp["_ycol"].iloc[0]
        temp["label"] = label
        combined.append(temp)

    if combined:
        all_df = pd.concat(combined, ignore_index=True)
        all_df = all_df.drop(columns=["_ycol"], errors="ignore")
        # choose axes depending on whether per-GameObject was used
        if per_gameobject:
            xcol = "GameObjects"
        else:
            xcol = "Frame"

        ycol = plot_ycol if plot_ycol is not None else "FPS"

        fig = px.line(all_df, x=xcol, y=ycol, color="label", markers=True)
        if selected_metric_key == "fps" and not norm_option:
            fig.add_hline(
                y=72,
                line_dash="dash",
                line_color="gray",
                annotation_text="72 FPS",
                annotation_position="top left",
            )
        figure_title = f"{selected_metric_label} per GameObject" if per_gameobject else f"{selected_metric_label} vs Frame"
        yaxis_title = f"Normalized {selected_metric_label}" if norm_option else selected_metric_label
        fig.update_layout(title=figure_title, xaxis_title=xcol, yaxis_title=yaxis_title, legend_title="Series")
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No series selected.")
