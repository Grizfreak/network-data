using Unity.Entities;
using UnityEngine;

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