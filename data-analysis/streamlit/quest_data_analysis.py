from __future__ import annotations

import numpy as np
import pandas as pd

from metrics_engine import metric_series_from_stats, _extract_finished_rows

"""
quest_data_analysis
--------------------
Quest-specific helpers mirroring PC processing, with attention to
differences in time units and exported column names. These functions
demonstrate defensive programming when merging data from sources
with slightly different schemas.
"""


def _interp_or_nan(x: float, xs: np.ndarray, ys: np.ndarray) -> float:
    """Like np.interp but returns NaN when x is outside [xs[0], xs[-1]].

    See pc_data_analysis._interp_or_nan for rationale: np.interp clamps
    to boundary values, which produces misleading "0 ms ping" segments
    when the boundary samples are Photon sentinels.
    """
    if x < xs[0] or x > xs[-1]:
        return float("nan")
    return float(np.interp(x, xs, ys))


def _stats_time_unit(stats_df: pd.DataFrame):
    """Return the dominant time unit used by the stats frame.

    Kept for compatibility with earlier callers; the per-GameObject
    aggregation now looks up events against the Frame axis directly.
    """
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

    event_points = []
    for _, row in finished_rows.iterrows():
        current_value = row.get("Value")
        if pd.isna(current_value):
            continue

        # Always look up against the Frame axis (the same axis the samples
        # use). Prefer Frame from the event; fall back to Time only when Frame
        # is unavailable, converting seconds → Frame via the stats Time/Frame
        # ratio. This fixes the previous unit-mismatch where event Time (in
        # seconds) was looked up against a Frame-numbered axis, producing a
        # constant clamped value of sample_y[0].
        lookup_frame = None
        if pd.notna(row.get("Frame")):
            lookup_frame = float(row["Frame"])
        elif pd.notna(row.get("Time")) and "Time" in stats_df.columns and "Frame" in stats_df.columns:
            t = float(row["Time"])
            times = pd.to_numeric(stats_df["Time"], errors="coerce")
            frames = pd.to_numeric(stats_df["Frame"], errors="coerce")
            valid = pd.DataFrame({"t": times, "f": frames}).dropna().sort_values("t")
            if not valid.empty:
                lookup_frame = float(np.interp(t, valid["t"].to_numpy(dtype=float), valid["f"].to_numpy(dtype=float)))
        if lookup_frame is None:
            continue

        event_points.append((float(current_value), _interp_or_nan(lookup_frame, sample_x, sample_y)))

    if not event_points:
        return None, None

    first_event_frame = None
    first_row = finished_rows.iloc[0]
    if pd.notna(first_row.get("Frame")):
        first_event_frame = float(first_row["Frame"])
    elif pd.notna(first_row.get("Time")) and "Time" in stats_df.columns and "Frame" in stats_df.columns:
        t = float(first_row["Time"])
        times = pd.to_numeric(stats_df["Time"], errors="coerce")
        frames = pd.to_numeric(stats_df["Frame"], errors="coerce")
        valid = pd.DataFrame({"t": times, "f": frames}).dropna().sort_values("t")
        if not valid.empty:
            first_event_frame = float(np.interp(t, valid["t"].to_numpy(dtype=float), valid["f"].to_numpy(dtype=float)))

    segment_points = []
    if first_event_frame is not None:
        segment_points.append((0, _interp_or_nan(first_event_frame, sample_x, sample_y)))
    segment_points.extend(event_points)

    out_col = f"Average{metric_col}"
    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", out_col])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data[out_col] = pd.to_numeric(segment_data[out_col], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", out_col]).reset_index(drop=True), out_col
