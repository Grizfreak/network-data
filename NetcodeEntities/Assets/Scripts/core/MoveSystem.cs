using Unity.Burst;
using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;
using UnityEngine;

[BurstCompile]
public partial struct MoveSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        state.RequireForUpdate<BenchmarkConfig>();
        state.RequireForUpdate<StaticTag>();
    }

    public void OnUpdate(ref SystemState state)
    {
        var config = SystemAPI.GetSingletonRW<BenchmarkConfig>();

        // Phase 3 not started yet
        if (!config.ValueRO.StartMove)
            return;
        
        // ---------------------------------
        // First-time initialization
        // ---------------------------------

        if (!config.ValueRO.MoveInitialized)
        {
            int totalStatic =
                SystemAPI.QueryBuilder()
                    .WithAll<StaticTag>()
                    .Build()
                    .CalculateEntityCount();
            
            int totalMoving =
                SystemAPI.QueryBuilder()
                    .WithAll<MovingTag>()
                    .Build()
                    .CalculateEntityCount();

            config.ValueRW.RemainingToMove = totalStatic;

            config.ValueRW.MoveTimer =
                config.ValueRO.TimeBeforeMoving;

            config.ValueRW.MoveInitialized = true;
        }

        // ---------------------------------
        // Wait before next movement wave
        // ---------------------------------

        config.ValueRW.MoveTimer -= SystemAPI.Time.DeltaTime;

        if (config.ValueRO.MoveTimer > 0f)
            return;

        // Reset timer for next wave
        config.ValueRW.MoveTimer =
            config.ValueRO.TimeBeforeMoving;

        // ---------------------------------
        // Calculate number of cubes to move
        // ---------------------------------

        int totalToMovePerWave = (int)math.max(
            1,
            math.ceil(
                config.ValueRO.RemainingToMove *
                (config.ValueRO.PercentageMoving / 100f)));

        // Safety clamp
        totalToMovePerWave = math.min(
            totalToMovePerWave,
            config.ValueRO.RemainingToMove);

        if (totalToMovePerWave <= 0)
        {
            config.ValueRW.StartMove = false;
            return;
        }

        // ---------------------------------
        // Randomly convert StaticTag -> MovingTag
        // ---------------------------------

        var ecb = new EntityCommandBuffer(Allocator.Temp);

        int movedThisWave = 0;

        foreach (var (velocity, entity)
                 in SystemAPI.Query<RefRW<Velocity>>()
                     .WithAll<StaticTag>()
                     .WithEntityAccess())
        {
            if (movedThisWave >= totalToMovePerWave)
                break;

            // Remove from static pool
            ecb.RemoveComponent<StaticTag>(entity);

            // Mark as moving
            ecb.AddComponent<MovingTag>(entity);

            // Enable actual movement
            velocity.ValueRW.Speed = 5f;

            movedThisWave++;
        }

        config.ValueRW.RemainingToMove -= movedThisWave;

        // ---------------------------------
        // Finished all movement
        // ---------------------------------

        if (config.ValueRO.RemainingToMove <= 0)
        {
            config.ValueRW.StartMove = false;

            Debug.Log("All cubes started moving. Phase 3 finished.");
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();
    }
}
