using Unity.Entities;
using Unity.NetCode;
using Unity.Burst;

[BurstCompile]
[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct StartBenchmarkRpcSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        foreach (var (_, entity) in
                 SystemAPI.Query<RefRO<StartBenchmarkRpc>>()
                          .WithEntityAccess())
        {
            UnityEngine.SceneManagement.SceneManager
                .LoadScene("Benchmark");

            state.EntityManager.DestroyEntity(entity);
        }
    }
}

public struct StartBenchmarkRpc : IRpcCommand
{
}