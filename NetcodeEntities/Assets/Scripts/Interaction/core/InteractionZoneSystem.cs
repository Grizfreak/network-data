using Unity.Burst;
using Unity.Entities;
using Unity.Mathematics;
using Unity.Rendering;
using Unity.Transforms;

[BurstCompile]
public partial struct InteractionZoneSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        state.RequireForUpdate<InteractionSpawnConfig>();
    }

    public void OnUpdate(ref SystemState state)
    {
        if (!SystemAPI.HasSingleton<InteractionSpawnConfig>())
            return;

        Entity configEntity = SystemAPI.GetSingletonEntity<InteractionSpawnConfig>();
        InteractionSpawnConfig config = state.EntityManager.GetComponentData<InteractionSpawnConfig>(configEntity);

        if (!config.ZoneEnabled)
            return;

        foreach (var (transform, entity) in SystemAPI.Query<RefRO<LocalTransform>>()
            .WithAll<InteractionSpawnedTag>()
            .WithEntityAccess())
        {
            if (entity == config.HoveredEntity || entity == config.DraggedEntity)
                continue;

            float3 position = transform.ValueRO.Position;
            bool inZone = IsPositionInZone(position, config.ZoneMin, config.ZoneMax);

            if (state.EntityManager.HasComponent<URPMaterialPropertyBaseColor>(entity))
            {
                float4 targetColor = inZone ? config.ZoneColor : config.BaseColor;
                state.EntityManager.SetComponentData(entity, new URPMaterialPropertyBaseColor
                {
                    Value = targetColor
                });
            }
        }
    }

    private static bool IsPositionInZone(float3 position, float3 zoneMin, float3 zoneMax)
    {
        return position.x >= zoneMin.x && position.x <= zoneMax.x &&
               position.y >= zoneMin.y && position.y <= zoneMax.y &&
               position.z >= zoneMin.z && position.z <= zoneMax.z;
    }
}
