using Unity.Entities;
using UnityEngine;
using Unity.Burst;


/// <summary>Debug-only system that logs the Spawner singleton's prefab entity once, then disables itself.</summary>
[BurstCompile]
public partial struct SpawnerDebugSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        state.RequireForUpdate<Spawner>();
    }

    public void OnUpdate(ref SystemState state)
    {
        Debug.Log("Spawner EXISTS in ECS world");

        var spawner = SystemAPI.GetSingleton<Spawner>();
        Debug.Log("Prefab entity: " + spawner.Prefab);

        state.Enabled = false; // run only once
    }
}