import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys
import os

# allow importing project helpers (assemble.py)
sys.path.append(str(Path(__file__).resolve().parents[1]))
try:
    import assemble
except Exception:
    assemble = None

st.set_page_config(page_title="Benchmark Metrics Viewer", layout="wide")

st.title("Benchmark Metrics Viewer")
st.markdown("Upload one or more CSV profiler/stat files. Choose a metric (FPS, Memory, CPU, GPU) and the app will plot either per-frame or per-GameObject series.")

# Initialize session state for pairings
if "pairings_state" not in st.session_state:
    st.session_state.pairings_state = {}

uploaded = st.file_uploader("Upload CSV files", type=["csv"], accept_multiple_files=True)
auto_load = st.checkbox("Auto-load latest data folder (./data)", value=True)


def detect_columns(df: pd.DataFrame):
    frame_col = None
    for c in ("Frame", "Time Stamp", "Time"):
        if c in df.columns:
            frame_col = c
            break
    fps_col = None
    for c in ("FPS", "average_frame_rate"):
        if c in df.columns:
            fps_col = c
            break
    return frame_col, fps_col


def _fps_series_from_stats(df: pd.DataFrame):
    frame_column = None
    if "Frame" in df.columns:
        frame_column = "Frame"
    elif "Time Stamp" in df.columns:
        frame_column = "Time Stamp"
    elif "Time" in df.columns:
        frame_column = "Time"
    else:
        return None

    fps_column = None
    if "FPS" in df.columns:
        fps_column = "FPS"
    elif "average_frame_rate" in df.columns:
        fps_column = "average_frame_rate"
    else:
        return None

    plot_data = df[[frame_column, fps_column]].copy()
    plot_data.columns = ["Frame", "FPS"]
    plot_data["Frame"] = pd.to_numeric(plot_data["Frame"], errors="coerce")
    plot_data["FPS"] = pd.to_numeric(plot_data["FPS"], errors="coerce")
    return plot_data.dropna(subset=["Frame", "FPS"]).reset_index(drop=True)


def _frame_series(df: pd.DataFrame):
    if "Frame" in df.columns:
        return pd.to_numeric(df["Frame"], errors="coerce")
    if "Time Stamp" in df.columns:
        return pd.to_numeric(df["Time Stamp"], errors="coerce")
    if "Time" in df.columns:
        return pd.to_numeric(df["Time"], errors="coerce")
    return None


def _memory_series_from_stats(df: pd.DataFrame):
    frame = _frame_series(df)
    if frame is None:
        return None

    if "Total Used Memory (bytes)" in df.columns:
        memory_mb = pd.to_numeric(df["Total Used Memory (bytes)"], errors="coerce") / (1024.0 * 1024.0)
    elif "app_rss_MB" in df.columns:
        memory_mb = pd.to_numeric(df["app_rss_MB"], errors="coerce")
    elif "app_pss_MB" in df.columns:
        memory_mb = pd.to_numeric(df["app_pss_MB"], errors="coerce")
    elif "app_uss_MB" in df.columns:
        memory_mb = pd.to_numeric(df["app_uss_MB"], errors="coerce")
    else:
        return None

    plot_data = pd.DataFrame({"Frame": frame, "MemoryMB": memory_mb})
    return plot_data.dropna(subset=["Frame", "MemoryMB"]).reset_index(drop=True)


def _metric_series_from_stats(df: pd.DataFrame, metric_key: str):
    if metric_key == "fps":
        return _fps_series_from_stats(df), "FPS"

    if metric_key == "memory":
        return _memory_series_from_stats(df), "MemoryMB"

    frame = _frame_series(df)
    if frame is None:
        return None, None

    if metric_key == "cpu":
        candidates = [
            ("CPU Total Frame Time (ns)", 1_000_000.0),
            ("CPU Main Thread Frame Time (ns)", 1_000_000.0),
            ("Main Thread (ns)", 1_000_000.0),
            ("FrameTimeMs", 1.0),
        ]
        out_col = "CPU (ms)"
    elif metric_key == "gpu":
        candidates = [
            ("GPU Frame Time (ns)", 1_000_000.0),
            ("app_gpu_time_microseconds", 1000.0),
        ]
        out_col = "GPU (ms)"
    else:
        return None, None

    metric_series = None
    for col, divisor in candidates:
        if col not in df.columns:
            continue
        candidate = pd.to_numeric(df[col], errors="coerce")
        if candidate.isna().all():
            continue
        metric_series = candidate / divisor
        break

    if metric_series is None:
        return None, None

    plot_data = pd.DataFrame({"Frame": frame, out_col: metric_series})
    return plot_data.dropna(subset=["Frame", out_col]).reset_index(drop=True), out_col


def _extract_finished_rows(events_df: pd.DataFrame):
    events = events_df.copy()
    if "Frame" not in events.columns and "Time" in events.columns:
        events["Frame"] = pd.to_numeric(events["Time"], errors="coerce") * 1000.0

    if not {"Frame", "Event", "Value"}.issubset(events.columns):
        return None

    finished_rows = events.loc[events["Event"] == "FinishedInstantiation", ["Frame", "Value"]].copy()
    finished_rows["Frame"] = pd.to_numeric(finished_rows["Frame"], errors="coerce")
    finished_rows["Value"] = pd.to_numeric(finished_rows["Value"], errors="coerce")
    return finished_rows.dropna().sort_values("Frame").reset_index(drop=True)


def _metric_per_gameobject_series(stats_df: pd.DataFrame, events_df: pd.DataFrame, metric_key: str):
    plot_data, metric_col = _metric_series_from_stats(stats_df, metric_key)
    if plot_data is None or metric_col is None:
        return None, None

    finished_rows = _extract_finished_rows(events_df)
    if finished_rows is None or finished_rows.empty:
        return None, None

    segment_points = []

    first_frame = finished_rows.iloc[0]["Frame"]
    initial_segment = plot_data.loc[plot_data["Frame"] <= first_frame, metric_col]
    if not initial_segment.empty:
        segment_points.append((0, initial_segment.iloc[-1]))

    previous_frame = None
    for _, row in finished_rows.iterrows():
        current_frame = row["Frame"]
        current_value = row["Value"]

        if previous_frame is None:
            segment = plot_data.loc[plot_data["Frame"] <= current_frame, metric_col]
        else:
            segment = plot_data.loc[(plot_data["Frame"] > previous_frame) & (plot_data["Frame"] <= current_frame), metric_col]

        if not segment.empty:
            segment_points.append((current_value, segment.mean()))
        previous_frame = current_frame

    if not segment_points:
        return None, None

    out_col = f"Average{metric_col}"
    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", out_col])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data[out_col] = pd.to_numeric(segment_data[out_col], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", out_col]).reset_index(drop=True), out_col


import re


def _extract_timestamp(file_name: str):
    patterns = [r"\d{8}_\d{6}", r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}"]
    for p in patterns:
        m = re.search(p, file_name)
        if m:
            return m.group(0)
    return None


def _normalize_timestamp(ts: str):
    """Normalize timestamps to YYYYMMDD_HHMM format for comparison."""
    if not ts:
        return None
    # Convert 2026.05.07-10.29 to 20260507_1029
    if "." in ts and "-" in ts:
        parts = ts.replace(".", "").replace("-", "")
        return parts[:8] + "_" + parts[8:12]
    # Already in format YYYYMMDD_HHMM or similar
    return ts[:8] + "_" + ts[-4:]


stats_files = []
events_files = []

# If files were uploaded, prefer them; otherwise, optionally auto-load latest data folder
if uploaded:
    read_files = []
    for uploaded_file in uploaded:
        try:
            df = pd.read_csv(uploaded_file)
            read_files.append((uploaded_file.name, df))
        except Exception as e:
            st.error(f"Failed to read {uploaded_file.name}: {e}")

    for name, df in read_files:
        lower = name.lower()
        if "event" in lower or ("event" in df.columns) or {"Event", "Value", "Frame"}.issubset(set(df.columns)):
            events_files.append((name, df))
        else:
            fcol, fpscol = detect_columns(df)
            if fpscol is not None:
                stats_files.append((name, df))
            else:
                # ambiguous; treat as event by default
                events_files.append((name, df))
else:
    if auto_load:
        data_root = Path(__file__).resolve().parents[1] / "data"
        st.info(f"Auto-load: looking for data in {data_root}")
        if assemble is None:
            st.error("Auto-load requested but assemble helper not available.")
        else:
            latest = assemble.get_latest_folder(str(data_root))
            if latest is None:
                st.warning(f"No data subfolders found in {data_root}")
            else:
                st.success(f"Found latest data folder: {latest}")
                # Read all CSV files directly and classify by name/columns
                latest_path = Path(latest)
                csv_files = list(latest_path.glob("*.csv"))
                st.info(f"Found {len(csv_files)} CSV files in folder")
                
                for csv_file in csv_files:
                    try:
                        df = pd.read_csv(csv_file)
                        file_name = csv_file.name
                        lower_name = file_name.lower()
                        
                        # Classify by name and columns
                        if "event" in lower_name or "Event" in df.columns:
                            events_files.append((file_name, df))
                        else:
                            # Check if it has FPS columns
                            fcol, fpscol = detect_columns(df)
                            if fpscol is not None:
                                stats_files.append((file_name, df))
                    except Exception as e:
                        st.warning(f"Failed to read {csv_file.name}: {e}")

# Auto-pair stat and event files by timestamp
def auto_pair_files(stats_list, events_list):
    """Match stat files to event files by normalized timestamp; returns dict of stat_name -> event_name"""
    pairings = {}
    debug_info = []
    
    for sname, _ in stats_list:
        ts = _extract_timestamp(sname)
        norm_ts = _normalize_timestamp(ts) if ts else None
        match = None
        
        if norm_ts:
            for ename, _ in events_list:
                e_ts = _extract_timestamp(ename)
                norm_e_ts = _normalize_timestamp(e_ts) if e_ts else None
                # Compare normalized timestamps
                if norm_ts and norm_e_ts and norm_ts in norm_e_ts:
                    match = ename
                    debug_info.append(f"✓ Paired {sname[:30]}... with {ename[:30]}...")
                    break
        
        # Fallback: use first event if only one exists
        if match is None and len(events_list) == 1:
            match = events_list[0][0]
            debug_info.append(f"⚠ {sname[:30]}... → fallback to only event file")
        
        if match is None:
            debug_info.append(f"✗ No match for {sname[:30]}...")
        
        pairings[sname] = match
    
    # Store debug info in session state for display
    st.session_state.pairing_debug = debug_info
    
    return pairings

# Auto-pair files
user_pairings = auto_pair_files(stats_files, events_files)

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
                ts = _extract_timestamp(sname)
                norm_ts = _normalize_timestamp(ts) if ts else None
                st.write(f"  {sname} → raw: {ts}, normalized: {norm_ts}")
        if events_files:
            st.write("**Event files:**")
            for ename, _ in events_files:
                ts = _extract_timestamp(ename)
                norm_ts = _normalize_timestamp(ts) if ts else None
                st.write(f"  {ename} → raw: {ts}, normalized: {norm_ts}")

# Now proceed with parsing and aggregation options
metric_options = {
    "FPS": "fps",
    "Memory (MB)": "memory",
    "CPU (ms)": "cpu",
    "GPU (ms)": "gpu",
}
selected_metric_label = st.selectbox("Metric", list(metric_options.keys()), index=0)
selected_metric_key = metric_options[selected_metric_label]

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

datasets = []

# Helper to get event df by name from our loaded files
def get_event_df(event_name):
    for ename, edf in events_files:
        if ename == event_name:
            return edf
    return None

for sname, sdf in stats_files:
    label = Path(sname).stem
    if per_gameobject:
        # Use user-selected pairing if available
        selected_event_name = user_pairings.get(sname)
        if selected_event_name is None:
            st.warning(f"No event file selected for {sname}; falling back to per-frame-to-GameObject conversion for this file.")
            series, ycol = _metric_series_from_stats(sdf, selected_metric_key)
            if series is None or ycol is None:
                st.warning(f"Also could not parse {selected_metric_label} series from {sname}.")
                continue
            series = series.rename(columns={"Frame": "GameObjects", ycol: f"Average{ycol}"})
            ycol = f"Average{ycol}"
            series["label"] = label
            series["_ycol"] = ycol
            datasets.append((label, series))
        else:
            edf = get_event_df(selected_event_name)
            if edf is None:
                st.warning(f"Event file {selected_event_name} not found for {sname}.")
                continue
            series, ycol = _metric_per_gameobject_series(sdf, edf, selected_metric_key)
            if series is None or series.empty or ycol is None:
                st.warning(f"Per-GameObject aggregation failed for {sname} with {selected_event_name}; falling back to per-frame.")
                series, ycol = _metric_series_from_stats(sdf, selected_metric_key)
                if series is None or ycol is None:
                    st.warning(f"Also could not parse {selected_metric_label} series from {sname}.")
                    continue
                series = series.rename(columns={"Frame": "GameObjects", ycol: f"Average{ycol}"})
                ycol = f"Average{ycol}"
            series["label"] = label
            series["_ycol"] = ycol
            datasets.append((label, series))
    else:
        series, ycol = _metric_series_from_stats(sdf, selected_metric_key)
        if series is None or ycol is None:
            st.warning(f"Could not parse {selected_metric_label} series from {sname}.")
            continue
        series["label"] = label
        series["_ycol"] = ycol
        datasets.append((label, series))

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
        figure_title = f"{selected_metric_label} per GameObject" if per_gameobject else f"{selected_metric_label} vs Frame"
        yaxis_title = f"Normalized {selected_metric_label}" if norm_option else selected_metric_label
        fig.update_layout(title=figure_title, xaxis_title=xcol, yaxis_title=yaxis_title, legend_title="Series")
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Preview data for selected series"):
            st.dataframe(all_df.head(200))

    else:
        st.info("No series selected.")
