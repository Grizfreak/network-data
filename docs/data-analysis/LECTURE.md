# Lecture Notes: Benchmark Metrics Viewer

> This document lives under `docs/`; the code it describes is in
> [`data-analysis/`](../../data-analysis/).

This file contains a concise, classroom-friendly walkthrough of the
project's data flow, the role of each module, and teaching pointers you
can use to explain the implementation to students or colleagues.

## Overview

The project processes Unity benchmark exports and visualizes them in a
lightweight Streamlit UI. Data flows from CSV files (stats and events)
through normalization and metric extraction to Plotly figures.

Files of interest:

- `data-analysis/streamlit/app.py`
  - UI and orchestration. Shows how to bind file selection and user
    controls to a data-processing pipeline. Demonstrates session state
    usage for preserving selections across re-renders.

- `data-analysis/streamlit/data_loader.py`
  - File discovery and normalization. Key teaching points:
    - Normalizing column names early simplifies downstream code.
    - Semantic pairing of stat/event files balances filename cues and
      timestamp proximity; explain trade-offs between strict vs loose
      pairing.

- `data-analysis/streamlit/metrics_engine.py`
  - Metric extraction and series construction. Key teaching points:
    - Keep extraction deterministic and side-effect free.
    - Support multiple compatible column names (PC vs Quest) using a
      small "candidates" mapping strategy.
    - Provide both per-frame time series and per-GameObject aggregated
      series (using event traces) so plots can compare different
      perspectives.

- `data-analysis/pcap_to_csv.py`
  - Converts PCAP/PCAPNG into per-second buckets. Important note:
    - Per-second buckets are rates (non-monotonic). The code now also
      emits cumulative totals (monotonic) for easier comparison with
      event-based aggregations.

- `data-analysis/streamlit/pc_data_analysis.py` and `data-analysis/streamlit/quest_data_analysis.py`
  - Platform-specific adjustments: unit conversions, time-base
    differences, and interpolation strategies for mapping events to
    stats samples.

## Teaching flow (suggested)

1. Start with `data_loader.py`: show how to make messy CSV files
   predictable by renaming columns and detecting file types.
2. Move to `metrics_engine.py`: demonstrate how metric columns are
   located, normalized, and converted to consistent pandas DataFrames.
3. Cover `data-analysis/pcap_to_csv.py`: discuss rate vs cumulative measures and why
   both are useful.
4. Walk through key functions in `metrics_engine.py` (slide-ready):

### `metric_series_from_stats(df, metric_key, stat_name, x_axis_mode)`
- Purpose: map a raw stats DataFrame into a consistent (X, Y) series
  for plotting. Returns `(DataFrame, ycol)` or `(None, None)` if
  unavailable.
- Teaching points: handling multiple possible column names,
  unit-conversion, and choosing a canonical output column name.

### `_pcap_per_gameobject_series(stats_df, events_df, metric_key, stat_name)`
- Purpose: convert PCAP time series into `(GameObjects, Average<metric>)`
  pairs using `FinishedInstantiation` events.
- Teaching points: aligning by Frame vs Time, handling different time
  scales, and the choice of representative sample (last sample vs mean).

### `build_datasets(...)`
- Purpose: orchestrate per-file decisions—per-frame vs per-GameObject,
  pairing, fallback behavior—and produce a list of labeled DataFrames
  ready for plotting in the UI.
- Teaching points: separation of concerns (parsing vs orchestration),
  and why the function collects warnings for the UI.

4. Show `data-analysis/streamlit/app.py` to tie things together: user controls,
   plotting, and session-state handling.
5. Optionally, use `LECTURE.md` as handout material for students.

## Dispatch mapping

If you want to extract a short commentary about a file for a
presentation, use these snippets:

- `data_loader.py`: "Normalizes filenames and CSV columns so the rest
  of the pipeline can assume canonical column names: Frame, Time,
  Event, Value." 

- `metrics_engine.py`: "Pure functions that map CSVs to chart-ready
  series and per-GameObject aggregates. Designed to be re-entrant and
  testable."

- `pcap_to_csv.py`: "Shows how to bucket packet captures into fixed
  time windows and compute both rates and cumulative totals."

## Notes on reproducibility and exercises

- Exercise: regenerate PCAP CSVs and compare 'BytesPerSec' vs
  'CumulativeBytes' to observe why per-second rates can appear to drop
  even while totals rise.
- Exercise: change the pairing strictness option in the UI and show
  how pairings change for ambiguous filenames.

---

These notes are intentionally concise; if you want a longer slide
script or expanded walk-through per function, tell me which file or
function to expand and I will produce a lecture-ready section.
