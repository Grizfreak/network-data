# The `Interaction` demo scene

`base/`, `base_GPU/`, `base_DOTS/` and `NetcodeEntities/` each ship an
`Interaction.unity` scene, separate from the benchmark scene. It spawns a
batch of cubes into a zone, lets the mouse hover/drag them, and re-colors
cubes that sit inside a second "zone" volume. It is a standalone demo, not
part of the benchmark flow or the CSV/profiler pipeline — no client wires it
into a run. `gpu_ngo` explicitly leaves it untouched (see
[`gpu_ngo/NETWORKING.md`](../../gpu_ngo/NETWORKING.md), "Interaction.unity
was left untouched" note); it is not networked in any variant.

This page documents *how* the feature is implemented in the two variants
whose mechanism differs most from a normal Unity workflow — `base_DOTS`
(ECS) and `base_GPU` (GPU-instanced, no ECS/GameObjects for the cubes).
`base/` implements the same behaviour with ordinary `GameObject`s and
`Physics.Raycast`, and isn't covered here.

## `base_DOTS`: ECS systems over a config singleton

All state lives on one singleton component,
[`InteractionSpawnConfig`](../../base_DOTS/Assets/Scripts/Interaction/InteractionSpawnConfig.cs)
(spawn bounds, colors, hover/drag entity references, a `HoverIndexDirty`
flag, and the request flags `SpawnRequested`/`DespawnRequested` that a
MonoBehaviour UI bridge, `InteractionManager.cs`, sets from button clicks).
Three `ISystem`s read/write it every frame:

- **`InteractionSpawnSystem`** ([source](../../base_DOTS/Assets/Scripts/Interaction/InteractionSpawnSystem.cs)) —
  Burst-compiled. On `SpawnRequested`, instantiates `config.Prefab` via an
  `EntityCommandBuffer`, giving each new entity a random `LocalTransform`,
  an `InteractionEntityValues` (id + random int/float), an
  `InteractionSpawnedTag`, and a `URPMaterialPropertyBaseColor`. On
  `DespawnRequested`, destroys every `InteractionSpawnedTag` entity outside
  the zone (or all of them, if the zone is disabled). Either action sets
  `HoverIndexDirty = true` to force a rebuild of the spatial index below.
- **`InteractionHoverSystem`** ([source](../../base_DOTS/Assets/Scripts/Interaction/InteractionHoverSystem.cs)) —
  *not* Burst-compiled (it touches `Camera.main`/`Mouse.current`, which
  aren't Burst-safe). Maintains its own
  `NativeParallelMultiHashMap<int2, HoverEntry>` spatial hash grid, keyed by
  cell coordinates derived from `config.HoverCellSize`, rebuilt from scratch
  whenever `HoverIndexDirty` is set (after every spawn/despawn). Each frame:
  casts a `Camera.main` ray, intersects it with the horizontal plane at
  `config.HoverPlaneY`, looks up the 3×3 neighborhood of cells around the
  hit point, and does a manual ray/AABB test (`RayIntersectsAabb`) against
  each candidate entity's `LocalTransform` position using
  `config.HoverHalfExtent` as the box half-extent — there is no
  `Physics.Raycast` or collider involved. On mouse-down over a hit entity it
  stores that entity as `config.DraggedEntity` plus a `DragOffset`; while
  dragging, it re-projects the ray onto the plane each frame and writes the
  entity's `LocalTransform` directly (no physics, no RPC). Hover/drag/base
  colors are applied by adding or overwriting the entity's
  `URPMaterialPropertyBaseColor` component.
- **`InteractionZoneSystem`** ([source](../../base_DOTS/Assets/Scripts/Interaction/InteractionZoneSystem.cs)) —
  Burst-compiled. Every frame, for every `InteractionSpawnedTag` entity that
  isn't the currently hovered/dragged one, does an AABB containment test
  against `config.ZoneMin`/`ZoneMax` and sets its
  `URPMaterialPropertyBaseColor` to `ZoneColor` or `BaseColor` accordingly.

Net effect: hover/drag/zone are three independent ECS systems synchronized
only through the shared `InteractionSpawnConfig` singleton and per-entity
components — there is no event system or job-scheduled query graph beyond
Unity's default system ordering.

## `base_GPU`: single MonoBehaviour over a `ComputeBuffer`

`base_GPU` doesn't use ECS or per-cube `GameObject`s at all — cubes are
instances inside one `ComputeBuffer` drawn with
`Graphics.RenderMeshIndirect`, so there is nothing a `Physics.Raycast` or an
ECS query could hit. All interaction logic instead lives in one
843-line MonoBehaviour,
[`InteractionManager.cs`](../../base_GPU/Assets/Scripts/GPUIndirect/Interaction/InteractionManager.cs),
which keeps a CPU-side mirror of the GPU buffer and a hand-rolled spatial
index:

- **CPU mirror** — `instanceArray` (an `InstanceData[]`) shadows the GPU
  `_InstanceDataBuffer` exactly; every write to an instance's position
  updates `instanceArray` first, then calls
  `instanceDataBuffer.SetData(instanceArray, i, i, 1)` to push just that
  slot to the GPU (`UpdateDraggedInstance`, ~line 482).
- **Spatial index** — a uniform grid over the XZ plane, implemented as three
  parallel `int[]` arrays (`gridHead`, `gridNext`, `instanceCellIndex`) —
  a manual linked-list-per-cell structure, rebuilt from `instanceArray` in
  `BuildHoverGridFromInstances` whenever cubes are added/removed or an
  instance leaves the grid's cached bounds. Hover lookup
  (`FindHoveredInstance`) casts a ray from the pointer, intersects a
  `Plane` at the cubes' Y height (`Plane.Raycast`, not `Physics.Raycast`),
  then walks the 3×3 neighborhood of grid cells doing a manual
  bounding-box distance test against `mesh.bounds.extents`.
- **Rendering feedback is push-only, one uniform at a time** — there is no
  per-instance "hovered" flag inside the `ComputeBuffer`/shader data.
  Instead, `SetHoveredInstance`/`PushZoneMaterialState` set global material
  properties every frame: `_HoveredInstance` (an int index),
  `_HoverColor`, `_ZoneColor`, `_ZoneMin`/`_ZoneMax`. The shader is
  expected to compare `instanceID == _HoveredInstance` and to test its own
  world position against the zone bounds to pick a color — none of that
  branching logic lives in this C# file (see the associated shader, not
  covered here).
- **Drag** stores the dragged index in `draggingInstanceIndex` plus a 2D
  `dragPointerOffset`; each frame it recomputes the target XZ position from
  the pointer/plane hit, updates `instanceArray` + grid membership, and
  re-uploads that one slot.
- Spawn/despawn (`SpawnInstances`, `AppendSpawnWave`, `DeleteAllCubes`)
  resize `instanceArray`, grow `instanceDataBuffer` geometrically via
  `EnsureInstanceBufferCapacity`, and rebuild the grid — there's no ECS
  command buffer equivalent; it's a plain array copy-and-replace.

## Comparison

| Aspect | `base_DOTS` | `base_GPU` |
|---|---|---|
| Entity representation | Real ECS entities + components | Rows in a CPU array mirroring a `ComputeBuffer`; no per-cube GameObject or entity |
| Spatial index for hover | `NativeParallelMultiHashMap<int2, HoverEntry>`, rebuilt on a dirty flag | Manual linked-list-per-cell (`gridHead`/`gridNext`/`instanceCellIndex`), rebuilt on spawn/despawn/out-of-bounds |
| Ray/plane math | Manual ray–AABB test against `LocalTransform`, no `Physics.Raycast` | Manual `Plane.Raycast` + bounding-box distance test, no `Physics.Raycast` |
| State ownership | One singleton component (`InteractionSpawnConfig`) read/written by 3 systems | Fields on one MonoBehaviour |
| Visual feedback | Per-entity `URPMaterialPropertyBaseColor` component writes | Global material uniforms (`_HoveredInstance`, `_HoverColor`, `_ZoneColor`) consumed by the shader per-instance |
| Concurrency model | Burst-compiled systems (`InteractionSpawnSystem`, `InteractionZoneSystem`); hover system runs on the main thread (touches `Camera`/`Mouse`) | Entirely main-thread `MonoBehaviour.Update` |
| Networking | None — not wired into `NetcodeEntities`'s netcode either | None — `gpu_ngo` explicitly skips this scene |

## Known gap

Neither variant's `Interaction` scene is networked, and no doc (including
this one) specifies what replicating it would require — e.g. whether
`NetcodeEntities` would need `GhostComponent` on `InteractionSpawnConfig`'s
fields and an RPC for drag-start/drag-end, or whether `gpu_ngo` would need
to fold instance mutations into its whole-buffer snapshot. Treat this scene
as a rendering/ECS demo only, not a networking reference.
