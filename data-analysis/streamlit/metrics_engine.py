from typing import List, Tuple

import pandas as pd


def _has_network_columns(df: pd.DataFrame) -> bool:
    """Check if the DataFrame has any network-related columns."""
    network_cols = {
        "Ping (ns)", "Ping_ms",
        "RTT_ms", "RTT (ms)",
        "Total Bytes Received (bytes)", "TotalBytesReceived",
        "NetInBytesPerSec", "Download (bytes/sec)",
        "Total Bytes Sent (bytes)", "TotalBytesSent",
        "NetOutBytesPerSec", "Upload (bytes/sec)",
        "Rpc Received", "PacketsIn",
        "Rpc Sent", "PacketsOut",
        "Object Spawned Bytes Received (bytes)",
        "Object Spawned Bytes Sent (bytes)",
        "Rpc Bytes Received (bytes)",
        "Rpc Bytes Sent (bytes)",
    }
    return any(col in df.columns for col in network_cols)


def _supports_gameobject_aggregation(metric_key: str) -> bool:
    return metric_key in {"fps", "memory", "cpu", "gpu"}


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
    elif "fishnet" in body:
        bench_type = "FishNet"
        if "fishnet_client" in body:
            variant = " Client"
        elif "fishnet_server" in body:
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
    # Prefer computing from FrameTimeMs when available (more reliable than
    # an exported FPS column which sometimes contains scaled values).
    if "FrameTimeMs" in df.columns:
        frame_time_ms = pd.to_numeric(df["FrameTimeMs"], errors="coerce")
        frame_time_ms = frame_time_ms.where(frame_time_ms > 0)
        fps_series = 1000.0 / frame_time_ms
    elif "average_frame_rate" in df.columns:
        fps_series = pd.to_numeric(df["average_frame_rate"], errors="coerce")
    elif "FPS" in df.columns:
        fps_series = pd.to_numeric(df["FPS"], errors="coerce")
    else:
        return None

    # Guard: if the FPS values look implausibly large (e.g., >1000), and a
    # FrameTimeMs column exists, prefer that computed series instead.
    if fps_series is not None and (fps_series.mean(skipna=True) > 1000 or fps_series.median(skipna=True) > 1000):
        if "FrameTimeMs" in df.columns:
            frame_time_ms = pd.to_numeric(df["FrameTimeMs"], errors="coerce")
            frame_time_ms = frame_time_ms.where(frame_time_ms > 0)
            fps_series = 1000.0 / frame_time_ms

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
        elif "RTT_ms" in df.columns:
            series = pd.to_numeric(df["RTT_ms"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Ping (ms)": series})
        return plot_data.dropna().reset_index(drop=True), "Ping (ms)"

    if metric_key == "network_rtt":
        if not _has_network_columns(df):
            return None, None
        if "RTT (ms)" in df.columns:
            series = pd.to_numeric(df["RTT (ms)"], errors="coerce")
        elif "RTT_ms" in df.columns:
            series = pd.to_numeric(df["RTT_ms"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "RTT (ms)": series})
        return plot_data.dropna().reset_index(drop=True), "RTT (ms)"

    if metric_key == "network_upload":
        if not _has_network_columns(df):
            return None, None
        if "Upload (bytes/sec)" in df.columns:
            series = pd.to_numeric(df["Upload (bytes/sec)"], errors="coerce")
        elif "NetOutBytesPerSec" in df.columns:
            series = pd.to_numeric(df["NetOutBytesPerSec"], errors="coerce")
        elif "Total Bytes Sent (bytes)" in df.columns:
            series = pd.to_numeric(df["Total Bytes Sent (bytes)"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Upload (bytes/sec)": series})
        return plot_data.dropna().reset_index(drop=True), "Upload (bytes/sec)"

    if metric_key == "network_download":
        if not _has_network_columns(df):
            return None, None
        if "Download (bytes/sec)" in df.columns:
            series = pd.to_numeric(df["Download (bytes/sec)"], errors="coerce")
        elif "NetInBytesPerSec" in df.columns:
            series = pd.to_numeric(df["NetInBytesPerSec"], errors="coerce")
        elif "Total Bytes Received (bytes)" in df.columns:
            series = pd.to_numeric(df["Total Bytes Received (bytes)"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "Download (bytes/sec)": series})
        return plot_data.dropna().reset_index(drop=True), "Download (bytes/sec)"
        
    if metric_key == "network_bytes_recv":
        if not _has_network_columns(df):
            return None, None
        if "Total Bytes Received (bytes)" in df.columns:
            series = pd.to_numeric(df["Total Bytes Received (bytes)"], errors="coerce")
        elif "TotalBytesReceived" in df.columns:
            series = pd.to_numeric(df["TotalBytesReceived"], errors="coerce")
        elif "NetInBytesPerSec" in df.columns:
            series = pd.to_numeric(df["NetInBytesPerSec"], errors="coerce")
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
        elif "NetOutBytesPerSec" in df.columns:
            series = pd.to_numeric(df["NetOutBytesPerSec"], errors="coerce")
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
        if col == "GPU Frame Time (ns)":
            # Some exports contain clearly corrupt GPU samples (e.g. 1e16 ns);
            # drop anything implausibly large before converting to ms.
            candidate = candidate.where((candidate > 0) & (candidate <= 1_000_000_000.0))
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
    x_axis_mode: str = "frame",
    include_unpaired: bool = False,
):
    """Build chart-ready datasets and warning messages from selected inputs."""
    datasets = []
    warnings = []

    for sname, sdf in stats_files:
        label = _format_label(sname)
        if per_gameobject:
            if not _supports_gameobject_aggregation(selected_metric_key):
                series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
                if series is None or ycol is None:
                    if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                        warnings.append(f"Could not parse {selected_metric_label} series from {sname}.")
                    continue
                series["label"] = label
                series["_ycol"] = ycol
                datasets.append((label, series))
                continue

            selected_event_name = user_pairings.get(sname)
            if selected_event_name is None:
                if not include_unpaired:
                    warnings.append(f"No event file selected for {sname}; skipping per-GameObject aggregation.")
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
                    series = series.rename(columns={"Frame": "GameObjects", ycol: f"Average{ycol}"})
                    ycol = f"Average{ycol}"
                series["label"] = label
                series["_ycol"] = ycol
                datasets.append((label, series))
        else:
            series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
            if series is None or ycol is None:
                # Skip silently for network metrics on files without network data
                if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                    warnings.append(f"Could not parse {selected_metric_label} series from {sname}.")
                continue
            series["label"] = label
            series["_ycol"] = ycol
            datasets.append((label, series))

    return datasets, warnings
