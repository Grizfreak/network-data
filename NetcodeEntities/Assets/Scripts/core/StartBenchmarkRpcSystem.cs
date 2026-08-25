using Unity.Entities;
using Unity.NetCode;
using Unity.Burst;
using UnityEngine.SceneManagement;

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

public struct StartBenchmarkRpc : IRpcCommand
{
}