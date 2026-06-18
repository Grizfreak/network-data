using Unity.Entities;
using Unity.NetCode;
using UnityEngine;

[WorldSystemFilter(WorldSystemFilterFlags.ServerSimulation)]
public partial struct ServerConnectionDebugSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        var ecb = new EntityCommandBuffer(Unity.Collections.Allocator.Temp);

        foreach (var (netId, entity) in
                 SystemAPI.Query<RefRO<NetworkId>>()
                          .WithNone<DebugLoggedConnection>()
                          .WithEntityAccess())
        {
            Debug.Log($"[SERVER] Client connected: {netId.ValueRO.Value}");

            ecb.AddComponent<DebugLoggedConnection>(entity);
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();
    }
}

public struct DebugLoggedConnection : IComponentData { }