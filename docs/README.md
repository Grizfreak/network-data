# Documentation Index

This is the entry point for all documentation in this repository. All
`data-analysis/` documentation — the two pipeline READMEs, the metrics
reference, and the narrative/teaching docs — has been moved here under
[`data-analysis/`](data-analysis/), each file carrying a note pointing back
to the code it describes (the code itself stays in
[`../data-analysis/`](../data-analysis/)). Generated report output
(`conclusions.md`, `conclusions_base.md`) stays next to the CSVs it's
generated alongside, and is linked, not copied.

## Start here

- [Root README](../README.md) — project overview, quick start, contributing.
- [Reference](reference.md) — implementation detail: config flags, benchmark
  flow, CSV/event schema, build/run commands, data-analysis workflow.
- [Data dictionary](data-dictionary.md) — every metric, its raw CSV column(s),
  units, and known caveats (sentinels, the Quest GPU clamp, ...).
- [Contributing / onboarding](contributing.md) — prerequisites, how to add a
  new benchmark variant end-to-end (Unity or Godot side, then the analysis
  side), how to run the test suites.
- [Experimental protocol — quick summary (FR)](protocol/README.md) —
  Markdown lookup for what's measured, the workload parameters, and the
  hardware setup. The formal version is the LaTeX/PDF:
  [FR](protocol/protocole_experimental.tex) / [EN](protocol/protocol_eng.tex)
  (compiled PDFs sit next to the `.tex` sources) — that's what has priority
  if the summary and the PDF ever disagree.

## Architecture

- [Architecture overview](architecture/README.md)
- [C4 — System Context](architecture/c4-context.md)
- [C4 — Container diagram](architecture/c4-container.md)
- [C4 — Components: `benchmark-base`](architecture/c4-component-benchmark-base.md) —
  how the shared package's classes work, and how each variant extends or
  bypasses them.
- [Architecture Decision Records](architecture/decisions/README.md) — why
  one Unity project per library, the shared package, the phase-based
  workload, the two analysis pipelines.

## Benchmark clients (Unity / Godot)

All Unity variants share the [`com.imt-atlantique.benchmark-base`](../com.imt-atlantique.benchmark-base/package.json)
package (benchmark flow, phase management, CSV/profiler export). Per-variant
notes live with each project; only the ones with their own README are listed
—the others are documented collectively in the
[Architecture overview](architecture/README.md#benchmark-client-variants).

- `base/`, `base_GPU/`, `base_DOTS/` — baseline (non-networked) Unity variants.
- `ngo/`, `fishNet/`, `photonFusion/`, `NetcodeEntities/` — one Unity project
  per networking library under test.
- `Godot_Benchmark/`, `Godot_Network_Benchmark/` — Godot baseline and
  networked equivalents.

## Data analysis (`docs/data-analysis/`)

- [`data-analysis/plots.md`](data-analysis/plots.md) — every plot the
  pipeline produces (Streamlit's per-metric chart template, and the 3
  static `generate_paper_figures.py` figures) and what each one shows.
- [`data-analysis/streamlit/README.md`](data-analysis/streamlit/README.md)
  — interactive Streamlit dashboard (module layout, pipeline, tests).
- [`data-analysis/streamlit/Stats.md`](data-analysis/streamlit/Stats.md)
  — statistics/metrics reference used by the dashboard.
- [`data-analysis/ccl/README.md`](data-analysis/ccl/README.md) — the two
  offline analysis pipelines (per-frame and load-based) that produce the
  statistical comparisons and Markdown conclusions.
- [`data-analysis/developer_experience.md`](data-analysis/developer_experience.md)
  — hand-written qualitative comparison (docs, community, learning curve).
- [`data-analysis/LECTURE.md`](data-analysis/LECTURE.md) — teaching
  walkthrough of the data pipeline.
- [`data-analysis/NETWORK_PLOTS_ASSOCIATION_EXPLAINED.md`](data-analysis/NETWORK_PLOTS_ASSOCIATION_EXPLAINED.md)
  — how network metric columns are detected and paired with runs (its
  "unified 3-subplot" framing at the top is stale, see
  [plots.md](data-analysis/plots.md#a-stale-doc-worth-knowing-about)).

Generated (not hand-written, stays with its sibling CSVs, run
`ccl/analyze_data.py` + `render_*.py` to regenerate — see the `ccl/README.md`
above):

- [`../data-analysis/ccl/analysis_results/conclusions.md`](../data-analysis/ccl/analysis_results/conclusions.md)
  and [`conclusions_base.md`](../data-analysis/ccl/analysis_results/base/conclusions_base.md)
  — network libraries vs. base engines.
