using Unity.Burst;
using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;
using Unity.Transforms;
using Unity.Rendering;

[BurstCompile]
public partial struct InteractionSpawnSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        state.RequireForUpdate<InteractionSpawnConfig>();
    }

    public void OnUpdate(ref SystemState state)
    {
        Entity configEntity = SystemAPI.GetSingletonEntity<InteractionSpawnConfig>();
        InteractionSpawnConfig config = state.EntityManager.GetComponentData<InteractionSpawnConfig>(configEntity);

        if (config.DespawnRequested)
        {
            var ecb = new EntityCommandBuffer(Allocator.Temp);
            var entitiesToCheck = SystemAPI.QueryBuilder().WithAll<InteractionSpawnedTag>().Build().ToEntityArray(Allocator.Temp);
            foreach (var entity in entitiesToCheck)
            {
                if (config.ZoneEnabled)
                {
                    float3 position = state.EntityManager.GetComponentData<LocalTransform>(entity).Position;
                    if (IsPositionInZone(position, config.ZoneMin, config.ZoneMax))
                    {
                        continue;
                    }
                }
                ecb.DestroyEntity(entity);
            }

            entitiesToCheck.Dispose();

            config.DespawnRequested = false;
            config.HoveredEntity = Entity.Null;
            config.DraggedEntity = Entity.Null;
            config.HoverIndexDirty = true;
            state.EntityManager.SetComponentData(configEntity, config);

            ecb.Playback(state.EntityManager);
            ecb.Dispose();
        }

        if (!config.SpawnRequested || config.NumberToSpawn <= 0)
            return;

        var ecbSpawn = new EntityCommandBuffer(Allocator.Temp);
        Random random = config.Random;
        int nextId = config.NextEntityId;
        bool hasValueOnPrefab = state.EntityManager.HasComponent<InteractionEntityValues>(config.Prefab);

        for (int i = 0; i < config.NumberToSpawn; i++)
        {
            float x = random.NextFloat(config.MinSpawn.x, config.MaxSpawn.x);
            float z = random.NextFloat(config.MinSpawn.z, config.MaxSpawn.z);
            int randomInt = NextIntInclusive(ref random, config.RandomIntMin, config.RandomIntMax);
            float randomFloat = NextFloatInclusive(ref random, config.RandomFloatMin, config.RandomFloatMax);
            int assignedId = nextId++;

            Entity entity = ecbSpawn.Instantiate(config.Prefab);
            ecbSpawn.SetComponent(entity, LocalTransform.FromPosition(new float3(x, config.MinSpawn.y, z)));
            ApplyColor(ref ecbSpawn, state.EntityManager.HasComponent<URPMaterialPropertyBaseColor>(config.Prefab), entity, config.BaseColor);
            ApplyValues(ref ecbSpawn, hasValueOnPrefab, entity, new InteractionEntityValues
            {
                Id = assignedId,
                RandomInt = randomInt,
                RandomFloat = randomFloat
            });
            ecbSpawn.AddComponent<InteractionSpawnedTag>(entity);
        }

        config.Random = random;
        config.NextEntityId = nextId;
        config.SpawnRequested = false;
        config.HoveredEntity = Entity.Null;
        config.DraggedEntity = Entity.Null;
        config.HoverIndexDirty = true;
        state.EntityManager.SetComponentData(configEntity, config);

        ecbSpawn.Playback(state.EntityManager);
        ecbSpawn.Dispose();
    }

    private static void ApplyColor(ref EntityCommandBuffer ecb, bool hasColorComponent, Entity entity, float4 color)
    {
        if (hasColorComponent)
        {
            ecb.SetComponent(entity, new URPMaterialPropertyBaseColor
            {
                Value = color
            });
        }
        else
        {
            ecb.AddComponent(entity, new URPMaterialPropertyBaseColor
            {
                Value = color
            });
        }
    }

    private static void ApplyValues(ref EntityCommandBuffer ecb, bool hasValueComponent, Entity entity, InteractionEntityValues values)
    {
        if (hasValueComponent)
        {
            ecb.SetComponent(entity, values);
        }
        else
        {
            ecb.AddComponent(entity, values);
        }
    }

    private static int NextIntInclusive(ref Random random, int minInclusive, int maxInclusive)
    {
        if (maxInclusive <= minInclusive)
            return minInclusive;

        if (maxInclusive == int.MaxValue)
        {
            uint range = (uint)(maxInclusive - minInclusive);
            return minInclusive + (int)math.min(range, random.NextUInt(range + 1u));
        }

        return random.NextInt(minInclusive, maxInclusive + 1);
    }

    private static bool IsPositionInZone(float3 position, float3 zoneMin, float3 zoneMax)
    {
        return position.x >= zoneMin.x && position.x <= zoneMax.x &&
               position.y >= zoneMin.y && position.y <= zoneMax.y &&
               position.z >= zoneMin.z && position.z <= zoneMax.z;
    }

    private static float NextFloatInclusive(ref Random random, float minInclusive, float maxInclusive)
    {
        if (maxInclusive <= minInclusive)
            return minInclusive;

        return random.NextFloat(minInclusive, maxInclusive);
    }
}