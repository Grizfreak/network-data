# Architecture Overview

## What this system is

A benchmark suite that runs the same synthetic workload — spawn N cubes,
progressively make them move, record events and profiler stats — across
several game-engine / networking-library combinations, so the results are
comparable. Each combination is its own standalone project (Unity or Godot);
a Python pipeline turns the exported CSVs into statistics and plots.

## Benchmark client variants

| Project | Engine | Networking | Purpose |
|---|---|---|---|
| `base/` | Unity | none | Baseline, no networking overhead |
| `base_GPU/` | Unity | none | Baseline with GPU-bound workload variant |
| `base_DOTS/` | Unity | none | Baseline using DOTS/ECS |
| `ngo/` | Unity | Netcode for GameObjects | |
| `fishNet/` | Unity | FishNet | |
| `photonFusion/` | Unity | Photon Fusion (relay) | |
| `NetcodeEntities/` | Unity | Netcode for Entities (DOTS) | |
| `Godot_Benchmark/` | Godot | none | Baseline, cross-engine comparison point |
| `Godot_Network_Benchmark/` | Godot | Godot high-level multiplayer | |

All seven Unity projects consume the same
[`com.imt-atlantique.benchmark-base`](../../com.imt-atlantique.benchmark-base/package.json)
package as a local file dependency (`Packages/manifest.json`), so the
benchmark flow, phase management, and CSV/profiler export logic exists once
and is not reimplemented per variant. See [reference.md](../reference.md)
for the package's internal layering (`base.model` / `base.core` /
`base.profiling`).

The Godot projects mirror the same phased workload independently — they
don't share code with the Unity package (different engine/language), only
the CSV output shape and the run naming convention that lets
`classify_subsystem()` in `data-analysis` tell them apart.

## Data flow

1. Each client run writes event + profiler CSVs to
   `Application.persistentDataPath` (standalone) or the Android
   equivalent (see [reference.md#runtime-outputs](../reference.md#runtime-outputs)).
   For network-focused runs, `capture_wireshark.ps1` / manual PCAP capture
   adds a raw traffic trace.
2. Runs are collected (manually, or captured directly) into
   `data-analysis/data/<run-folder>/`; `pcap_to_csv.py` /
   `pcap_to_csv_quest.py` convert PCAP captures into bucketed CSVs.
3. Two independent consumers read `data-analysis/data/`:
   - `data-analysis/streamlit/` — interactive exploration (one dashboard).
   - `data-analysis/ccl/` — offline statistical pipelines that produce
     Markdown conclusions (see its [README](../data-analysis/ccl/README.md)
     for the two-pipeline split and how to register a new benchmark variant).

See the diagrams for the visual version:

- [C4 — System Context](c4-context.md)
- [C4 — Container diagram](c4-container.md)
- [C4 — Components: `benchmark-base`](c4-component-benchmark-base.md) — how
  the shared package's classes work, and the four different strategies
  variants use to extend or bypass them.

For the *why* behind the structure above, see the
[Architecture Decision Records](decisions/README.md).
