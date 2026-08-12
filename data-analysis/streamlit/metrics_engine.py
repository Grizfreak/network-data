from typing import List, Tuple, Optional
"""
metrics_engine
---------------
Metric extraction and aggregation helpers used by the Streamlit UI.

This module provides:
- locating metric columns in a DataFrame exported from the benchmark
- normalizing units and column names
- producing per-frame time series or per-GameObject aggregated series
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
    if lower.startswith("[godot]"):
        return "godot"
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


def _bytes_series_to_mb(df: pd.DataFrame, column_name: str):
    if column_name not in df.columns:
        return None
    series = pd.to_numeric(df[column_name], errors="coerce")
    return series / (1024.0 * 1024.0)


def _sanitize_latency_series(series: "pd.Series[float]") -> "pd.Series[float]":
    """Drop sentinel/no-measurement and out-of-range values from a latency series.

    Three classes of bad values are filtered out:

    1. **Negative sentinels.** Some profilers (notably Photon's older
       ``RTT (ms)`` export) emit ``-1`` as a sentinel meaning "RTT not yet
       measured" before the first round-trip completes.
    2. **Zero sentinels.** Photon's older ``Ping_ms`` export writes 0
       whenever no measurement is available (e.g. before the connection
       is established or after a disconnect). The vast majority of
       rows in a typical capture can be 0, and ``np.interp`` would
       happily return 0 for any frame in those regions, producing
       misleading "0 ms ping" flat segments. We treat 0 as a sentinel
       so the per-GameObject aggregation skips those rows instead.
       Truly sub-millisecond LAN pings are exceedingly rare and were
       already implicit noise; rejecting 0s makes the chart match
       the underlying signal.
    3. **Out-of-range values** (likely a unit-mislabel). The Quest
       base/DOTS/GPU profiler exports store nanoseconds in a column
       labelled ``RTT (ms)`` — values like 13,851,306 appear where
       13.85 ms was intended. Any value above 30 seconds (30,000 ms) is
       treated as a unit error and dropped.
    """
    return series.where((series > 0) & (series <= 30_000))


def _bytes_per_sec_from_cumulative(
    df: pd.DataFrame, cumulative_col: str, x_column: str, frame: "pd.Series[float]"
) -> "pd.Series[float]":
    """Convert a monotonically-increasing cumulative byte counter into a bytes/sec rate.

    The benchmark CSV only ships cumulative counters (e.g. ``TotalBytesReceived``,
    ``Total Bytes Sent (bytes)``). Plotting them directly as a "rate" produces a
    constantly-rising curve and, worse, yields negative values whenever the
    counter wraps or resets (Photon reconnects, scene reloads, etc.).

    Strategy:
      1. Take ``diff()`` of the cumulative counter; clamp negative diffs to 0
         so a reset is treated as "no bytes transferred" rather than a bogus
         negative spike.
      2. Convert the diff to a per-second rate using the most precise time axis
         available (``Time Stamp`` in ms, ``Time`` in s, else sample index).
    """
    counter = pd.to_numeric(df[cumulative_col], errors="coerce")
    byte_diff = counter.diff().clip(lower=0)

    # Choose the most precise time axis (seconds).
    if "Time Stamp" in df.columns:
        dt = pd.to_numeric(df["Time Stamp"], errors="coerce").diff() / 1000.0
    elif "Time" in df.columns:
        dt = pd.to_numeric(df["Time"], errors="coerce").diff()
    elif x_column == "Frame":
        dt = pd.to_numeric(frame, errors="coerce").diff()
    else:
        dt = pd.Series([1.0] * len(df), index=df.index)

    rate = byte_diff / dt.replace(0, pd.NA)
    return rate


def metric_series_from_stats(df: pd.DataFrame, metric_key: str, stat_name: str | None = None, x_axis_mode: str = "frame"):
    """
    Return (DataFrame, ycol) for the requested metric_key, or (None, None).
    """
    if metric_key == "fps":
        return _fps_series_from_stats(df, stat_name, x_axis_mode), "FPS"
    if metric_key == "memory":
        return _memory_series_from_stats(df, x_axis_mode), "MemoryMB"

    if metric_key == "godot_fps":
        return _fps_series_from_stats(df, stat_name, x_axis_mode), "FPS"

    if metric_key == "godot_frame_time":
        frame = _frame_series(df, x_axis_mode)
        if frame is None or "FrameTimeMs" not in df.columns:
            return None, None
        series = pd.to_numeric(df["FrameTimeMs"], errors="coerce")
        plot_data = pd.DataFrame({"Frame" if x_axis_mode == "frame" else "Time": frame, "FrameTimeMs": series})
        return plot_data.dropna().reset_index(drop=True), "FrameTimeMs"

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
        series = _sanitize_latency_series(series)
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
        elif "Ping_ms" in df.columns:
            # Photon exports don't expose RTT_ms; fall back to Ping_ms so
            # the RTT subplot isn't empty when comparing Photon vs. NGO.
            series = pd.to_numeric(df["Ping_ms"], errors="coerce")
        else:
            return None, None
        series = _sanitize_latency_series(series)
        plot_data = pd.DataFrame({x_column: frame, "RTT (ms)": series})
        return plot_data.dropna().reset_index(drop=True), "RTT (ms)"

    if metric_key == "network_rtt_rpc":
        if not _has_network_columns(df):
            return None, None
        if "RTT (ms) - Calculated from RPC" in df.columns:
            series = pd.to_numeric(df["RTT (ms) - Calculated from RPC"], errors="coerce")
        else:
            return None, None
        series = _sanitize_latency_series(series)
        plot_data = pd.DataFrame({x_column: frame, "RTT (ms) - Calculated from RPC": series})
        return plot_data.dropna().reset_index(drop=True), "RTT (ms) - Calculated from RPC"

    if metric_key == "network_upload":
        if not _has_network_columns(df):
            return None, None
        if "Upload (bytes/sec)" in df.columns:
            series = pd.to_numeric(df["Upload (bytes/sec)"], errors="coerce")
        elif "NetOutBytesPerSec" in df.columns:
            series = pd.to_numeric(df["NetOutBytesPerSec"], errors="coerce")
        elif "TotalBytesSent" in df.columns:
            series = _bytes_per_sec_from_cumulative(
                df, "TotalBytesSent", x_column, frame
            )
        elif "Total Bytes Sent (bytes)" in df.columns:
            series = _bytes_per_sec_from_cumulative(
                df, "Total Bytes Sent (bytes)", x_column, frame
            )
        else:
            return None, None
        # Clamp negatives: counters can wrap/reset mid-run; treat those as 0.
        if series is not None:
            series = series.clip(lower=0)
        plot_data = pd.DataFrame({x_column: frame, "Upload (bytes/sec)": series})
        return plot_data.dropna().reset_index(drop=True), "Upload (bytes/sec)"

    if metric_key == "network_download":
        if not _has_network_columns(df):
            return None, None
        if "Download (bytes/sec)" in df.columns:
            series = pd.to_numeric(df["Download (bytes/sec)"], errors="coerce")
        elif "NetInBytesPerSec" in df.columns:
            series = pd.to_numeric(df["NetInBytesPerSec"], errors="coerce")
        elif "TotalBytesReceived" in df.columns:
            series = _bytes_per_sec_from_cumulative(
                df, "TotalBytesReceived", x_column, frame
            )
        elif "Total Bytes Received (bytes)" in df.columns:
            series = _bytes_per_sec_from_cumulative(
                df, "Total Bytes Received (bytes)", x_column, frame
            )
        else:
            return None, None
        # Clamp negatives: counters can wrap/reset mid-run; treat those as 0.
        if series is not None:
            series = series.clip(lower=0)
        plot_data = pd.DataFrame({x_column: frame, "Download (bytes/sec)": series})
        return plot_data.dropna().reset_index(drop=True), "Download (bytes/sec)"

    # CPU / GPU metrics with candidate columns and divisors for unit conversion
    if metric_key == "cpu":
        # Prefer real frame-time columns. On Quest captures that only expose
        # `average_frame_rate` and `cpu_utilization_percentage`, fall back to
        # the frame time derived from FPS (1000 / fps). We intentionally
        # ignore `cpu_utilization_percentage` (it's a sum across cores, e.g.
        # 600% on 6 cores) to keep CPU expressed in milliseconds, which is
        # directly comparable across PC and Quest.
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

    # Fallback for captures that only expose FPS: derive total frame time in
    # ms as 1000 / average_frame_rate. This matches what `threadplot.py`
    # already does for Quest captures, and lets us express CPU in ms even
    # when no explicit frame-time column is available.
    if metric_series is None and metric_key == "cpu" and "average_frame_rate" in df.columns:
        fps = pd.to_numeric(df["average_frame_rate"], errors="coerce")
        metric_series = 1000.0 / fps.where(fps > 0)
        used_col = "average_frame_rate"

    if metric_series is None:
        return None, None

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
    # Godot files no longer carry a dedicated [Godot] prefix; they are
    # tagged with their capture platform ([PC] / [Quest]) and identified
    # by the `godot` token in the filename. Route them through the PC
    # per-GameObject pipeline, which is what the alias used to point at
    # anyway (see `pc_data_analysis.metric_per_gameobject_series`).
    if "godot" in (stat_name or "").lower():
        from pc_data_analysis import metric_per_gameobject_series as godot_metric_per_gameobject_series
        return godot_metric_per_gameobject_series(stats_df, events_df, metric_key, stat_name)
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

    # Decide whether to align on Frame or Time depending on scale.
    #
    # PCAP-derived time series have a `Frame` column that is just a
    # per-second bucket index (0..N where N is the capture duration in
    # seconds), NOT a Unity/engine frame number. The events file's
    # `Frame` column is the actual engine frame (typically 0..tens of
    # thousands). Comparing the two directly is meaningless and produces
    # bogus segment ranges (e.g. every PCAP sample has Frame <= 2191, so
    # the first event claims the entire PCAP trace, and every later
    # event finds an empty segment). For PCAP files, the only alignment
    # that makes sense is time-based: the PCAP `Time (s)` column maps 1:1
    # to the events `Time` column.
    use_time_alignment = _has_pcap_columns(stats_df)

    if not use_time_alignment and "Frame" in metric_data.columns:
        try:
            max_metric_frame = float(pd.to_numeric(metric_data["Frame"], errors="coerce").max())
            max_event_frame = float(pd.to_numeric(finished_rows["Frame"], errors="coerce").max())
            if max_event_frame > max_metric_frame * 100:
                use_time_alignment = True
        except Exception as exc:
            # Log the exception for debugging but continue with frame alignment
            # Use print instead of warnings since this is a standalone function
            print(f"Time alignment decision failed: {exc}")
            use_time_alignment = False

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
        # Initialize variables for frame alignment path to avoid undefined references
        finished_index_col = "Frame"
        sample_frames = pd.to_numeric(metric_data["Frame"], errors="coerce")
        sample_values = pd.to_numeric(metric_data[metric_column], errors="coerce")
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
            # Use the median of the per-bucket samples in this segment as a
            # representative value. PCAP traffic is bursty (a few buckets with
            # many packets followed by empty ones), so the median is more
            # representative of the typical load than the last sample or the
            # mean. This de-noises the per-GameObject curve while preserving
            # the overall trend.
            current_segment_value = float(segment.median())
            if previous_value is None:
                value = current_segment_value
            else:
                # For rate-based metrics (Packets/sec, Bytes/sec), a per-segment
                # delta is meaningless — the rate can fluctuate up and down
                # bucket to bucket, so a difference between two medians is
                # not a meaningful "amount per GameObject". Only for cumulative
                # counters does the delta make sense (packets added between
                # two paliers of GameObjects).
                if metric_key in ("pcap_cumulative_packets", "pcap_cumulative_bytes"):
                    value = current_segment_value - previous_value
                    if value < 0:
                        value = current_segment_value
                else:
                    value = current_segment_value
            previous_value = current_segment_value
            segment_points.append((gos, value))
        previous_frame = current_frame

    if not segment_points:
        return None, None
    if metric_key == "pcap_cumulative_packets":
        # Total packets sent between the previous palier and this one —
        # this is the true "delta" (cumulative difference) meaningful for
        # understanding the cost of adding the new GameObjects.
        out_col = "Packets per palier (delta)"
    elif metric_key == "pcap_cumulative_bytes":
        out_col = "Bytes per palier (delta)"
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


def average_series_across_runs(
    series_list: list,
    x_col: str,
    y_col: str,
    tolerance: float = 0.0,
) -> pd.DataFrame:
    """Combine N per-run (x, y) series for the SAME system into one
    averaged series with spread.

    Each entry in `series_list` is a DataFrame with at least
    [x_col, y_col] (e.g. the per-GameObject output of
    metric_per_gameobject_series). A list of length 1 passes through
    safely (mean == the single value, std == NaN, n == 1) so callers can
    always route single-run data through this function.

    tolerance: if > 0, x-values within this distance are snapped onto a
    shared grid before averaging (handles GameObjects milestones that
    drift slightly between runs). 0 (default) requires exact x matches.

    Returns a DataFrame [x_col, "mean", "std", "min", "max", "n"] sorted
    by x_col; a milestone reached by only some runs still appears, with
    n < len(series_list).
    """
    frames = []
    for series in series_list:
        cleaned = series[[x_col, y_col]].dropna()
        if not cleaned.empty:
            frames.append(cleaned)
    if not frames:
        return pd.DataFrame(columns=[x_col, "mean", "std", "min", "max", "n"])

    combined = pd.concat(frames, ignore_index=True)
    if tolerance > 0:
        combined["_bucket"] = (combined[x_col] / tolerance).round() * tolerance
    else:
        combined["_bucket"] = combined[x_col]

    grouped = (
        combined.groupby("_bucket")
        .agg(
            **{
                x_col: (x_col, "mean"),
                "mean": (y_col, "mean"),
                "std": (y_col, "std"),
                "min": (y_col, "min"),
                "max": (y_col, "max"),
                "n": (y_col, "count"),
            }
        )
        .reset_index(drop=True)
    )
    return grouped.sort_values(x_col).reset_index(drop=True)
