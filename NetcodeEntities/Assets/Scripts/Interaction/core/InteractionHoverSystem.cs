using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;
using Unity.Rendering;
using Unity.Transforms;
using UnityEngine;
using UnityEngine.InputSystem;
using Unity.Burst;

/// <summary>Handles mouse hover and drag for spawned interaction entities: maintains a spatial grid to find the entity under the cursor, applies hover/drag colors, and moves the dragged entity along the ground plane.</summary>
[BurstCompile]
public partial struct InteractionHoverSystem : ISystem
{
    private struct HoverEntry
    {
        public Entity Entity;
        public float3 Position;
    }

    // Spatial hash grid of spawned entities, keyed by cell coordinates, so hover picking only has
    // to check nearby cells instead of every spawned entity every frame.
    private NativeParallelMultiHashMap<int2, HoverEntry> hoverMap;

    public void OnCreate(ref SystemState state)
    {
        state.RequireForUpdate<InteractionSpawnConfig>();
        hoverMap = new NativeParallelMultiHashMap<int2, HoverEntry>(1024, Allocator.Persistent);
    }

    public void OnDestroy(ref SystemState state)
    {
        if (hoverMap.IsCreated)
        {
            hoverMap.Dispose();
        }
    }

    public void OnUpdate(ref SystemState state)
    {
        if (!TryGetConfig(ref state, out Entity configEntity, out InteractionSpawnConfig config))
            return;

        if (Mouse.current == null)
            return;

        Camera camera = Camera.main;
        if (camera == null)
            return;

        Ray ray = camera.ScreenPointToRay(Mouse.current.position.ReadValue());

        if (config.DraggedEntity != Entity.Null)
        {
            UpdateDraggedEntity(ref state, ref config, configEntity, ray);
            return;
        }

        if (Mouse.current.leftButton.wasPressedThisFrame)
        {
            // A press can start a drag even while the hover index is stale/empty, since
            // TryGetHoveredEntity reads directly from the (possibly outdated) grid built so far.
            if (TryGetHoveredEntity(ray, config, out Entity pressedEntity) && pressedEntity != Entity.Null)
            {
                StartDrag(ref state, ref config, configEntity, pressedEntity, ray);
                return;
            }
        }

        if (config.HoverIndexDirty)
        {
            RebuildHoverIndex(ref state, configEntity, ref config);
        }

        if (!hoverMap.IsCreated || hoverMap.Count() == 0)
            return;

        if (!TryGetHoveredEntity(ray, config, out Entity hoveredEntity))
        {
            hoveredEntity = Entity.Null;
        }

        if (Mouse.current.leftButton.wasPressedThisFrame && hoveredEntity != Entity.Null)
        {
            StartDrag(ref state, ref config, configEntity, hoveredEntity, ray);
            return;
        }

        if (hoveredEntity == config.HoveredEntity)
            return;

        ApplyColor(ref state, config.HoveredEntity, config.BaseColor);
        ApplyColor(ref state, hoveredEntity, config.HoverColor);

        config.HoveredEntity = hoveredEntity;
        state.EntityManager.SetComponentData(configEntity, config);
    }

    // Begins dragging the given entity, capturing its offset from the ray hit point so it doesn't
    // snap to the cursor on the first frame of the drag.
    private void StartDrag(ref SystemState state, ref InteractionSpawnConfig config, Entity configEntity, Entity draggedEntity, Ray ray)
    {
        if (draggedEntity == Entity.Null || !state.EntityManager.Exists(draggedEntity))
            return;

        float3 currentPosition = state.EntityManager.GetComponentData<LocalTransform>(draggedEntity).Position;
        float3 hitPoint = ProjectRayToPlane(ray, config.HoverPlaneY, currentPosition);

        config.DraggedEntity = draggedEntity;
        config.DragOffset = currentPosition - hitPoint;
        config.HoveredEntity = draggedEntity;
        ApplyColor(ref state, draggedEntity, config.DragColor);
        state.EntityManager.SetComponentData(configEntity, config);
    }

    // Moves the currently dragged entity to follow the cursor along the hover plane, and releases
    // it when the mouse button is let go or the entity was destroyed mid-drag.
    private void UpdateDraggedEntity(ref SystemState state, ref InteractionSpawnConfig config, Entity configEntity, Ray ray)
    {
        Entity draggedEntity = config.DraggedEntity;
        if (draggedEntity == Entity.Null || !state.EntityManager.Exists(draggedEntity))
        {
            config.DraggedEntity = Entity.Null;
            config.HoverIndexDirty = true;
            state.EntityManager.SetComponentData(configEntity, config);
            return;
        }

        if (Mouse.current.leftButton.wasReleasedThisFrame)
        {
            ApplyColor(ref state, draggedEntity, config.BaseColor);
            config.DraggedEntity = Entity.Null;
            config.HoverIndexDirty = true;
            state.EntityManager.SetComponentData(configEntity, config);
            return;
        }

        float3 currentPosition = state.EntityManager.GetComponentData<LocalTransform>(draggedEntity).Position;
        float3 hitPoint = ProjectRayToPlane(ray, config.HoverPlaneY, currentPosition);
        float3 targetPosition = hitPoint + config.DragOffset;
        targetPosition.y = config.HoverPlaneY;

        state.EntityManager.SetComponentData(draggedEntity, LocalTransform.FromPosition(targetPosition));
    }

    // Intersects the ray with the horizontal hover plane, falling back to fallbackPosition when
    // the ray is (near) parallel to the plane or the plane is behind the camera.
    private static float3 ProjectRayToPlane(Ray ray, float planeY, float3 fallbackPosition)
    {
        if (math.abs(ray.direction.y) < 0.0001f)
            return fallbackPosition;

        float distance = (planeY - ray.origin.y) / ray.direction.y;
        if (distance < 0f)
            return fallbackPosition;

        float3 hitPoint = ray.origin + ray.direction * distance;
        hitPoint.y = planeY;
        return hitPoint;
    }

    private bool TryGetConfig(ref SystemState state, out Entity configEntity, out InteractionSpawnConfig config)
    {
        configEntity = Entity.Null;
        config = default;

        if (!SystemAPI.HasSingleton<InteractionSpawnConfig>())
            return false;

        configEntity = SystemAPI.GetSingletonEntity<InteractionSpawnConfig>();
        config = state.EntityManager.GetComponentData<InteractionSpawnConfig>(configEntity);
        return true;
    }

    // Rebuilds the spatial hash grid from all currently spawned entities; called only when
    // HoverIndexDirty is set (after a spawn/despawn) rather than every frame.
    private void RebuildHoverIndex(ref SystemState state, Entity configEntity, ref InteractionSpawnConfig config)
    {
        hoverMap.Clear();

        int spawnedCount = 0;
        foreach (var (transform, entity) in SystemAPI.Query<RefRO<LocalTransform>>().WithAll<InteractionSpawnedTag>().WithEntityAccess())
        {
            float3 position = transform.ValueRO.Position;
            int2 cell = GetCell(position, config);
            hoverMap.Add(cell, new HoverEntry
            {
                Entity = entity,
                Position = position
            });
            spawnedCount++;
        }

        if (hoverMap.Capacity < math.max(1024, spawnedCount))
        {
            // Grow ahead of the current count to reduce the frequency of costly reallocations
            // as more entities get spawned.
            hoverMap.Capacity = math.max(1024, spawnedCount);
        }

        config.HoverIndexDirty = false;
        state.EntityManager.SetComponentData(configEntity, config);
    }

    // Finds the closest entity whose AABB the ray intersects, searching only the 3x3 block of
    // grid cells around the ray's plane hit point rather than the whole hover map.
    private bool TryGetHoveredEntity(Ray ray, in InteractionSpawnConfig config, out Entity hoveredEntity)
    {
        hoveredEntity = Entity.Null;

        if (math.abs(ray.direction.y) < 0.0001f)
            return false;

        float distanceToPlane = (config.HoverPlaneY - ray.origin.y) / ray.direction.y;
        if (distanceToPlane < 0f)
            return false;

        float3 hitPoint = ray.origin + ray.direction * distanceToPlane;
        int2 centerCell = GetCell(hitPoint, config);

        float bestDistance = float.MaxValue;
        bool found = false;

        for (int offsetZ = -1; offsetZ <= 1; offsetZ++)
        {
            for (int offsetX = -1; offsetX <= 1; offsetX++)
            {
                int2 cell = centerCell + new int2(offsetX, offsetZ);
                if (!hoverMap.TryGetFirstValue(cell, out HoverEntry entry, out NativeParallelMultiHashMapIterator<int2> iterator))
                    continue;

                do
                {
                    if (RayIntersectsAabb(ray, entry.Position, config.HoverHalfExtent, out float hitDistance) && hitDistance < bestDistance)
                    {
                        bestDistance = hitDistance;
                        hoveredEntity = entry.Entity;
                        found = true;
                    }
                }
                while (hoverMap.TryGetNextValue(out entry, ref iterator));
            }
        }

        return found;
    }

    // Converts a world position to its hash grid cell using config.HoverCellSize.
    private int2 GetCell(float3 position, in InteractionSpawnConfig config)
    {
        float cellSize = math.max(0.01f, config.HoverCellSize);
        int cellX = (int)math.floor((position.x - config.MinSpawn.x) / cellSize);
        int cellZ = (int)math.floor((position.z - config.MinSpawn.z) / cellSize);
        return new int2(cellX, cellZ);
    }

    // Standard slab-method ray/AABB intersection test.
    private static bool RayIntersectsAabb(Ray ray, float3 center, float halfExtent, out float hitDistance)
    {
        float3 min = center - new float3(halfExtent);
        float3 max = center + new float3(halfExtent);

        float tMin = 0f;
        float tMax = float.MaxValue;

        if (!AxisIntersection(ray.origin.x, ray.direction.x, min.x, max.x, ref tMin, ref tMax))
        {
            hitDistance = 0f;
            return false;
        }

        if (!AxisIntersection(ray.origin.y, ray.direction.y, min.y, max.y, ref tMin, ref tMax))
        {
            hitDistance = 0f;
            return false;
        }

        if (!AxisIntersection(ray.origin.z, ray.direction.z, min.z, max.z, ref tMin, ref tMax))
        {
            hitDistance = 0f;
            return false;
        }

        hitDistance = tMin;
        return tMax >= 0f && tMax >= tMin;
    }

    // Narrows [tMin, tMax] against a single axis' slab; used by RayIntersectsAabb for each of x/y/z.
    private static bool AxisIntersection(float origin, float direction, float min, float max, ref float tMin, ref float tMax)
    {
        if (math.abs(direction) < 0.000001f)
            // Ray is parallel to this axis' slab: it only intersects if the origin already lies within it.
            return origin >= min && origin <= max;

        float inverseDirection = 1f / direction;
        float t1 = (min - origin) * inverseDirection;
        float t2 = (max - origin) * inverseDirection;

        if (t1 > t2)
        {
            (t1, t2) = (t2, t1);
        }

        tMin = math.max(tMin, t1);
        tMax = math.min(tMax, t2);
        return tMax >= tMin;
    }

    // Sets the entity's base color, adding the material property component if it isn't present yet.
    private static void ApplyColor(ref SystemState state, Entity entity, float4 color)
    {
        if (entity == Entity.Null || !state.EntityManager.Exists(entity))
            return;

        if (state.EntityManager.HasComponent<URPMaterialPropertyBaseColor>(entity))
        {
            state.EntityManager.SetComponentData(entity, new URPMaterialPropertyBaseColor
            {
                Value = color
            });
        }
        else
        {
            state.EntityManager.AddComponentData(entity, new URPMaterialPropertyBaseColor
            {
                Value = color
            });
        }
    }
}