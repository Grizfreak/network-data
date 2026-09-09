using Unity.Collections;
using Unity.Entities;

/// <summary>Read-only lookup helpers for querying InteractionEntityValues from outside ECS systems (e.g. UI code).</summary>
public static class InteractionValuesApi
{
    /// <summary>Gets the InteractionEntityValues attached to the given entity, if it exists and has the component.</summary>
    public static bool TryGetValues(Entity entity, out InteractionEntityValues values)
    {
        values = default;

        if (!TryGetEntityManager(out EntityManager entityManager))
            return false;

        if (!entityManager.Exists(entity) || !entityManager.HasComponent<InteractionEntityValues>(entity))
            return false;

        values = entityManager.GetComponentData<InteractionEntityValues>(entity);
        return true;
    }

    /// <summary>Gets the InteractionEntityValues for the spawned entity with the given Id.</summary>
    public static bool TryGetValuesById(int id, out InteractionEntityValues values)
    {
        values = default;
        if (!TryGetEntityById(id, out Entity entity))
            return false;

        return TryGetValues(entity, out values);
    }

    /// <summary>Linearly scans all spawned entities to find the one whose InteractionEntityValues.Id matches.</summary>
    public static bool TryGetEntityById(int id, out Entity entity)
    {
        entity = Entity.Null;

        if (!TryGetEntityManager(out EntityManager entityManager))
            return false;

        EntityQuery query = entityManager.CreateEntityQuery(
            ComponentType.ReadOnly<InteractionSpawnedTag>(),
            ComponentType.ReadOnly<InteractionEntityValues>());

        NativeArray<Entity> entities = query.ToEntityArray(Allocator.Temp);
        NativeArray<InteractionEntityValues> values = query.ToComponentDataArray<InteractionEntityValues>(Allocator.Temp);

        for (int i = 0; i < values.Length; i++)
        {
            if (values[i].Id == id)
            {
                entity = entities[i];
                entities.Dispose();
                values.Dispose();
                return true;
            }
        }

        entities.Dispose();
        values.Dispose();
        return false;
    }

    /// <summary>Gets the InteractionEntityValues of the entity currently hovered, as tracked by InteractionSpawnConfig.HoveredEntity.</summary>
    public static bool TryGetHoveredValues(out InteractionEntityValues values)
    {
        values = default;

        if (!TryGetEntityManager(out EntityManager entityManager))
            return false;

        EntityQuery configQuery = entityManager.CreateEntityQuery(ComponentType.ReadOnly<InteractionSpawnConfig>());
        if (!configQuery.HasSingleton<InteractionSpawnConfig>())
            return false;

        Entity configEntity = configQuery.GetSingletonEntity();
        InteractionSpawnConfig config = entityManager.GetComponentData<InteractionSpawnConfig>(configEntity);

        if (config.HoveredEntity == Entity.Null)
            return false;

        return TryGetValues(config.HoveredEntity, out values);
    }

    private static bool TryGetEntityManager(out EntityManager entityManager)
    {
        entityManager = default;

        World world = World.DefaultGameObjectInjectionWorld;
        if (world == null || !world.IsCreated)
            return false;

        entityManager = world.EntityManager;
        return true;
    }
}
