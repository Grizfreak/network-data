using Unity.Entities;
using Unity.NetCode;
using Unity.Burst;
using UnityEngine.SceneManagement;

/// <summary>Client-side handler for StartBenchmarkRpc: loads the Benchmark scene once the server signals the test should begin.</summary>
[BurstCompile]
[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct StartBenchmarkRpcSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        var ecb = new EntityCommandBuffer(Unity.Collections.Allocator.Temp);

        bool sceneRequested = false;

        foreach (var (_, entity) in
                 SystemAPI.Query<RefRO<StartBenchmarkRpc>>()
                          .WithEntityAccess())
        {
            if (!sceneRequested)
            {
                NetworkLauncher.Instance.gameObject.GetComponent<BaseLauncher>().startAutoPhase1 = false;
                SceneManager.LoadScene("Benchmark");
                sceneRequested = true;
            }

            ecb.DestroyEntity(entity);
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();
    }
}

/// <summary>RPC sent from the server to all clients to signal that the benchmark test should start.</summary>
public struct StartBenchmarkRpc : IRpcCommand
{
}