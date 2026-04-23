import numpy as np
import pandas as pd


def get_x_axis_info(data):
    if "Time (s)" in data.columns:
        return "Time (s)", "Time (s)", True
    if "Frame" in data.columns:
        return "Frame", "Frame", False
    raise ValueError("Missing Time (s) or Frame column in stats file")


def to_numeric_series(data, column):
    return pd.to_numeric(data[column], errors="coerce")


def event_frames_to_x(event_frames, data, x_col):
    frame_series = pd.to_numeric(event_frames, errors="coerce")
    if x_col == "Frame":
        return frame_series.dropna()

    if "Frame" not in data.columns or x_col not in data.columns:
        return pd.Series(dtype="float64")

    map_df = data[["Frame", x_col]].copy()
    map_df["Frame"] = pd.to_numeric(map_df["Frame"], errors="coerce")
    map_df[x_col] = pd.to_numeric(map_df[x_col], errors="coerce")
    map_df = map_df.dropna(subset=["Frame", x_col]).sort_values("Frame")
    map_df = map_df.drop_duplicates(subset=["Frame"], keep="first")

    if map_df.empty:
        return pd.Series(dtype="float64")

    min_frame = map_df["Frame"].min()
    max_frame = map_df["Frame"].max()
    in_range = frame_series.where(frame_series.between(min_frame, max_frame))

    mapped = np.interp(
        in_range.fillna(min_frame),
        map_df["Frame"].to_numpy(),
        map_df[x_col].to_numpy(),
    )
    result = pd.Series(mapped, index=frame_series.index)
    result[in_range.isna()] = np.nan
    return result.dropna()
