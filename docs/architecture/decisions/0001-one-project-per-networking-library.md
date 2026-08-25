# 1. One Unity project per networking library

**Status:** Accepted (retroactive — see [decisions/README.md](README.md))
**Date evidenced:** 2026-04-07 (`b79cd21`, "added new project for ngo debut")

## Context

The benchmark needs to run the same workload across several networking
libraries (NGO, FishNet, Photon Fusion, Netcode for Entities) plus
non-networked baseline variants (`base`, `base_GPU`, `base_DOTS`). Unity
offers at least two ways to organize that:

- **One project per library** (what this repo does): `ngo/`, `fishNet/`,
  `photonFusion/`, `NetcodeEntities/`, each a fully independent Unity
  project with its own `Packages/manifest.json`.
- **One project, one scene/assembly per variant**: a single Unity project
  where each networking library lives behind its own scene and assembly
  definition, switched at build time.

## Decision

One Unity project per networking library.

## Consequences

**Why this was the right call here:**

- **Dependency isolation.** Each networking library brings its own package
  or vendored SDK (see
  [`docs/contributing.md`](../../contributing.md#adding-a-new-networking-library-to-the-unity-side)
  for the UPM-vs-vendored split across NGO/NetcodeEntities vs
  FishNet/PhotonFusion) — some of these are large, some pull in their own
  transitive dependencies, and Unity has no first-class way to make a
  package conditional on which "variant" is active in a single project.
  Combining them into one project risks version conflicts and bloats every
  build with every library's assets, even the ones not being benchmarked.
- **Build isolation.** `build_all_versions.ps1` builds each project
  independently and moves the result to `builds/<project>/`; a build
  failure in one library's project (a common occurrence when SDKs update)
  doesn't block building or running the others.
- **Comparable results depend on shared code.** Since every project
  references the same
  [`com.imt-atlantique.benchmark-base`](0002-shared-benchmark-base-package.md)
  package, the benchmark logic (spawn/move/phase/CSV export) is identical
  by default across variants, with the networking-library-specific glue
  confined to each project's own `Scripts/<lib>/core/`. That said, "by
  default" isn't "always" — see the
  [component diagram](../c4-component-benchmark-base.md) for how far each
  variant actually deviates (`NetcodeEntities` overrides more of the shared
  flow than the others).

**What it costs:**

- Adding a new variant means creating (or cloning) a whole Unity project,
  not just a new scene — see
  [`docs/contributing.md`](../../contributing.md#adding-a-new-networking-library-to-the-unity-side)
  for the actual checklist this implies.
- No single Unity Editor session can have two variants open at once for
  side-by-side debugging.
- Shared non-package code (if any accidentally creeps in outside
  `benchmark-base`) has to be manually kept in sync across projects — this
  is why [ADR 0002](0002-shared-benchmark-base-package.md) exists as a
  companion decision.
