from typing import List, Tuple

import pandas as pd


def _has_network_columns(df: pd.DataFrame) -> bool:
    """Check if the DataFrame has any network-related columns."""
    network_cols = {
        "Ping (ns)", "Ping_ms",
        "Total Bytes Received (bytes)", "TotalBytesReceived",
        "Total Bytes Sent (bytes)", "TotalBytesSent",
        "Rpc Received", "PacketsIn",
        "Rpc Sent", "PacketsOut",
        "Object Spawned Bytes Received (bytes)",
        "Object Spawned Bytes Sent (bytes)",
        "Rpc Bytes Received (bytes)",
        "Rpc Bytes Sent (bytes)",
    }
    return any(col in df.columns for col in network_cols)


def _source_from_name(file_name: str):
    lower = file_name.lower()
    if lower.startswith("[pc]"):
        return "pc"
    if lower.startswith("[quest]"):
        return "quest"
    return None


def _frame_column_name(df: pd.DataFrame):
    for column in ("Frame", "Time Stamp", "Time"):
        if column in df.columns:
            return column
    return None


def _x_column_name(df: pd.DataFrame, x_axis_mode: str):
    if x_axis_mode == "time":
        for column in ("Time (s)", "Time", "Time Stamp", "Frame"):
            if column in df.columns:
                return column, "Time"
    frame_column = _frame_column_name(df)
    if frame_column is not None:
        return frame_column, "Frame"
    return None, None


def _format_label(file_name: str):
    """Format a stat filename as 'Source - BenchmarkType [Client/Server]' for legend display."""
    source = _source_from_name(file_name)
    if not source:
        return file_name.rsplit(".", 1)[0]
    source_label = source.upper()

    # Remove the [SOURCE] prefix to inspect the filename body
    body = file_name.lower()
    if body.startswith("[pc] "):
        body = body[5:]
    elif body.startswith("[quest] "):
        body = body[8:]

    # Extract benchmark type and client/server variant
    bench_type = "Unknown"
    variant = ""

    if "dots" in body:
        bench_type = "DOTS"
    elif "ngo" in body:
        bench_type = "NGO"
        if "ngo_client" in body:
            variant = " Client"
        elif "ngo_server" in body:
            variant = " Server"
    elif "photon" in body:
        bench_type = "Photon"
        if "photon_client" in body:
            variant = " Client"
        elif "photon_server" in body:
            variant = " Server"
    elif "benchmarkbase" in body:
        bench_type = "Base"
    elif "gpu" in body:
        bench_type = "GPU"
    elif "profiler_stats-" in body:
        bench_type = "Base"
    else:
        # Fallback: use the first meaningful word
        parts = body.split("_")
        bench_type = parts[0].title() if parts else "Unknown"

    return f"{source_label} - {bench_type}{variant}"


def _fps_series_from_stats(df: pd.DataFrame, stat_name: str | None = None, x_axis_mode: str = "frame"):
    x_column, output_column = _x_column_name(df, x_axis_mode)
    if x_column is None or output_column is None:
        return None

    fps_series = None
    # Prefer the reported average frame rate when it is available.
    if "average_frame_rate" in df.columns:
        fps_series = pd.to_numeric(df["average_frame_rate"], errors="coerce")
    elif "FPS" in df.columns:
        fps_series = pd.to_numeric(df["FPS"], errors="coerce")
    elif "FrameTimeMs" in df.columns:
        frame_time_ms = pd.to_numeric(df["FrameTimeMs"], errors="coerce")
        frame_time_ms = frame_time_ms.where(frame_time_ms > 0)
        fps_series = 1000.0 / frame_time_ms
    else:
        return None

    plot_data = df[[x_column]].copy()
    plot_data["FPS"] = fps_series
    plot_data.columns = [output_column, "FPS"]
    plot_data[output_column] = pd.to_numeric(plot_data[output_column], errors="coerce")
    plot_data["FPS"] = pd.to_numeric(plot_data["FPS"], errors="coerce")
    return plot_data.dropna(subset=[output_column, "FPS"]).reset_index(drop=True)


def _frame_series(df: pd.DataFrame, x_axis_mode: str = "frame"):
    x_column, _ = _x_column_name(df, x_axis_mode)
    if x_column is not None:
        return pd.to_numeric(df[x_column], errors="coerce")
    return None


def _memory_series_from_stats(df: pd.DataFrame, x_axis_mode: str = "frame"):
    frame = _frame_series(df, x_axis_mode)
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

    x_column = "Time" if x_axis_mode == "time" else "Frame"
    plot_data = pd.DataFrame({x_column: frame, "MemoryMB": memory_mb})
    return plot_data.dropna(subset=[x_column, "MemoryMB"]).reset_index(drop=True)


def metric_series_from_stats(df: pd.DataFrame, metric_key: str, stat_name: str | None = None, x_axis_mode: str = "frame"):
    if metric_key == "fps":
        return _fps_series_from_stats(df, stat_name, x_axis_mode), "FPS"

    if metric_key == "memory":
        return _memory_series_from_stats(df, x_axis_mode), "MemoryMB"

    frame = _frame_series(df, x_axis_mode)
    if frame is None:
        return None, None

    x_column = "Time" if x_axis_mode == "time" else "Frame"

    if metric_key == "network_ping":
        if not _has_network_columns(df):
            return None, None
        if "Ping (ns)" in df.columns:
            series = pd.to_numeric(df["Ping (ns)"], errors="coerce") / 1000000.0
        elif "Ping_ms" in df.columns:
            series = pd.to_numeric(df["Ping_ms"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Ping (ms)": series})
        return plot_data.dropna().reset_index(drop=True), "Ping (ms)"
        
    if metric_key == "network_bytes_recv":
        if not _has_network_columns(df):
            return None, None
        if "Total Bytes Received (bytes)" in df.columns:
            series = pd.to_numeric(df["Total Bytes Received (bytes)"], errors="coerce")
        elif "TotalBytesReceived" in df.columns:
            series = pd.to_numeric(df["TotalBytesReceived"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Bytes Received": series})
        return plot_data.dropna().reset_index(drop=True), "Bytes Received"

    if metric_key == "network_bytes_sent":
        if not _has_network_columns(df):
            return None, None
        if "Total Bytes Sent (bytes)" in df.columns:
            series = pd.to_numeric(df["Total Bytes Sent (bytes)"], errors="coerce")
        elif "TotalBytesSent" in df.columns:
            series = pd.to_numeric(df["TotalBytesSent"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Bytes Sent": series})
        return plot_data.dropna().reset_index(drop=True), "Bytes Sent"

    if metric_key == "network_rpc_recv":
        if not _has_network_columns(df):
            return None, None
        if "Rpc Received" in df.columns:
            series = pd.to_numeric(df["Rpc Received"], errors="coerce")
        elif "PacketsIn" in df.columns:
            series = pd.to_numeric(df["PacketsIn"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Messages Received": series})
        return plot_data.dropna().reset_index(drop=True), "Messages Received"

    if metric_key == "network_rpc_sent":
        if not _has_network_columns(df):
            return None, None
        if "Rpc Sent" in df.columns:
            series = pd.to_numeric(df["Rpc Sent"], errors="coerce")
        elif "PacketsOut" in df.columns:
            series = pd.to_numeric(df["PacketsOut"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Messages Sent": series})
        return plot_data.dropna().reset_index(drop=True), "Messages Sent"

    if metric_key == "cpu":
        candidates = [
            ("CPU Total Frame Time (ns)", 1_000_000.0),
            ("CPU Main Thread Frame Time (ns)", 1_000_000.0),
            ("Main Thread (ns)", 1_000_000.0),
            ("FrameTimeMs", 1.0),
            ("cpu_utilization_percentage", 1.0),
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
    used_col = None
    for col, divisor in candidates:
        if col not in df.columns:
            continue
        candidate = pd.to_numeric(df[col], errors="coerce")
        if candidate.isna().all():
            continue
        metric_series = candidate / divisor
        used_col = col
        break

    if metric_series is None:
        return None, None

    # Adjust output column name for Quest CPU utilization (percentage, not time)
    if used_col == "cpu_utilization_percentage":
        out_col = "CPU Utilization (%)"

    plot_data = pd.DataFrame({x_column: frame, out_col: metric_series})
    return plot_data.dropna(subset=[x_column, out_col]).reset_index(drop=True), out_col


def _extract_finished_rows(events_df: pd.DataFrame):
    events = events_df.copy()
    # Parse numeric Time and Frame separately so callers can choose the
    # alignment strategy (prefer Time when available).
    if "Time" in events.columns:
        events["Time"] = pd.to_numeric(events["Time"], errors="coerce")
    if "Frame" in events.columns:
        events["Frame"] = pd.to_numeric(events["Frame"], errors="coerce")

    if "Event" not in events.columns or "Value" not in events.columns:
        return None

    finished = events.loc[events["Event"] == "FinishedInstantiation", ["Frame", "Time", "Value"]].copy()
    # coerce Value to numeric and drop rows without it
    finished["Value"] = pd.to_numeric(finished["Value"], errors="coerce")
    finished = finished.dropna(subset=["Value"]).sort_values(by=["Time", "Frame"], na_position="last")
    return finished.reset_index(drop=True)


def _phase_bound(row: pd.Series, column: str):
    value = row.get(column)
    if pd.isna(value):
        return None
    return float(value)


def extract_movement_phase_window(events_df: pd.DataFrame, event_name: str | None = None):
    """Return the frame/time window for the movement phase.

    Prefer the longest complete phase with meaningful duration (>1 second).
    For NGO client captures, fall back to the last phase marker as the phase entry point 
    when the phase marker is zero-duration, then extend the window to the end of the capture.
    """
    events = events_df.copy()
    for column in ("Frame", "Time"):
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")

    if "Event" not in events.columns:
        return None

    phase_events = events.loc[events["Event"].isin(["PhaseStarted", "PhaseFinished"]), ["Frame", "Time", "Event"]].copy()
    if phase_events.empty:
        return None

    phase_events = phase_events.sort_values(by=["Time", "Frame"], na_position="last").reset_index(drop=True)
    start_positions = phase_events.index[phase_events["Event"] == "PhaseStarted"].tolist()
    if not start_positions:
        return None

    # NGO client captures expose the last phase marker as the point where the
    # movement capture should begin, even if that marker is zero-duration.
    if event_name is not None and "ngo_client" in event_name.lower():
        last_start_row = phase_events.loc[phase_events["Event"] == "PhaseStarted"].iloc[-1]
        last_event_row = events.sort_values(by=["Time", "Frame"], na_position="last").iloc[-1]
        start_time = _phase_bound(last_start_row, "Time")
        end_time = _phase_bound(last_event_row, "Time")
        if start_time is not None and end_time is not None and end_time > start_time:
            return {
                "frame_start": _phase_bound(last_start_row, "Frame"),
                "frame_end": _phase_bound(last_event_row, "Frame"),
                "time_start": start_time,
                "time_end": end_time,
            }

    # Find the longest complete phase with meaningful duration (>1 second, not zero-duration)
    # This avoids selecting very short phases that may be noise/transitions
    best_phase = None
    max_duration = 0
    
    for start_pos in start_positions:
        following_finished = phase_events.loc[(phase_events.index > start_pos) & (phase_events["Event"] == "PhaseFinished")]
        if following_finished.empty:
            continue

        start_row = phase_events.iloc[start_pos]
        end_row = following_finished.iloc[0]
        time_start = _phase_bound(start_row, "Time")
        time_end = _phase_bound(end_row, "Time")
        
        # Skip zero-duration phases (where start and end have the same timestamp)
        # Also skip phases shorter than 1 second (likely noise/transitions)
        if time_start is not None and time_end is not None:
            duration = time_end - time_start
            if duration > 1.0 and duration > max_duration:
                max_duration = duration
                best_phase = {
                    "frame_start": _phase_bound(start_row, "Frame"),
                    "frame_end": _phase_bound(end_row, "Frame"),
                    "time_start": time_start,
                    "time_end": time_end,
                }
    
    return best_phase


def _find_any_movement_phase_window(events_files: List[Tuple[str, pd.DataFrame]]):
    """Find any movement phase window from available event files.
    
    This is used as a fallback for Quest stats files that have no associated event file.
    Try each event file until we find one with a valid movement phase window.
    """
    if not events_files:
        return None
    
    for event_name, events_df in events_files:
        phase_window = extract_movement_phase_window(events_df, event_name)
        if phase_window is not None:
            return phase_window
    
    return None


def _filter_dataframe_to_window(df: pd.DataFrame, window):
    if window is None or df.empty:
        return df.copy()

    column = _frame_column_name(df)
    if column is None:
        return df.copy()

    values = pd.to_numeric(df[column], errors="coerce")
    start = window.get("frame_start")
    end = window.get("frame_end")

    if column != "Frame":
        start = window.get("time_start")
        end = window.get("time_end")
        
        # Convert time bounds to milliseconds if the column is 'Time Stamp' (in ms)
        # while window bounds are in seconds (from PC event files)
        if column == "Time Stamp" and start is not None and end is not None:
            start = start * 1000.0
            end = end * 1000.0

    if start is None or end is None:
        return df.copy()

    mask = values.between(start, end, inclusive="both")
    return df.loc[mask].copy()


def _normalize_time_to_phase_start(df: pd.DataFrame, window):
    """Normalize time column to start at 0 from phase window start time.
    
    For movement phase visualization, convert absolute time to relative elapsed time
    since the phase started. This aligns all benchmarks to start at x=0 on plots.
    
    Always outputs time in seconds for consistency across all data sources.
    """
    if window is None or df.empty:
        return df.copy()
    
    df_out = df.copy()
    column = _frame_column_name(df_out)
    if column is None or column == "Frame":
        return df_out
    
    start_time = window.get("time_start")
    if start_time is None:
        return df_out
    
    # Get the raw time values
    values = pd.to_numeric(df_out[column], errors="coerce")
    if not values.notna().any():
        return df_out
    
    first_val = values.dropna().iloc[0]
    
    # Detect if input is in milliseconds (values > 1000 likely mean milliseconds)
    if first_val > 1000:
        # Input is in milliseconds, convert to seconds
        values_normalized = (values - start_time * 1000.0) / 1000.0
    else:
        # Input is in seconds, subtract phase start (also in seconds)
        values_normalized = values - start_time
    
    df_out[column] = values_normalized
    return df_out


def metric_per_gameobject_series(stats_df: pd.DataFrame, events_df: pd.DataFrame, metric_key: str, stat_name: str | None = None):
    source = _source_from_name(stat_name or "")
    if source == "pc":
        from pc_data_analysis import metric_per_gameobject_series as pc_metric_per_gameobject_series

        return pc_metric_per_gameobject_series(stats_df, events_df, metric_key, stat_name)
    if source == "quest":
        from quest_data_analysis import metric_per_gameobject_series as quest_metric_per_gameobject_series

        return quest_metric_per_gameobject_series(stats_df, events_df, metric_key, stat_name)

    return None, None


def _get_event_df(events_files, event_name):
    for ename, edf in events_files:
        if ename == event_name:
            return edf
    return None


def build_datasets(
    stats_files,
    events_files,
    user_pairings,
    selected_metric_key: str,
    selected_metric_label: str,
    per_gameobject: bool,
    phase_filter: str | None = None,
    x_axis_mode: str = "frame",
):
    """Build chart-ready datasets and warning messages from selected inputs."""
    datasets = []
    warnings = []

    for sname, sdf in stats_files:
        label = _format_label(sname)
        if per_gameobject:
            selected_event_name = user_pairings.get(sname)
            if selected_event_name is None:
                if phase_filter == "movement":
                    warnings.append(f"No event file selected for {sname}; cannot isolate the movement phase.")
                    continue
                warnings.append(
                    f"No event file selected for {sname}; falling back to per-frame-to-GameObject conversion for this file."
                )
                series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
                if series is None or ycol is None:
                    # Skip silently for network metrics on files without network data
                    if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                        warnings.append(f"Also could not parse {selected_metric_label} series from {sname}.")
                    continue
                series = series.rename(columns={"Frame": "GameObjects", ycol: f"Average{ycol}"})
                ycol = f"Average{ycol}"
                series["label"] = label
                series["_ycol"] = ycol
                datasets.append((label, series))
            else:
                edf = _get_event_df(events_files, selected_event_name)
                if edf is None:
                    warnings.append(f"Event file {selected_event_name} not found for {sname}.")
                    continue

                phase_window = None
                if phase_filter == "movement":
                    phase_window = extract_movement_phase_window(edf, selected_event_name)
                    if phase_window is None:
                        warnings.append(f"No movement phase found in {selected_event_name}; skipping {sname}.")
                        continue
                    sdf = _filter_dataframe_to_window(sdf, phase_window)
                    edf = _filter_dataframe_to_window(edf, phase_window)

                series, ycol = metric_per_gameobject_series(sdf, edf, selected_metric_key, sname)
                if series is None or series.empty or ycol is None:
                    # Skip warning for network metrics on files without network data
                    if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                        warnings.append(
                            f"Per-GameObject aggregation failed for {sname} with {selected_event_name}; falling back to per-frame."
                        )
                    series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
                    if series is None or ycol is None:
                        # Skip silently for network metrics on files without network data
                        if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                            warnings.append(f"Also could not parse {selected_metric_label} series from {sname}.")
                        continue
                    
                    # Normalize time if movement phase and time x-axis (in fallback path)
                    if phase_filter == "movement" and phase_window is not None and x_axis_mode == "time":
                        series = _normalize_time_to_phase_start(series, phase_window)
                    
                    series = series.rename(columns={"Frame": "GameObjects", ycol: f"Average{ycol}"})
                    ycol = f"Average{ycol}"
                series["label"] = label
                series["_ycol"] = ycol
                datasets.append((label, series))
        else:
            phase_window = None
            if phase_filter == "movement":
                selected_event_name = user_pairings.get(sname)
                
                # Try to use paired event file first
                if selected_event_name is not None:
                    edf = _get_event_df(events_files, selected_event_name)
                    if edf is not None:
                        phase_window = extract_movement_phase_window(edf, selected_event_name)
                
                # Fallback to any available movement phase window (for Quest data without events)
                if phase_window is None:
                    phase_window = _find_any_movement_phase_window(events_files)
                
                # Skip only if we found no phase window at all
                if phase_window is None:
                    if selected_event_name is not None:
                        warnings.append(f"No movement phase found in {selected_event_name}; skipping {sname}.")
                    else:
                        warnings.append(f"No event file selected for {sname} and no movement phase found in other event files; skipping.")
                    continue
                
                sdf = _filter_dataframe_to_window(sdf, phase_window)

            series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
            if series is None or ycol is None:
                # Skip silently for network metrics on files without network data
                if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                    warnings.append(f"Could not parse {selected_metric_label} series from {sname}.")
                continue
            
            # Normalize time to start at 0 from phase window start (for time-based x-axis)
            # Apply AFTER metric_series_from_stats so column names are finalized
            if phase_filter == "movement" and phase_window is not None and x_axis_mode == "time":
                series = _normalize_time_to_phase_start(series, phase_window)
            
            series["label"] = label
            series["_ycol"] = ycol
            datasets.append((label, series))

    return datasets, warnings
