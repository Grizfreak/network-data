from typing import List, Tuple, Optional
"""
metrics_engine
---------------
Clean, documented implementation of the metric extraction and
aggregation helpers used by the Streamlit UI.

This module focuses on:
- locating metric columns in a DataFrame exported from the benchmark
- normalizing units and column names
- producing per-frame time series or per-GameObject aggregated series

The code aims to be defensive and easy to teach; docstrings explain the
reasoning behind alignment and aggregation choices.
"""

import pandas as pd


def _has_network_columns(df: pd.DataFrame) -> bool:
    network_cols = {
        "Ping (ns)", "Ping_ms",
        "RTT_ms", "RTT (ms)",
        "RTT (ms) - Calculated from RPC",
        "Total Bytes Received (bytes)", "TotalBytesReceived",
        "NetInBytesPerSec", "Download (bytes/sec)",
        "Total Bytes Sent (bytes)", "TotalBytesSent",
        "NetOutBytesPerSec", "Upload (bytes/sec)",
        "Rpc Received", "PacketsIn",
        "Rpc Sent", "PacketsOut",
    }
    return any(col in df.columns for col in network_cols)


def _has_pcap_columns(df: pd.DataFrame) -> bool:
    return any(col in df.columns for col in ("PacketsPerSec", "BytesPerSec", "Packets", "Bytes", "BitsPerSec", "CumulativePackets", "CumulativeBytes", "CumulativeBits"))


def _supports_gameobject_aggregation(metric_key: str) -> bool:
    # These metrics can be meaningfully summarized against event-derived
    # GameObject counts, so the UI is allowed to request the per-object path.
    return metric_key in {
        "fps",
        "memory",
        "cpu",
        "gpu",
        "pcap_packets",
        "pcap_bytes",
        "pcap_cumulative_packets",
        "pcap_cumulative_bytes",
        "network_ping",
        "network_rtt",
        "network_rtt_rpc",
        "network_upload",
        "network_download",
        "network_bytes_recv",
        "network_bytes_sent",
        "network_rpc_recv",
        "network_rpc_sent",
    }


def _source_from_name(file_name: str) -> Optional[str]:
    lower = (file_name or "").lower()
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


def _fps_series_from_stats(df: pd.DataFrame, stat_name: str | None = None, x_axis_mode: str = "frame"):
    x_column, output_column = _x_column_name(df, x_axis_mode)
    if x_column is None or output_column is None:
        return None

    fps_series = None
    if "FrameTimeMs" in df.columns:
        frame_time_ms = pd.to_numeric(df["FrameTimeMs"], errors="coerce").where(lambda s: s > 0)
        fps_series = 1000.0 / frame_time_ms
    elif "average_frame_rate" in df.columns:
        fps_series = pd.to_numeric(df["average_frame_rate"], errors="coerce")
    elif "FPS" in df.columns:
        fps_series = pd.to_numeric(df["FPS"], errors="coerce")
    else:
        return None

    if fps_series is not None and (fps_series.mean(skipna=True) > 1000 or fps_series.median(skipna=True) > 1000):
        if "FrameTimeMs" in df.columns:
            frame_time_ms = pd.to_numeric(df["FrameTimeMs"], errors="coerce").where(lambda s: s > 0)
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
    else:
        return None

    x_column = "Time" if x_axis_mode == "time" else "Frame"
    plot_data = pd.DataFrame({x_column: frame, "MemoryMB": memory_mb})
    return plot_data.dropna(subset=[x_column, "MemoryMB"]).reset_index(drop=True)


def metric_series_from_stats(df: pd.DataFrame, metric_key: str, stat_name: str | None = None, x_axis_mode: str = "frame"):
    """
    Return (DataFrame, ycol) for the requested metric_key, or (None, None).
    """
    if metric_key == "fps":
        return _fps_series_from_stats(df, stat_name, x_axis_mode), "FPS"
    if metric_key == "memory":
        return _memory_series_from_stats(df, x_axis_mode), "MemoryMB"

    frame = _frame_series(df, x_axis_mode)
    if frame is None:
        return None, None
    x_column = "Time" if x_axis_mode == "time" else "Frame"

    # PCAP packet counts / rates
    if metric_key == "pcap_packets":
        if not _has_pcap_columns(df):
            return None, None
        if "PacketsPerSec" in df.columns:
            series = pd.to_numeric(df["PacketsPerSec"], errors="coerce")
            out_col = "Packets/sec"
        elif "Packets" in df.columns:
            series = pd.to_numeric(df["Packets"], errors="coerce")
            out_col = "Packets"
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, out_col: series})
        return plot_data.dropna().reset_index(drop=True), out_col

    if metric_key == "pcap_cumulative_packets":
        if not _has_pcap_columns(df):
            return None, None
        if "CumulativePackets" in df.columns:
            series = pd.to_numeric(df["CumulativePackets"], errors="coerce")
            out_col = "Cumulative Packets"
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, out_col: series})
        return plot_data.dropna().reset_index(drop=True), out_col

    # PCAP bytes/rates
    if metric_key == "pcap_bytes":
        if not _has_pcap_columns(df):
            return None, None
        if "BytesPerSec" in df.columns:
            series = pd.to_numeric(df["BytesPerSec"], errors="coerce")
            out_col = "Bytes/sec"
        elif "Bytes" in df.columns:
            series = pd.to_numeric(df["Bytes"], errors="coerce")
            out_col = "Bytes"
        elif "BitsPerSec" in df.columns:
            series = pd.to_numeric(df["BitsPerSec"], errors="coerce")
            out_col = "Bits/sec"
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, out_col: series})
        return plot_data.dropna().reset_index(drop=True), out_col

    if metric_key == "pcap_cumulative_bytes":
        if not _has_pcap_columns(df):
            return None, None
        if "CumulativeBytes" in df.columns:
            series = pd.to_numeric(df["CumulativeBytes"], errors="coerce")
            out_col = "Cumulative Bytes"
        elif "CumulativeBits" in df.columns:
            series = pd.to_numeric(df["CumulativeBits"], errors="coerce")
            out_col = "Cumulative Bits"
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, out_col: series})
        return plot_data.dropna().reset_index(drop=True), out_col

    # Network-derived metrics (many possible column names across exports)
    if metric_key == "network_ping":
        if not _has_network_columns(df):
            return None, None
        if "Ping (ns)" in df.columns:
            series = pd.to_numeric(df["Ping (ns)"], errors="coerce") / 1_000_000.0
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
        elif "RTT (ms) - Calculated from RPC" in df.columns:
            series = pd.to_numeric(df["RTT (ms) - Calculated from RPC"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "RTT (ms)": series})
        return plot_data.dropna().reset_index(drop=True), "RTT (ms)"

    if metric_key == "network_rtt_rpc":
        if not _has_network_columns(df):
            return None, None
        if "RTT (ms) - Calculated from RPC" in df.columns:
            series = pd.to_numeric(df["RTT (ms) - Calculated from RPC"], errors="coerce")
        else:
            return None, None
        plot_data = pd.DataFrame({x_column: frame, "RTT (ms) - Calculated from RPC": series})
        return plot_data.dropna().reset_index(drop=True), "RTT (ms) - Calculated from RPC"

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

    # CPU / GPU metrics with candidate columns and divisors for unit conversion
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
            candidate = candidate.where((candidate > 0) & (candidate <= 1_000_000_000.0))
        metric_series = candidate / divisor
        used_col = col
        break

    if metric_series is None:
        return None, None
    if used_col == "cpu_utilization_percentage":
        out_col = "CPU Utilization (%)"

    plot_data = pd.DataFrame({x_column: frame, out_col: metric_series})
    return plot_data.dropna(subset=[x_column, out_col]).reset_index(drop=True), out_col


def _extract_finished_rows(events_df: pd.DataFrame):
    events = events_df.copy()
    if "Time" in events.columns:
        events["Time"] = pd.to_numeric(events["Time"], errors="coerce")
    if "Frame" in events.columns:
        events["Frame"] = pd.to_numeric(events["Frame"], errors="coerce")
    if "Event" not in events.columns or "Value" not in events.columns:
        return None
    finished = events.loc[events["Event"] == "FinishedInstantiation", ["Frame", "Time", "Value"]].copy()
    finished["Value"] = pd.to_numeric(finished["Value"], errors="coerce")
    finished = finished.dropna(subset=["Value"]).sort_values(by=["Time", "Frame"], na_position="last")
    return finished.reset_index(drop=True)


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


def _pcap_per_gameobject_series(stats_df: pd.DataFrame, events_df: pd.DataFrame, metric_key: str, stat_name: str | None = None):
    """
    Convert a PCAP-derived time series into a per-GameObject series.

    Uses FinishedInstantiation events as segment boundaries and picks the
    last sample inside each segment as a representative value.
    """
    metric_data, metric_column = metric_series_from_stats(stats_df, metric_key, stat_name, x_axis_mode="frame")
    if metric_data is None or metric_column is None:
        return None, None
    finished_rows = _extract_finished_rows(events_df)
    if finished_rows is None or finished_rows.empty:
        return None, None

    # Decide whether to align on Frame or Time depending on scale
    use_time_alignment = False
    if "Frame" in metric_data.columns:
        try:
            max_metric_frame = float(pd.to_numeric(metric_data["Frame"], errors="coerce").max())
            max_event_frame = float(pd.to_numeric(finished_rows["Frame"], errors="coerce").max())
            if max_event_frame > max_metric_frame * 100:
                use_time_alignment = True
        except Exception:
            use_time_alignment = True

    if use_time_alignment:
        metric_data_time, metric_column_time = metric_series_from_stats(stats_df, metric_key, stat_name, x_axis_mode="time")
        if metric_data_time is None or metric_column_time is None or "Time" not in metric_data_time.columns:
            return None, None
        sample_times = pd.to_numeric(metric_data_time["Time"], errors="coerce")
        sample_values = pd.to_numeric(metric_data_time[metric_column_time], errors="coerce")
        finished_index_col = "Time"
        metric_column = metric_column_time
        valid_samples = pd.DataFrame({"Time": sample_times, metric_column: sample_values}).dropna().sort_values("Time").reset_index(drop=True)
    else:
        sample_frames = pd.to_numeric(metric_data["Frame"], errors="coerce")
        sample_values = pd.to_numeric(metric_data[metric_column], errors="coerce")
        finished_index_col = "Frame"
        valid_samples = pd.DataFrame({"Frame": sample_frames, metric_column: sample_values}).dropna().sort_values("Frame").reset_index(drop=True)

    if valid_samples.empty:
        return None, None

    segment_points = []
    previous_value = None
    previous_frame = None
    for _, row in finished_rows.iterrows():
        current_frame = row.get(finished_index_col)
        current_value = row.get("Value")
        if pd.isna(current_frame) or pd.isna(current_value):
            continue
        if previous_frame is None:
            if finished_index_col == "Frame":
                segment = valid_samples.loc[valid_samples["Frame"] <= float(current_frame), metric_column]
            else:
                segment = valid_samples.loc[sample_times <= float(current_frame), metric_column]
        else:
            if finished_index_col == "Frame":
                segment = valid_samples.loc[(valid_samples["Frame"] > float(previous_frame)) & (valid_samples["Frame"] <= float(current_frame)), metric_column]
            else:
                segment = valid_samples.loc[(sample_times > float(previous_frame)) & (sample_times <= float(current_frame)), metric_column]
        if not segment.empty:
            try:
                gos = float(current_value)
            except Exception:
                gos = 0.0
            current_segment_value = float(segment.iloc[-1])
            if previous_value is None:
                value = current_segment_value
            else:
                value = current_segment_value - previous_value
                if value < 0:
                    value = current_segment_value
            previous_value = current_segment_value
            segment_points.append((gos, value))
        previous_frame = current_frame

    if not segment_points:
        return None, None
    if metric_key == "pcap_cumulative_packets":
        out_col = "Packets per GameObject (delta)"
    elif metric_key == "pcap_cumulative_bytes":
        out_col = "Bytes per GameObject (delta)"
    else:
        out_col = f"Average{metric_column}"
    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", out_col])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data[out_col] = pd.to_numeric(segment_data[out_col], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", out_col]).reset_index(drop=True), out_col


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
    """
    Assemble labeled DataFrames ready for plotting and return warnings.
    """
    datasets = []
    warnings = []

    for sname, sdf in stats_files:
        label = sname.rsplit(".", 1)[0]
        # Simple PCAP path (no per-GameObject aggregation requested)
        if selected_metric_key.startswith("pcap_") and not per_gameobject:
            series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
            if series is None or ycol is None:
                warnings.append(f"Could not parse {selected_metric_label} series from {sname}.")
                continue
            series["label"] = label
            series["_ycol"] = ycol
            datasets.append((label, series))
            continue

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
                warnings.append(f"No event file selected for {sname}; falling back to per-frame-to-GameObject conversion for this file.")
                series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
                if series is None or ycol is None:
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
                if selected_metric_key.startswith("pcap_"):
                    series, ycol = _pcap_per_gameobject_series(sdf, edf, selected_metric_key, sname)
                else:
                    series, ycol = metric_per_gameobject_series(sdf, edf, selected_metric_key, sname)
                if series is None or series.empty or ycol is None:
                    if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                        warnings.append(f"Per-GameObject aggregation failed for {sname} with {selected_event_name}; falling back to per-frame.")
                    series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname, x_axis_mode=x_axis_mode)
                    if series is None or ycol is None:
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
                if not (selected_metric_key.startswith("network_") and not _has_network_columns(sdf)):
                    warnings.append(f"Could not parse {selected_metric_label} series from {sname}.")
                continue
            series["label"] = label
            series["_ycol"] = ycol
            datasets.append((label, series))

    return datasets, warnings
