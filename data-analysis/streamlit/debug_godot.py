"""Diagnostic: why does PC - Godot Client 16.1602 stop at ~4500 GO?

Runs the exact per-GameObject pipeline (metrics_engine → pc_data_analysis)
on the Godot CSV and prints where the curve truncates.
"""
import sys
import os

# Ensure we run inside the streamlit package so relative imports work
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)

import pandas as pd
from data_loader import load_csv_files_from_folder
from metrics_engine import metric_per_gameobject_series
from pc_data_analysis import _interp_or_nan
import numpy as np

from pathlib import Path
FOLDER = Path(r"e:\Lab\unity-network-benchmark\data-analysis\data\20260528_145024")

print("=" * 72)
print("Loading CSV files from folder ...")
print("=" * 72)
stats_files, events_files, errors = load_csv_files_from_folder(FOLDER)
for n, e in errors:
    print(f"  [read error] {n}: {e}")

# Find the Godot profiler stats and its matching events
godot_stat = None
godot_event = None
for n, df in stats_files:
    if "godot" in n.lower() and "stats" in n.lower():
        godot_stat = (n, df)
for n, df in events_files:
    if "godot" in n.lower() and "event" in n.lower():
        godot_event = (n, df)

if godot_stat is None or godot_event is None:
    print("ERROR: could not find godot stat/event pair")
    print("Found stat files:")
    for n, _ in stats_files:
        print(f"  - {n}")
    print("Found event files:")
    for n, _ in events_files:
        print(f"  - {n}")
    sys.exit(1)

stat_name, stats_df = godot_stat
event_name, events_df = godot_event
print(f"\nStat file: {stat_name}  ({len(stats_df)} rows)")
print(f"Event file: {event_name}  ({len(events_df)} rows)")

# Print column info
print(f"\nStats columns: {list(stats_df.columns)}")
print(f"Stats Frame range: {pd.to_numeric(stats_df['Frame'], errors='coerce').min()} -> {pd.to_numeric(stats_df['Frame'], errors='coerce').max()}")
print(f"Events Frame range: {pd.to_numeric(events_df['Frame'], errors='coerce').min()} -> {pd.to_numeric(events_df['Frame'], errors='coerce').max()}")

# Run the metric_per_gameobject_series for FPS
print("\n" + "=" * 72)
print("Running metric_per_gameobject_series('fps', ...) on Godot data")
print("=" * 72)

result_df, result_col = metric_per_gameobject_series(
    stats_df, events_df, "fps", stat_name
)

if result_df is None or result_df.empty:
    print("RESULT IS EMPTY OR NONE")
    print("This is why the Streamlit plot truncates at ~4500 GO.")
else:
    print(f"Got {len(result_df)} per-GameObject points")
    print(f"Columns: {list(result_df.columns)}")
    print(f"GameObject range: {result_df['GameObjects'].min()} -> {result_df['GameObjects'].max()}")
    print("\nFirst 10 points:")
    print(result_df.head(10).to_string())
    print("\nLast 10 points:")
    print(result_df.tail(10).to_string())
    print("\nNaN count in result column:", result_df[result_col].isna().sum())

# Also try to manually step through the code to see WHERE it fails
print("\n" + "=" * 72)
print("Step-by-step trace of the interpolation")
print("=" * 72)

from metrics_engine import metric_series_from_stats, _extract_finished_rows
plot_data, metric_col = metric_series_from_stats(stats_df, "fps", stat_name)
finished_rows = _extract_finished_rows(events_df)
print(f"plot_data shape: {plot_data.shape}, metric_col: {metric_col}")
print(f"finished_rows shape: {finished_rows.shape}")

sample_frames = pd.to_numeric(plot_data["Frame"], errors="coerce")
sample_values = pd.to_numeric(plot_data[metric_col], errors="coerce")
valid_samples = pd.DataFrame({"Frame": sample_frames, metric_col: sample_values}).dropna().sort_values("Frame")
print(f"valid_samples shape: {valid_samples.shape}")
print(f"valid_samples Frame range: {valid_samples['Frame'].min()} -> {valid_samples['Frame'].max()}")

sample_x = valid_samples["Frame"].to_numpy(dtype=float)
sample_y = valid_samples[metric_col].to_numpy(dtype=float)

# Now check each event Frame
nan_count = 0
ok_count = 0
first_nan_event = None
last_ok_event = None
for idx, row in finished_rows.iterrows():
    cf = row.get("Frame")
    cv = row.get("Value")
    if pd.isna(cf) or pd.isna(cv):
        continue
    val = _interp_or_nan(float(cf), sample_x, sample_y)
    if np.isnan(val):
        nan_count += 1
        if first_nan_event is None:
            first_nan_event = (cv, cf)
    else:
        ok_count += 1
        last_ok_event = (cv, cf)

print(f"\nFor {len(finished_rows)} events:")
print(f"  OK interp: {ok_count}")
print(f"  NaN interp: {nan_count}")
if first_nan_event:
    print(f"  First NaN event: GameObjects={first_nan_event[0]}, Frame={first_nan_event[1]}")
if last_ok_event:
    print(f"  Last OK event:   GameObjects={last_ok_event[0]}, Frame={last_ok_event[1]}")
