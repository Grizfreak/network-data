# 4. Two independent statistical pipelines instead of one

**Status:** Accepted
**Note:** unlike the other three ADRs in this log, this one isn't purely
reconstructed after the fact — the reasoning is already written out in
[`ccl/README.md`](../../data-analysis/ccl/README.md); this ADR mainly
promotes it to a decision record so it's discoverable from the
architecture docs, not only from inside `ccl/`.

## Context

`ccl/` needs to answer "is library X faster than library Y" with an actual
statistical test, not just eyeballing a chart. The natural unit of
observation for that test is ambiguous: a run produces thousands of
per-frame samples, but the runs themselves (not the frames) are what's
actually independent of each other.

**Pipeline A** (`analyze_data.py` → `render_conclusions.py` /
`render_base_conclusions.py`) pools every per-frame sample of a run into
one bucket per (platform, subsystem, metric) and runs Mann-Whitney U
directly on that. It's simple and fast, but has two real problems:
frames within a run are autocorrelated (consecutive frames aren't
independent samples), and a run can mix multiple load levels into one
bucket, diluting a comparison that's only true at high load.

## Decision

Keep Pipeline A (it's cheap, already-shipped, and useful for a quick
overview) **and** add a second, statistically stricter pipeline instead of
trying to fix Pipeline A's sampling unit in place.

**Pipeline B** (`load_analysis.py`) makes the unit of observation **one run
at one load level ("palier")**: each run's frames are segmented by how many
entities were instantiated at capture time (via the `FinishedInstantiation`
event trail — see [ADR 0003](0003-phase-based-workload-shape.md)), each
segment collapses to one `(median, IQR, n_frames)` row, and only *then* are
configurations compared, with N = number of runs (≤ 10), not number of
frames. It uses an exact permutation Mann-Whitney (appropriate for that
small N) plus Holm/Benjamini-Hochberg correction for testing multiple load
levels at once — see
[`ccl/README.md`'s "Pipeline B"](../../data-analysis/ccl/README.md#pipeline-b--load-based-analysis-load_analysispy)
for the full method.

## Consequences

- The two pipelines **answer different questions and don't feed into each
  other** — Pipeline B is fully self-contained, reading `data-analysis/data/`
  directly rather than depending on Pipeline A's CSV output. Anyone citing
  a result needs to say which pipeline it came from; a p-value from
  Pipeline A and one from Pipeline B for "the same" comparison aren't
  interchangeable (different N, different autocorrelation assumptions).
- Both pipelines share the same lookup tables
  (`metrics_catalog.py`, `subsystem_catalog.py`) so a metric or subsystem
  only needs to be registered once — see
  [`ccl/README.md`'s "Adding a new benchmark type"](../../data-analysis/ccl/README.md#adding-a-new-benchmark-type).
- Pipeline B has a real test suite (59 tests); Pipeline A doesn't have an
  equivalent one yet — treat conclusions rendered from Pipeline B's output
  as the more defensible of the two when they disagree.
