# 3. Three-phase workload (setup → spawn → move)

**Status:** Accepted (retroactive — see [decisions/README.md](README.md))
**Date evidenced:** 2026-03-30 (`91487be`, "Added phase system and logic -
Modified instantiation to be by waves or fully once - Added timestamped
events to record the start timing of each phase system - Added moving
system for cubes")

## Context

The earliest version of the benchmark (`decc39d`, `91487ba`'s parent) just
spawned a fixed set of objects and ran. `91487be` restructured that into
`PhaseManager` driving three distinct, timestamped phases — see
[reference.md#benchmark-flow](../../reference.md#benchmark-flow) for the
current implementation (`BaseLauncher` → `PhaseManager` phase 1 → phase 2
`InstantiateManager.StartSpawning()` → phase 3
`MoveManager.StartMovingCubes()`).

## Decision

Split the workload into three explicit, separately-timestamped phases
instead of one continuous scenario:

1. **Setup/connect** — wait for initialization and (for networked variants)
   connection readiness, before any load is applied.
2. **Spawn** — instantiate a configurable number of objects, either as a
   single batch or in waves (`mSpawnOnce`, `mNumberPerWave` in
   [`Base.json`](../../../com.imt-atlantique.benchmark-base/Samples~/Base.json)-style
   configs — see [data-dictionary.md](../../data-dictionary.md) and
   [reference.md#configuration](../../reference.md#configuration)).
3. **Move** — progressively switch spawned objects to moving, again
   optionally in waves, while the object count keeps growing.

Each phase emits a `PhaseStarted`/`PhaseFinished` event pair (plus
`StartedInstantiation`/`FinishedInstantiation` and
`StartedMovingLocally`/`EndedMovingLocally` inside them — see
[reference.md#runtime-outputs](../../reference.md#runtime-outputs)), so
downstream analysis can attribute a metric sample to a specific phase and
load level rather than only to "the run" as a whole.

## Consequences

- **This is what makes the load-based analysis pipeline possible at all.**
  `ccl/load_analysis.py` segments each run by
  "how many entities were instantiated at capture time" using the
  `FinishedInstantiation` event trail (see
  [`ccl/README.md`](../../data-analysis/ccl/README.md#pipeline-b--load-based-analysis-load_analysispy))
  — without phase boundaries and wave-level events, there would be no way
  to isolate "the system at N objects" from "the system averaged over the
  whole run."
- Spawning and moving are deliberately separate phases (not spawn-and-move
  simultaneously) so CPU/GPU/network cost from instantiation doesn't get
  conflated with the cost of ongoing movement/replication in the same
  sample window — a networking library that's cheap to spawn into but
  expensive to keep synchronized (or vice versa) would otherwise average
  out to a misleading single number.
- Cost: three phases (plus wave subdivisions within spawn/move) is more
  configuration surface than a single "just run it" scenario — see
  [reference.md#configuration](../../reference.md#configuration) for what
  each config field controls, since it's not self-evident from the field
  names alone (`mAmount`, `mNumberPerWave`,
  `mPercentageMovingCubesPerWave`, ...).
