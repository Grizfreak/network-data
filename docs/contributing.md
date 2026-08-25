# Contributing / Onboarding

End-to-end guide for two kinds of change: adding a new benchmark variant
(a new engine or networking library), and working on the analysis pipeline.
For "how do I run an existing variant", see
[reference.md#running-each-variant-locally](reference.md#running-each-variant-locally).

## Prerequisites

| Tool | Version used in this repo | Where it's pinned |
|---|---|---|
| Unity Editor | `6000.3.7f1` | `ProjectSettings/ProjectVersion.txt` in every Unity project (`base`, `base_GPU`, `base_DOTS`, `ngo`, `fishNet`, `photonFusion`, `NetcodeEntities`) — all seven are locked to the same version |
| Godot | `4.7` | `project.godot`'s `config/features` in `Godot_Benchmark/` and `Godot_Network_Benchmark/` |
| Python | 3.x (dev environment used 3.14 via [uv](https://docs.astral.sh/uv/)) | not pinned in a `requirements.txt`/`pyproject.toml` — `data-analysis/streamlit/requirements.txt` lists packages without versions |

Open a Unity project by pointing Unity Hub at its folder (not via "New
Project" — each folder is already a full project). Same for Godot: open the
existing `project.godot`, don't create a new project.

## Adding a new networking library to the Unity side

There's no scaffolding script for this — clone the closest existing project
and adapt it. "Closest" depends on how the new library is distributed:

- **UPM package** (like NGO's `com.unity.netcode.gameobjects` or Netcode for
  Entities' `com.unity.netcode`): start from `ngo/` or `NetcodeEntities/`.
- **Asset-store / manual import** (like FishNet or Photon Fusion, both
  vendored directly under `Assets/`): start from `fishNet/` or
  `photonFusion/`.

Steps:

1. **Duplicate the closest project folder**, rename it, and open it in
   Unity Hub. `Packages/manifest.json` already has the
   `com.imt-atlantique.benchmark-base` file dependency — leave that as-is,
   it's what gives you the shared phase/spawn/move/CSV-export flow for
   free.
2. **Bring in the new library.** UPM: add its package id/version to
   `Packages/manifest.json` (see `ngo/Packages/manifest.json` or
   `NetcodeEntities/Packages/manifest.json` for the shape). Manual/vendored:
   import its `.unitypackage` or SDK into `Assets/` (see how
   `fishNet/Assets/FishNet/` or `photonFusion/Assets/Photon/` are laid out).
3. **Replace the library-specific scripts.** Every existing networked
   variant has the same script set under `Assets/Scripts/<lib>/core/`
   (`ngo/Assets/Scripts/ngo/core/`, `fishNet/Assets/Scripts/core/`,
   `photonFusion/Assets/Scripts/core/`,
   `NetcodeEntities/Assets/Scripts/core/`):
   - `NetworkLauncher.cs` — exposes `StartServer()` / `StartClient(address)`
     (and usually `StartHost()`) against the new library's connection API.
   - `NetworkLoader.cs` — **keep this file's logic identical across
     variants**: it reads `--server` off
     `System.Environment.GetCommandLineArgs()` and calls
     `NetworkLauncher.Instance.StartServer()` if present, otherwise the
     project defaults to client. This is what lets
     `docs/reference.md`'s "same convention for all four variants" claim
     stay true, and what a runner script (or a human at the command line)
     relies on — don't invent a different flag for the new library.
   - `NetworkInstantiateManager.cs` / `Network*EndLogic.cs` / `PingRPC.cs`
     — wire the shared `base.core` spawn/move/phase flow to the new
     library's object-spawning and RPC APIs.
4. **Config**: either add a `Resources/<Lib>Resource.asset` +
   `Resources/<Lib>Resource.json` sample pair (like `ngo/`'s), or skip the
   project-specific sample and just document that `--conf-file` should
   point at one of the shared samples in the repo-root
   [`Resources/`](../Resources/) (like `fishNet/`/`photonFusion/`/
   `NetcodeEntities/` currently do — see reference.md).
5. **Scenes**: reuse the shared package's
   `Packages/com.imt-atlantique.benchmark-base/Runtime/Scenes/Benchmark.unity`
   (that's what `BaseLauncher` loads) plus your own `base.unity` bootstrap
   scene, matching the existing `Scenes/base.unity` + `Scenes/Benchmark.unity`
   pair.
6. **If the library needs credentials/relay config** (Photon Fusion does —
   see the App ID note in reference.md), document that requirement
   explicitly; don't assume it's obvious from the SDK's own docs.
7. **Add the new project folder to `build_all_versions.ps1`**'s
   `-ProjectFolders` default list so it's covered by the PC+Android build
   sweep.
8. **Register it with the analysis pipeline** — this is the one part that
   already has a proper checklist, don't duplicate it here: follow
   [`ccl/README.md`'s "Adding a new benchmark type"](data-analysis/ccl/README.md#adding-a-new-benchmark-type),
   then run `python data-analysis/ccl/check_subsystem_coverage.py` to
   confirm nothing was missed.

## Adding a new Godot variant

Godot doesn't share code with the Unity `benchmark-base` package (different
engine/language) — `Godot_Benchmark/` (baseline) and
`Godot_Network_Benchmark/` (networked) each carry their own `scripts/`
implementing the same phase/spawn/move/CSV-export flow independently:
`base_launcher.gd`, `base_loader.gd`, `phase_manager.gd`,
`instantiate_manager.gd`, `move_manager.gd`, `logs_manager.gd`,
`profiler_stats_to_csv_exporter.gd`. A new Godot-based variant (a different
Godot multiplayer backend, for instance) should clone
`Godot_Network_Benchmark/` and follow its `server_manager.gd` +
`*BenchmarkProvider.gd` pattern for the networking-specific piece — see
[reference.md](reference.md#godot_network_benchmark) for the CLI convention
it must keep (`server` / `client <ip:port>` positional argument, **not**
the Unity variants' `--server` flag — the two engines deliberately don't
share a convention here, so don't try to unify them without touching both
sides' launcher code).

Whatever the source, keep the output CSV columns and the run-folder naming
convention (`[PC]`/`[Quest]`/`[Godot]` prefix, etc.) consistent with what
`classify_subsystem()` in `data-analysis/streamlit/data_loader.py` expects
— that's the thing that actually ties a new variant's output into the
analysis side; see the `ccl/README.md` checklist linked above.

## Working on the analysis pipeline

`streamlit/` and `ccl/` both have real test suites — run them before
sending a change to a module either one imports (`data_loader.py`,
`metrics_engine.py` especially, since both consumers share those):

```powershell
cd data-analysis\streamlit
python -m unittest discover -s tests -v

cd data-analysis\ccl
python -m unittest discover -s tests -v
```

See [`streamlit/README.md`](data-analysis/streamlit/README.md#tests) (test
suite breakdown) and [`ccl/README.md`](data-analysis/ccl/README.md)'s
"Pipeline B" section (59 tests, no pytest dependency by design) for what
each suite actually pins down.
