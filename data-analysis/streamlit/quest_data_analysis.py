from __future__ import annotations

import numpy as np
import pandas as pd

from metrics_engine import metric_series_from_stats, _extract_finished_rows


def _stats_time_unit(stats_df: pd.DataFrame):
    if "Time Stamp" in stats_df.columns:
        return "ms"
    if "Time" in stats_df.columns:
        return "s"
    return "frames"


def metric_per_gameobject_series(
    stats_df: pd.DataFrame,
    events_df: pd.DataFrame,
    metric_key: str,
    stat_name: str | None = None,
):
    plot_data, metric_col = metric_series_from_stats(stats_df, metric_key, stat_name)
    if plot_data is None or metric_col is None:
        return None, None

    finished_rows = _extract_finished_rows(events_df)
    if finished_rows is None or finished_rows.empty:
        return None, None

    sample_frames = pd.to_numeric(plot_data["Frame"], errors="coerce")
    sample_values = pd.to_numeric(plot_data[metric_col], errors="coerce")
    valid_samples = pd.DataFrame({"Frame": sample_frames, metric_col: sample_values}).dropna().sort_values("Frame")
    if valid_samples.empty:
        return None, None

    sample_x = valid_samples["Frame"].to_numpy(dtype=float)
    sample_y = valid_samples[metric_col].to_numpy(dtype=float)
    stats_time_unit = _stats_time_unit(stats_df)

    event_points = []
    for _, row in finished_rows.iterrows():
        current_value = row.get("Value")
        if pd.isna(current_value):
            continue

        if pd.notna(row.get("Time")):
            event_time = float(row["Time"])
            event_time_on_stats = event_time * 1000.0 if stats_time_unit == "ms" else event_time
        elif pd.notna(row.get("Frame")):
            event_time_on_stats = float(row["Frame"])
        else:
            continue

        event_points.append((float(current_value), float(np.interp(event_time_on_stats, sample_x, sample_y))))

    if not event_points:
        return None, None

    first_event_time = None
    first_row = finished_rows.iloc[0]
    if pd.notna(first_row.get("Time")):
        first_event_time = float(first_row["Time"])
        if stats_time_unit == "ms":
            first_event_time *= 1000.0
    elif pd.notna(first_row.get("Frame")):
        first_event_time = float(first_row["Frame"])

    segment_points = []
    if first_event_time is not None:
        segment_points.append((0, float(np.interp(first_event_time, sample_x, sample_y))))
    segment_points.extend(event_points)

    out_col = f"Average{metric_col}"
    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", out_col])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data[out_col] = pd.to_numeric(segment_data[out_col], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", out_col]).reset_index(drop=True), out_col
