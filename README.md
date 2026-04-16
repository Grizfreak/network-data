# Unity Network Benchmark

This repository contains Unity benchmark projects centered on a three-phase workload:

1. wait for initialization and network readiness,
2. spawn a configurable number of cubes (single batch or waves),
3. progressively switch cubes to moving while recording events and profiler metrics.

The repository is organized around:

- `com.imt-atlantique.benchmark-base/` for shared runtime package code, scenes, and sample configs.
- `base/` for the base Unity project.
- `ngo/` for the NGO Unity project.
- `data-analysis/` for CSV collection and plotting scripts.

## Architecture

Core runtime layers:

- `base.model` provides benchmark data containers (`BaseResource`, `ProfilerStats`, `ProfilerStatsEntry`) and JSON loading (`BaseLoader`).
- `base.core` contains benchmark flow and scene logic (`BaseLauncher`, `PhaseManager`, `InstantiateManager`, `MoveManager`, `ObjectBehaviour`).
- `base.profiling` handles CSV and profiler export (`LogsManager`, `ProfilerStatsToCsvExporter`, `ProfilerManagement`).

`BaseLoader` supports both standalone and Android configuration loading.

## Benchmark Flow

The benchmark scene flow is:

1. `BaseLauncher` loads `Packages/com.imt-atlantique.benchmark-base/Runtime/Scenes/Benchmark.unity`.
2. `PhaseManager` starts phase 1 (setup/connect window).
3. Phase 2 triggers spawning via `InstantiateManager.StartSpawning()`.
4. Phase 3 triggers movement via `MoveManager.StartMovingCubes()`.
5. After the final phase, the application exits after the configured delay.

## Configuration

`BaseLoader` clones scriptable objects at runtime, then applies JSON overrides.

Standalone arguments:

- `--conf-file <path>` loads `Base.json`.
- `--conf-profiler <path>` loads `ProfilerStats.json` (optional).

Android loading path:

- `Application.persistentDataPath/conf_resources/Base.json`
- `Application.persistentDataPath/conf_resources/ProfilerStats.json`

Sample JSON files are available under `com.imt-atlantique.benchmark-base/Samples~/`.

## Build

Use the root script to build both Unity projects for Windows and Android:

```powershell
.\build_all_versions.ps1
```

The script builds `base` and `ngo`, then moves outputs to:

- `builds/base/` (Windows exe)
- `builds/base_android/` (APK)
- `builds/ngo/` (Windows exe)
- `builds/ngo_android/` (APK)

## Running NGO Benchmark

Runner scripts are in `ngo/Assets/Runners/`.

Run local server + local client:

```powershell
.\ngo\Assets\Runners\run-ngo-benchmark.ps1
```

Both scripts pass `--conf-file` with `ngo/Assets/Resources/NgoResource.json` for the server instance.

## Runtime Outputs

Runtime CSV outputs are written under `Application.persistentDataPath`.

- Event CSV from `LogsManager` with columns `Frame,Time,Event,Value`.
- Profiler CSV from `ProfilerStatsToCsvExporter`.
- Optional `profiler_handles.json` export from `ProfilerManagement`.

Main benchmark events:

- `PhaseStarted`
- `PhaseFinished`
- `StartedInstantiation`
- `FinishedInstantiation`
- `StartedMovingLocally`
- `EndedMovingLocally`

## Data Analysis

The Python workflow is in `data-analysis/`.

1. Create/activate the virtual environment.
2. Install dependencies:

```powershell
pip install -r .\data-analysis\requirements.txt
```

3. Collect latest local/Quest CSV files into `data-analysis/data/<timestamp>/`:

```powershell
python .\data-analysis\extract_data.py
```

4. Generate plots from the latest folder in `data-analysis/data/`:

```powershell
python .\data-analysis\plot.py
```

Plots are saved to `data-analysis/results/<timestamp>/`.

## Project Layout

- `base/`: base Unity project.
- `ngo/`: NGO Unity project.
- `com.imt-atlantique.benchmark-base/`: shared package (runtime scripts, scenes, samples).
- `builds/`: consolidated build outputs.
- `data-analysis/`: extraction and plotting scripts.
