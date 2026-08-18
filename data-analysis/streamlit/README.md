# Streamlit Benchmark Metrics Viewer

Interactive Streamlit app for exploring the PC/Quest/Godot benchmark
captures under `../data/`: FPS, memory, CPU, GPU, PCAP-derived throughput,
and network RTT/upload/download, plotted either per-frame or per-GameObject
("palier").

Requirements

Install dependencies in your Python environment (preferably a venv):

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

## What it actually does

There is no file-upload widget. On launch the app scans `../data/` for
run folders (`benchmarkPC#N/`, `benchmarkQuest#N/`, ...) via
`data_loader.list_pc_and_quest_folders()` and lets you pick which PC and/or
Quest runs to load ("Select Data to Load"). Everything downstream — pairing,
metrics, plots — operates on whatever runs you selected there.

Rough pipeline, in the order it happens in `app.py`:

1. **Discover + load** — find PC/Quest run folders, read every CSV in the
   selected ones, split into stat files vs. event files
   (`data_loader.load_csv_files_from_folder`).
2. **Auto-pair** — match each stat file to its event file by filename
   semantics + timestamp proximity (`data_loader.auto_pair_files`); you can
   override individual pairings in the "Match stat files to event files"
   expander.
3. **Pick metrics** — only metrics that actually produce a parseable series
   for at least one loaded file are offered (`metrics_engine.get_available_metrics`,
   which calls the real per-metric extractor rather than a second,
   hand-maintained "does this look available" column list).
4. **Line Filter** — a global multiselect (plus one-click presets: Network
   only, PC only, Quest clients, Godot only, ...) that scopes every plot
   below to a chosen subset of runs. In "average across runs" mode the
   dropdown shows one entry per (platform, subsystem, role) group instead
   of one per individual run.
5. **Plot** — `plotting.build_metric_figures()` assembles one Plotly figure
   per selected metric, either as a straight time series or aggregated
   against GameObject-count milestones (`per_gameobject`), optionally
   averaging repeated runs of the same system with min/max spread.

There's also a PCAP conversion toolbox (per-platform expanders) that wraps
`pcap_to_csv.py` / `pcap_to_csv_quest.py` to turn raw `.pcap`/`.pcapng`
captures in a run folder into the bucketed CSVs the rest of the app reads.

## Module layout

`app.py` itself is thin: Streamlit widget wiring and page layout only. The
actual logic lives in four importable, Streamlit-free modules, each usable
(and unit-tested) without running the Streamlit script:

- **`data_loader.py`** / **`metrics_engine.py`** — shared with `../ccl/`
  too (file discovery/pairing/subsystem classification, and metric
  extraction/unit normalization/availability). See `../ccl/README.md` for
  how that pipeline uses them.
- **`label_formatting.py`** — Streamlit-only, but not app.py-only: display-
  label formatting (`short_label`) and role/client-server/run-group
  detection for the quick filters and averaging. Derives its tech-name
  logic directly from `data_loader.py::_CLASSIFICATION_RULES` (via
  `base_tech_label()` / `NETWORKED_TECH_KEYWORDS`) rather than keeping a
  separate list — see "Adding a new benchmark type" below.
- **`plotting.py`** — Streamlit-only: dataset dedup, line-filter expansion,
  and the Plotly figure builders, tied together by `build_metric_figures()`.
  Every input `build_metric_figures()` needs (`stats_files`,
  `selected_metric_keys`, `active_line_filters`, ...) is an explicit keyword
  argument — `app.py` passes its widget-derived values in by name at the
  call site near the bottom of the file, rather than the function reading
  them implicitly off module scope.

`app.py` importing any of these three modules (or `label_formatting.py`/
`plotting.py` importing each other) has no side effects — none of them
scan `../data/`, touch pcap tooling, or call `st.stop()`. Only `app.py`
itself does that, top-to-bottom, as a Streamlit script. This is why the
test suite (below) can exercise `short_label()`, `get_available_metrics()`,
and `build_metric_figures()` directly with synthetic data, instead of
needing the real dataset or a running Streamlit server.

## Adding a new benchmark type

**1. The shared classification** — see
`../ccl/README.md#adding-a-new-benchmark-type` for the full checklist:
`data_loader.py::_CLASSIFICATION_RULES`, `../ccl/subsystem_catalog.py`, then
run `python ../ccl/check_subsystem_coverage.py`. That script checks both the
`ccl/` report registrations *and* (via `streamlit_display_gaps()`) that this
app's `label_formatting.base_tech_label()` still recognizes the new rule —
covering this app's tech-tag and "Network only" quick-filter logic
automatically, since both derive from `_CLASSIFICATION_RULES` rather than
keeping their own list. If the display text should differ from the raw
`subsystem` name (e.g. `_CLASSIFICATION_RULES`'s `"Base-GPU"` shows as
`"Base GPU"` in the UI legend), set that rule's `short_label_tech` field.

**2. Metric columns, if the new benchmark exports data under new column
names** — add the new column name to the relevant candidate list in
`metrics_engine.py`'s `metric_series_from_stats()` (or the `_has_*_columns`
helpers it calls). `get_available_metrics()` calls that same function
directly, so it picks up the new column automatically — there's no second
list to update.

**3. `pc_data_analysis.py` / `quest_data_analysis.py`** — only relevant if
the new benchmark needs different Frame/Time alignment logic for
per-GameObject aggregation than the existing PC/Quest paths already provide
(see `metrics_engine.metric_per_gameobject_series`'s routing).

Adding *more runs* of an existing benchmark type needs none of this — drop a
new folder under `../data/` and it's picked up automatically (see
`../ccl/README.md`'s "Adding a new benchmark type" section for the same
point on the `ccl/` side).

## Tests

Characterization test suites pin the current, real behavior of every
ordered/heuristic matching table in this app against real filenames from
`../data/` (or, for `build_metric_figures()`/`get_available_metrics()`,
small synthetic DataFrames) rather than checking it by eye:

- `classify_subsystem()`, `base_tech_label()`, `NETWORKED_TECH_KEYWORDS`
  (`data_loader.py`) — `tests/test_data_loader.py`
- `short_label()`, `_type_tag_for()`, `_run_group_key()` and friends
  (`label_formatting.py`) — `tests/test_label_formatting.py`
- `_pairing_score()` / `auto_pair_files()` (`data_loader.py`) —
  `tests/test_pairing.py`
- `get_available_metrics()` (`metrics_engine.py`) — `tests/test_metrics_engine.py`
- `build_metric_figures()` and the dataset-dedup helpers (`plotting.py`) —
  `tests/test_plotting.py`

```bash
python -m unittest discover -s tests -v
```
