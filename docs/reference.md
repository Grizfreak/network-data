# Reference

Implementation-level detail that a first-time reader doesn't need but a
contributor eventually will. See the [root README](../README.md) for the
quick start, [architecture/](architecture/README.md) for the diagrams, and
[data-dictionary.md](data-dictionary.md) for what each metric column means.

## `benchmark-base` package layers

- `base.model` — benchmark data containers (`BaseResource`, `ProfilerStats`,
  `ProfilerStatsEntry`) and JSON loading (`BaseLoader`).
- `base.core` — benchmark flow and scene logic (`BaseLauncher`,
  `PhaseManager`, `InstantiateManager`, `MoveManager`, `ObjectBehaviour`).
- `base.profiling` — CSV and profiler export (`LogsManager`,
  `ProfilerStatsToCsvExporter`, `ProfilerManagement`).

`BaseLoader` supports both standalone and Android configuration loading.

## Benchmark flow

1. `BaseLauncher` loads `Packages/com.imt-atlantique.benchmark-base/Runtime/Scenes/Benchmark.unity`.
2. `PhaseManager` starts phase 1 (setup/connect window).
3. Phase 2 triggers spawning via `InstantiateManager.StartSpawning()`.
4. Phase 3 triggers movement via `MoveManager.StartMovingCubes()`.
5. After the final phase, the application exits after the configured delay.

## Configuration

`BaseLoader` clones scriptable objects at runtime, then applies JSON
overrides.

Standalone arguments:

- `--conf-file <path>` loads `Base.json`.
- `--conf-profiler <path>` loads `ProfilerStats.json` (optional).

Android loading path:

- `Application.persistentDataPath/conf_resources/Base.json`
- `Application.persistentDataPath/conf_resources/ProfilerStats.json`

Sample JSON files are available under `com.imt-atlantique.benchmark-base/Samples~/`.

`Base.json` fields (`BaseResource.cs`), applied via `JsonUtility.FromJsonOverwrite`
so any field omitted from the JSON keeps its ScriptableObject default:

| Field | Meaning |
|---|---|
| `mAmount` | Total number of objects to spawn over the run |
| `mSpawnOnce` | `true`: spawn all `mAmount` objects in one batch; `false`: spawn in waves of `mNumberPerWave` |
| `mTimeBeforeEachSpawn` | Delay (s) between spawn waves (ignored if `mSpawnOnce`) |
| `mNumberPerWave` | Objects spawned per wave (ignored if `mSpawnOnce`) |
| `mPercentageMovingCubesPerWave` | % of spawned objects switched to moving per movement wave |
| `mTimeBeforeMovingCubes` | Delay (s) between movement waves |
| `mWaitingPhase1Time` | Duration (s) of phase 1 (setup/connect window) before spawning starts |
| `mWaitBetweenPhases` | Delay (s) inserted between phase 2 (spawn) and phase 3 (move) |
| `mWaitBeforeQuittingApp` | Delay (s) after phase 3 ends before the application exits |
| `moveAndSpawn` | If `true`, run spawning and movement concurrently instead of as sequential phases (used by the `AcceleratedBase` sample config) |

See [ADR 0003](architecture/decisions/0003-phase-based-workload-shape.md)
for why the workload is phase-based in the first place.

## Building all variants

```powershell
.\build_all_versions.ps1
```

Builds PC + Android for every project passed via `-ProjectFolders` (defaults
to `base`, `base_DOTS`, `base_GPU`, `photonFusion`, `ngo`, `fishNet`,
`NetcodeEntities` — Godot projects are not covered by this script, build
them from the Godot editor). Outputs land in `builds/<project>/` (PC) and
`builds/<project>_android/` (APK).

## Running each variant locally

### The four networked Unity variants (`ngo`, `fishNet`, `photonFusion`, `NetcodeEntities`)

All four share the exact same launcher convention (`NetworkLoader.cs` is
near-identical across the four projects): pass `--server` on the command
line to start headless as server; omit it to start as client. Combine with
`--conf-file` (see [Configuration](#configuration) above) to control the
workload. `build_all_versions.ps1` puts each PC build at
`builds/<project>/benchmark.exe`.

```powershell
# server
.\builds\<project>\benchmark.exe --server --conf-file <path-to-config.json>
# client
.\builds\<project>\benchmark.exe --conf-file <path-to-config.json>
```

- **`ngo/`** has a ready-made runner that does both:
  ```powershell
  .\ngo\Assets\Runners\run-ngo-benchmark.ps1
  ```
  Starts a local server + local client, passing `--conf-file` with
  `ngo/Assets/Resources/NgoResource.json` for the server instance. The
  other three don't have an equivalent runner script yet.
- **`fishNet/`**, **`NetcodeEntities/`** have no project-specific sample
  config — use one of the shared samples at the repo root's
  [`Resources/`](../Resources/) (`NetworkBase.json` is the generic
  networked-workload default) via `--conf-file`.
- **`photonFusion/`** additionally needs a Photon App ID configured in
  `photonFusion/Assets/Photon/Fusion/Resources/PhotonAppSettings.asset`
  (`AppIdFusion` field) — one is already set for development in this repo;
  get your own from the [Photon dashboard](https://dashboard.photonengine.com/)
  if it stops working or you fork the project.

### `Godot_Benchmark/` (baseline, no networking)

Same `--conf-file <path>` convention as the Unity variants (see
[`base_loader.gd`](../Godot_Benchmark/scripts/base_loader.gd)); on Android
it reads from `.../files/conf_resources/Base.json` instead.

### `Godot_Network_Benchmark/`

Different convention — a positional argument, not a flag (see
[`server_manager.gd`](../Godot_Network_Benchmark/scripts/server_manager.gd)):

```powershell
Godot_Network_Benchmark.exe server                   # host (ENet, port 9999)
Godot_Network_Benchmark.exe client 127.0.0.1:9999     # connect to a server
Godot_Network_Benchmark.exe                           # no args -> defaults to host
```

Uses Godot's `ENetMultiplayerPeer` directly (no external relay service).
`WiresharkManager` auto-starts a packet capture on the server as soon as
the first client connects.

## Runtime outputs

Runtime CSV outputs are written under `Application.persistentDataPath`.

- Event CSV from `LogsManager`, columns `Frame,Time,Event,Value`.
- Profiler CSV from `ProfilerStatsToCsvExporter`.
- Optional `profiler_handles.json` export from `ProfilerManagement`.

Main benchmark events:

- `PhaseStarted`
- `PhaseFinished`
- `StartedInstantiation`
- `FinishedInstantiation`
- `StartedMovingLocally`
- `EndedMovingLocally`

## Data analysis workflow

There is no extraction script anymore (an older `extract_data.py` /
`plot.py` pair under `data-analysis/old/` is superseded). The current
workflow:

1. Copy/collect run exports into `data-analysis/data/<run-folder>/`
   (existing folders follow `benchmarkPC#N` / `benchmarkQuest#N`).
2. Explore interactively:
   ```powershell
   cd data-analysis\streamlit
   pip install -r requirements.txt
   streamlit run app.py
   ```
   See [`streamlit/README.md`](data-analysis/streamlit/README.md).
3. Or generate the statistical comparisons and Markdown conclusions:
   ```powershell
   cd data-analysis\ccl
   python analyze_data.py
   python render_conclusions.py
   python render_base_conclusions.py
   ```
   See [`ccl/README.md`](data-analysis/ccl/README.md) for the load-based
   pipeline and how the two pipelines differ.
