using Unity.Entities;
using Unity.NetCode;
using UnityEngine;

/// <summary>Logs each new server connection, puts it in-game, and (when running headless) auto-starts the benchmark once a client connects.</summary>
[WorldSystemFilter(WorldSystemFilterFlags.ServerSimulation)]
public partial struct ServerConnectionDebugSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        bool shouldStartBenchmark = false;
        var ecb = new EntityCommandBuffer(Unity.Collections.Allocator.Temp);

        foreach (var (netId, entity) in
                 SystemAPI.Query<RefRO<NetworkId>>()
                          .WithNone<DebugLoggedConnection>()
                          .WithEntityAccess())
        {
            Debug.Log($"[SERVER] Client connected: {netId.ValueRO.Value}");
            ecb.AddComponent<NetworkStreamInGame>(entity);
            ecb.AddComponent<DebugLoggedConnection>(entity);
            if (NetworkLauncher.Instance.isLaunchedHeadless)
            {
                shouldStartBenchmark = true;
            }
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();

        if (shouldStartBenchmark)
        {
            NetworkLauncher.Instance.StartTest();
        }
    }
}

/// <summary>Tag preventing a connection from being logged/processed more than once by ServerConnectionDebugSystem.</summary>
public struct DebugLoggedConnection : IComponentData { }