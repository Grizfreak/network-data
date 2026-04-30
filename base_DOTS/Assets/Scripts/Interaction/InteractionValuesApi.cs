using Unity.Collections;
using Unity.Entities;

public static class InteractionValuesApi
{
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

    public static bool TryGetValuesById(int id, out InteractionEntityValues values)
    {
        values = default;
        if (!TryGetEntityById(id, out Entity entity))
            return false;

        return TryGetValues(entity, out values);
    }

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
