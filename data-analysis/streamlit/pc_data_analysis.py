from __future__ import annotations

import numpy as np
import pandas as pd

from metrics_engine import metric_series_from_stats, _extract_finished_rows

"""
pc_data_analysis
----------------
PC-specific helpers for converting a per-frame metric time series
into a per-GameObject aggregated series using the event trace.

Keep these helpers small and well-documented: they show how to map
continuous samples into discrete experiment phases for analysis.
"""


def _interp_or_nan(x: float, xs: np.ndarray, ys: np.ndarray) -> float:
    """Like np.interp but returns NaN when x is outside [xs[0], xs[-1]].

    np.interp clamps to the boundary values, which is misleading when
    those boundary samples are sentinel zeros (e.g. Photon writing 0
    before the connection is established). Returning NaN instead makes
    Plotly break the line at that point, so the chart accurately
    reflects "no measurement" rather than a fake zero.
    """
    if x < xs[0] or x > xs[-1]:
        return float("nan")
    return float(np.interp(x, xs, ys))


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

    segment_points = []
    first_frame = finished_rows.iloc[0]["Frame"]
    if pd.notna(first_frame):
        first_value = _interp_or_nan(float(first_frame), sample_x, sample_y)
        segment_points.append((0, first_value))

    for _, row in finished_rows.iterrows():
        current_frame = row.get("Frame")
        current_value = row.get("Value")
        if pd.isna(current_frame) or pd.isna(current_value):
            continue
        interpolated_value = _interp_or_nan(float(current_frame), sample_x, sample_y)
        segment_points.append((float(current_value), interpolated_value))

    if not segment_points:
        return None, None

    out_col = f"Average{metric_col}"
    segment_data = pd.DataFrame(segment_points, columns=["GameObjects", out_col])
    segment_data["GameObjects"] = pd.to_numeric(segment_data["GameObjects"], errors="coerce")
    segment_data[out_col] = pd.to_numeric(segment_data[out_col], errors="coerce")
    return segment_data.dropna(subset=["GameObjects", out_col]).reset_index(drop=True), out_col
