# 2. Shared `benchmark-base` UPM package instead of per-project duplication

**Status:** Accepted (retroactive — see [decisions/README.md](README.md))
**Date evidenced:** 2026-04-03 (`c1b20a9`, "modified architecture to match
package like system (beginning work on VR profiling before moving on
network behaviors)")

## Context

[ADR 0001](0001-one-project-per-networking-library.md) put each networking
library in its own Unity project. Left alone, that means `PhaseManager`,
`InstantiateManager`, `MoveManager`, `LogsManager`, and the rest of the
benchmark flow would need to be copy-pasted into every project — with the
near-certainty that a bugfix or metric change in one copy quietly doesn't
make it into the others, silently invalidating any cross-variant comparison.

The commit that did this extraction is explicit about the motivation: it
happened *before* any networking variant existed yet ("beginning work on VR
profiling before moving on network behaviors") — the shared-package split
was made in anticipation of the multi-project structure that came a few
days later ([ADR 0001](0001-one-project-per-networking-library.md),
2026-04-07), not as a refactor after duplication had already caused pain.

## Decision

Move the engine-agnostic benchmark flow (`base.model` / `base.core` /
`base.profiling` — see [reference.md](../../reference.md#benchmark-base-package-layers))
into `com.imt-atlantique.benchmark-base`, a local Unity package
(`Packages/manifest.json`'s `"file:../../com.imt-atlantique.benchmark-base"`
dependency), instead of duplicating the scripts into each project's own
`Assets/`.

## Consequences

- A change to spawn/move/phase logic or CSV export is written once and
  most variants pick it up automatically the next time its project is
  opened/built — this is the property that makes cross-variant
  measurements comparable at all. **Caveat found while writing the
  [component diagram](../c4-component-benchmark-base.md):** this holds for
  `ngo`, `fishNet`, and `photonFusion`, but `NetcodeEntities` overrides
  `PhaseManager` to bridge into its own ECS systems for the actual
  spawn/move mechanics — a shared-package change there can silently *not*
  reach `NetcodeEntities` if it touches logic the override bypasses. Check
  the component diagram before assuming a shared-logic change is uniformly
  applied.
- Every variant's `Scenes/Benchmark.unity` is the *same* scene, loaded
  from the package (`Packages/com.imt-atlantique.benchmark-base/Runtime/Scenes/Benchmark.unity`)
  — a variant's own project only needs a `base.unity` bootstrap scene plus
  its networking-library-specific scripts.
- The package boundary is also the natural place to draw the
  "what's this benchmark actually measuring, independent of networking
  library" line — useful when explaining the methodology (see
  [`docs/protocol/`](../../protocol/)).
- Cost: changes to shared logic have a wider blast radius (every variant),
  so they need to be tested against more than one project before being
  considered safe — there's no automated cross-project test for this today
  (not currently tracked as a formal documentation gap; noting it here
  since it's a real cost of this decision).
