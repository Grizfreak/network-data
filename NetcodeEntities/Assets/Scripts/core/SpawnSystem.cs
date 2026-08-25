using System;
using UnityEngine;
using Unity.Burst;
using Unity.Entities;
using Unity.NetCode;
using Unity.Mathematics;
using Unity.Transforms;
using Unity.Collections;

[BurstCompile]
[WorldSystemFilter(WorldSystemFilterFlags.ServerSimulation)]
public partial struct SpawnSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        Debug.Log("SpawnSystem created");
        state.RequireForUpdate<Spawner>();
    }

    public void OnUpdate(ref SystemState state)
    {
        var config = SystemAPI.GetSingletonRW<BenchmarkConfig>();
        var spawnAreaConfig = SystemAPI.GetSingletonRW<SpawnArea>();

        if (!config.ValueRO.StartSpawn)
            return;

        var spawner = SystemAPI.GetSingleton<Spawner>();
        var ecb = new EntityCommandBuffer(Allocator.Temp);

        if (config.ValueRO.SpawnInstantly)
        {
            SpawnBatch(ref config.ValueRW, spawnAreaConfig.ValueRO, spawner, ref ecb, config.ValueRO.NumberToSpawn);
            config.ValueRW.StartSpawn = false;
        }
        else
        {
            config.ValueRW.SpawnTimer -= SystemAPI.Time.DeltaTime;

            if (config.ValueRO.SpawnTimer <= 0f)
            {
                int batch = math.min(
                    config.ValueRO.NumberPerWave,
                    config.ValueRO.NumberToSpawn - config.ValueRO.SpawnedEntities);
                
                SpawnBatch(
                    ref config.ValueRW,
                    spawnAreaConfig.ValueRO,
                    spawner,
                    ref ecb,
                    batch);

                config.ValueRW.SpawnTimer = config.ValueRO.TimeBeforeSpawn;
                
                if  (config.ValueRO.SpawnedEntities >= config.ValueRO.NumberToSpawn)
                {
                    config.ValueRW.StartSpawn = false;
                }
            }
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();
    }
    
    private void SpawnBatch(
        ref BenchmarkConfig config,
        SpawnArea area,
        Spawner spawner,
        ref EntityCommandBuffer ecb,
        int amount)
    {
        for (int i = 0; i < amount; i++)
        {
            float x = config.Random.NextFloat(
                area.Min.x,
                area.Max.x);

            float z = config.Random.NextFloat(
                area.Min.z,
                area.Max.z);

            Entity e = ecb.Instantiate(spawner.Prefab);

            ecb.SetComponent(
                e,
                LocalTransform.FromPosition(
                    new float3(x, 0, z)));
            
            if (!PhaseManager.Instance.moveAndSpawn)
            {
                ecb.AddComponent<StaticTag>(e);
            }
            else
            {
                ecb.AddComponent<MovingTag>(e);
            }

            ecb.AddComponent(e, new Velocity
            {
                Speed = 5f,
                JumpVelocity = 0f
            });

            config.SpawnedEntities++;
        }
    }
}