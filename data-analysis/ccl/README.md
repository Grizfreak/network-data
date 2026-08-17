# ccl/ — benchmark analysis pipeline

This folder turns the raw per-run CSV captures under `../data/` into the
statistical comparisons and Markdown conclusions for the benchmark. It is
**two independent pipelines** that share a few common building blocks — they
answer different questions and don't feed into each other.

Both pipelines reuse `../streamlit/data_loader.py` (file discovery, run
pairing, subsystem classification) and `../streamlit/metrics_engine.py`
(metric extraction, unit normalization) rather than re-implementing that
logic — that's why every script does
`sys.path.append(.../streamlit)` before importing them.

## Pipeline A — per-frame analysis (`analyze_data.py` → `render_*.py`)

Pools every per-frame sample of a run into one bucket per (platform,
subsystem, metric) and runs Mann-Whitney U directly on that. Simple and
fast, but frames within a run are autocorrelated and a run can mix multiple
scene loads into one bucket — see the caveats each report calls out, and
Pipeline B below for the fix.

```
analyze_data.py
  reads:  ../data/**/*.csv
  writes: analysis_results/raw_per_file_metrics.csv
          analysis_results/per_folder_subsystem_metrics.csv
          analysis_results/summary_by_subsystem.csv
          analysis_results/statistical_comparisons.csv
          analysis_results/statistical_comparisons_significant.csv
        │
        ├── render_conclusions.py        (network libraries: Photon, NGO,
        │     reads:  analysis_results/*.csv     FishNet, NetcodeEntities,
        │     writes: analysis_results/conclusions.md   Godot Network)
        │
        └── render_base_conclusions.py   (base engines: Godot, Unity base,
              reads:  analysis_results/*.csv        Unity GPU, Unity DOTS)
              writes: analysis_results/base/conclusions_base.md
                      analysis_results/base/*.csv  (filtered copies)
```

Run order matters: `analyze_data.py` must run first, the two `render_*.py`
scripts just filter and format its CSV output and can run in either order
(or independently, any time after) relative to each other.

```bash
cd ccl
python analyze_data.py
python render_conclusions.py
python render_base_conclusions.py
```

### `analyze_data.py`

For every stat file in every `../data/benchmark*/` folder: extracts each
metric's time series, computes descriptive stats (mean/median/p95/p99/std),
runs pairwise Mann-Whitney U + Cliff's delta between subsystems within the
same platform, and writes it all out as CSV. `MIN_SAMPLES_FOR_TEST = 5`
skips pairs too small to test.

### `render_conclusions.py` / `render_base_conclusions.py`

Read the CSVs `analyze_data.py` produced, restrict to a subsystem list
(`LIBS` / `DISPLAY_LIBS`), score "decisive" pairwise wins (p < 0.05 and
effect size ≥ small) into a weighted per-library ranking, and render it as
Markdown. They differ only in *which* subsystems and metrics they scope to
— `render_base_conclusions.py` additionally writes filtered copies of the
CSVs into `analysis_results/base/` so that subset is self-contained.

## Pipeline B — load-based analysis (`load_analysis.py`)

Fixes Pipeline A's two problems by making the unit of observation **one run
at one load level ("palier")**, not one frame: each run's frames are
segmented by how many entities were instantiated at capture time (via the
`FinishedInstantiation` event trail), each segment collapses to one
(median, IQR, n_frames) row, and only *then* are configurations compared —
with N = number of runs, not number of frames. Uses an exact permutation
Mann-Whitney (appropriate for the resulting small per-run N ≤ 10), plus
Holm/Benjamini-Hochberg correction for testing multiple loads at once.

Fully self-contained — reads `../data/` directly, doesn't depend on
`analyze_data.py`'s output.

```bash
cd ccl
python load_analysis.py                     # writes analysis_results/load_based/*.csv
python load_analysis.py --comparisons all --loads 2000 5000 10000 20000
```

Key outputs in `analysis_results/load_based/`: `observations_long.csv` (the
per-run-per-load rows), `test_results.csv` (the pairwise comparisons),
`capacity.csv`/`capacity_headline.csv` (max load each run reached),
`issues.csv` (data-quality flags — coverage gaps, capacity outliers — that
are surfaced, not silently dropped).

Has a real test suite: `python -m unittest discover -s tests -v` (52 tests,
no pytest dependency by design — see `tests/test_load_analysis.py`'s
docstring).

## Shared modules

Three small modules hold logic that both pipelines (or both `render_*.py`
scripts) need, so it's defined once instead of drifting out of sync:

- **`stats_common.py`** — `cliffs_delta()` and `cliffs_delta_effect_size()`
  (Romano et al. 2006 thresholds). Used by both `analyze_data.py` and
  `load_analysis.py`. Their Mann-Whitney *U* implementations stay separate
  on purpose (normal-approximation for large per-frame N vs. exact
  permutation for small per-run N — genuinely different tests for
  genuinely different sample-size regimes).
- **`metrics_catalog.py`** — one canonical `(key, long_label, short_label,
  unit, lower_is_better, description)` per metric. Two label conventions
  are kept as explicit fields rather than derived from one another:
  `long_label` is unit-suffixed (`"CPU (ms)"`) and matches the `metric`
  column text `analyze_data.py` writes into its CSVs — `render_base_conclusions.py`
  depends on that exact text to filter. `short_label` is plain (`"CPU"`)
  and matches `load_analysis.py`'s own, separately-computed CSV exports.
- **`report_common.py`** — the parts of the two Markdown renderers that
  don't vary between them: decisive-win scoring, the overall-ranking and
  per-metric tables, the median table, and the per-library
  strengths/weaknesses section. Each `render_*.py` script keeps its own
  header/methodology/caveats prose and its own subsystem list.

## Other files in `analysis_results/`

- **`developer_experience.md`** — hand-written qualitative notes (docs
  quality, community support, learning curve per library). Not generated
  by any script here; edit it directly.

## Known data caveats worth knowing before trusting a number

- **Quest GPU (ms) clamps at 65.535 ms.** The underlying
  `app_gpu_time_microseconds` column is a 16-bit microsecond counter (max
  65535). During real stalls the true GPU time exceeds that and gets
  truncated instead of reported — confirmed correlated with genuine stalls
  (capped rows average ~2.6 FPS vs. ~29 FPS uncapped), not noise. Hits
  ~75% of Godot-on-Quest samples, ~40-49% of Photon Fusion, ~27-33% of
  Unity base. Nothing in the pipeline filters or flags this (unlike the
  RTT sentinel handling in `../streamlit/metrics_engine.py`), so
  median/p95/max Quest GPU figures for the worst-performing subsystems are
  understated lower bounds, not exact values.
- **`raw_per_file_metrics.csv` isn't byte-reproducible run to run** — a
  couple hundred bytes of wobble between two `analyze_data.py` runs on the
  same data, even with no code changes. The derived statistics
  (`statistical_comparisons*.csv`, `summary_by_subsystem.csv`, and both
  rendered `conclusions*.md`) are unaffected and reproduce exactly, so this
  hasn't been tracked down further.
