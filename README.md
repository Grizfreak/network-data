# Unity Network Benchmark Base

This repository contains a Unity benchmark project built around a simple three-phase workload:

1. wait for the scene to initialize and the network layer to be ready,
2. spawn a configurable number of cubes, either all at once or in waves,
3. progressively switch cubes into a moving state while recording timing and profiler data.

The project is split into a local package and a Unity project:

- `com.imt-atlantique.benchmark-base/` contains the runtime package code, scenes, and sample JSON configurations.
- `base/` is the Unity project that consumes that package and contains the generated project files.
    - every network engine used will be based on this project
- `data-analysis/` contains Python scripts for plotting the collected CSV data.

## Architecture

The runtime code is organized into three layers:

- `base.model` defines the data containers used by the benchmark, including `BaseResource`, `ProfilerStats`, and `ProfilerStatsEntry`.
- `base.core` contains the benchmark flow and scene logic:
	- `BaseLauncher` loads the benchmark scene and kicks off phase 1.
	- `PhaseManager` coordinates the three benchmark phases and handles automatic phase chaining.
	- `InstantiateManager` spawns the benchmark objects either all at once or per wave.
	- `MoveManager` gradually marks spawned cubes as moving.
	- `ObjectBehaviour` applies the movement, jump, and rotation behaviour to cubes.
	- `CameraRotate` adjusts the camera orientation on Android.
- `base.profiling` contains logging and profiler export code:
	- `LogsManager` writes phase and spawn/move events to CSV.
	- `ProfilerStatsToCSVExporter` records selected Unity profiler metrics to CSV.
	- `ProfilerManagement` can export the list of available profiler recorder handles for debugging.

The package metadata is defined in `com.imt-atlantique.benchmark-base/package.json`, which declares the package name, Unity version, and sample content.

## Benchmark Flow

The benchmark scene is driven by `PhaseManager` and follows this sequence:

1. `BaseLauncher` loads `Packages/com.imt-atlantique.benchmark-base/Runtime/Scenes/Benchmark.unity`.
2. `PhaseManager` starts phase 1 after the initial delay.
3. Phase 1 acts as the connection/setup window.
4. Phase 2 calls `InstantiateManager.StartSpawning()`.
5. Phase 3 calls `MoveManager.StartMovingCubes()`.
6. Once the final phase finishes, the app waits briefly and exits.

The phase timing values can come from the inspector or from JSON configuration loaded by `BaseLoader`.

## Configuration

`BaseLoader` clones the editable ScriptableObjects at runtime and overwrites them from JSON so the original assets stay unchanged.

On standalone builds, configuration is passed with command-line arguments:

- `--conf-file <path>` loads `Base.json` into `BaseResource`.
- `--conf-profiler <path>` loads `ProfilerStats.json` into `ProfilerStats`.

On Android, the loader looks for the same files in `Application.persistentDataPath/conf_resources/`.

The sample files in `com.imt-atlantique.benchmark-base/Samples~/` show the expected JSON shape.

### Base.json

These fields control the benchmark workload:

- `mAmount`: total number of cubes to spawn.
- `mSpawnOnce`: if `true`, spawn all cubes in a single batch; otherwise spawn by wave.
- `mTimeBeforeEachSpawn`: delay before each spawn step.
- `mNumberPerWave`: number of cubes to spawn per wave.
- `mPercentageMovingCubesPerWave`: percentage of currently static cubes that should start moving each wave.
- `mTimeBeforeMovingCubes`: delay between movement waves.
- `mWaitingPhase1Time`: time spent in phase 1.
- `mWaitBetweenPhases`: delay between phases.
- `mWaitBeforeQuittingApp`: delay before exiting once the test is finished.

### ProfilerStats.json

This file lists the profiler recorder handles that `ProfilerStatsToCSVExporter` should record. Each entry contains:

- `category`
- `name`

The exporter writes the selected values to CSV once per frame.

## Outputs

At runtime, the project writes benchmark data to `Application.persistentDataPath`.

- `LogsManager` creates an event log CSV with columns `Frame,Time,Event,Value`.
- `ProfilerStatsToCSVExporter` creates a profiler CSV with frame time, FPS, and the selected profiler metrics.
- `ProfilerManagement` can export `profiler_handles.json` for discovering available profiler recorder names.

The event names used by the benchmark are:

- `PhaseStarted`
- `PhaseFinished`
- `StartedInstantiation`
- `FinishedInstantiation`
- `StartedMovingLocally`
- `EndedMovingLocally`

## Data Analysis

The `data-analysis/` folder contains Python scripts for plotting benchmark results:

- `plot.py` is geared toward the desktop CSV format.
- `quest_plot.py` is geared toward Quest-style exports.

Install the Python dependencies listed in `data-analysis/requirements.txt`:

```bash
pip install -r data-analysis/requirements.txt
```

Then place the exported CSV files in `data-analysis/results/` and run one of the scripts:

```bash
python plot.py
python quest_plot.py
```

Generated charts are written to `data-analysis/plot_output/`.

## Project Layout

- `base/` - Unity project root.
- `base/Assets/` - project assets and editor-side Unity content.
- `base/Packages/` - package manifest and lock file.
- `com.imt-atlantique.benchmark-base/Runtime/Scenes/` - benchmark scenes.
- `com.imt-atlantique.benchmark-base/Runtime/Scripts/` - runtime code.
- `com.imt-atlantique.benchmark-base/Samples~/` - sample JSON configuration files.
- `data-analysis/` - plotting and post-processing scripts.

## Notes

- The project is designed to benchmark networked or VR-heavy workloads by measuring how the scene behaves across spawning, movement, and profiler capture.
- The current flow is intentionally event-driven so additional systems can subscribe to phase, spawn, and movement events without changing the core managers.
