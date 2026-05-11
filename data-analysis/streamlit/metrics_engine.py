from typing import List, Tuple

import pandas as pd


def _source_from_name(file_name: str):
    lower = file_name.lower()
    if lower.startswith("[pc]"):
        return "pc"
    if lower.startswith("[quest]"):
        return "quest"
    return None


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


def _fps_series_from_stats(df: pd.DataFrame, stat_name: str | None = None):
    frame_column = None
    if "Frame" in df.columns:
        frame_column = "Frame"
    elif "Time Stamp" in df.columns:
        frame_column = "Time Stamp"
    elif "Time" in df.columns:
        frame_column = "Time"
    else:
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

    plot_data = df[[frame_column]].copy()
    plot_data["FPS"] = fps_series
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


def metric_series_from_stats(df: pd.DataFrame, metric_key: str, stat_name: str | None = None):
    if metric_key == "fps":
        return _fps_series_from_stats(df, stat_name), "FPS"

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
):
    """Build chart-ready datasets and warning messages from selected inputs."""
    datasets = []
    warnings = []

    for sname, sdf in stats_files:
        label = _format_label(sname)
        if per_gameobject:
            selected_event_name = user_pairings.get(sname)
            if selected_event_name is None:
                warnings.append(
                    f"No event file selected for {sname}; falling back to per-frame-to-GameObject conversion for this file."
                )
                series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname)
                if series is None or ycol is None:
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
                    warnings.append(
                        f"Per-GameObject aggregation failed for {sname} with {selected_event_name}; falling back to per-frame."
                    )
                    series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname)
                    if series is None or ycol is None:
                        warnings.append(f"Also could not parse {selected_metric_label} series from {sname}.")
                        continue
                    series = series.rename(columns={"Frame": "GameObjects", ycol: f"Average{ycol}"})
                    ycol = f"Average{ycol}"
                series["label"] = label
                series["_ycol"] = ycol
                datasets.append((label, series))
        else:
            series, ycol = metric_series_from_stats(sdf, selected_metric_key, sname)
            if series is None or ycol is None:
                warnings.append(f"Could not parse {selected_metric_label} series from {sname}.")
                continue
            series["label"] = label
            series["_ycol"] = ycol
            datasets.append((label, series))

    return datasets, warnings
