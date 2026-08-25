using Unity.Collections;
using Unity.Entities;
using Unity.NetCode;

[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct LogEventRpcReceiveSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        var ecb = new EntityCommandBuffer(Allocator.Temp);

        foreach (var (rpc, entity) in
                 SystemAPI.Query<RefRO<LogEventRpc>>()
                     .WithEntityAccess())
        {
            switch (rpc.ValueRO.Type)
            {
                case LogEventType.StartingInstantiation:
                    InstantiateManager.Instance?
                        .StartingInstantiation
                        ?.Invoke(rpc.ValueRO.Message.ToString());
                    break;

                case LogEventType.FinishedInstantiation:
                    InstantiateManager.Instance?
                        .FinishedInstantiation
                        ?.Invoke(
                            rpc.ValueRO.Message.ToString(),
                            rpc.ValueRO.Value);
                    break;

                case LogEventType.PhaseStarted:
                    PhaseManager.Instance?
                        .PhaseStarted
                        ?.Invoke(rpc.ValueRO.Message.ToString());
                    break;

                case LogEventType.PhaseFinished:
                    PhaseManager.Instance?
                        .PhaseFinished
                        ?.Invoke(rpc.ValueRO.Message.ToString());
                    break;

                case LogEventType.StartMovingEntities:
                    MoveManager.Instance?
                        .StartMovingEntities
                        ?.Invoke(rpc.ValueRO.Message.ToString());
                    break;

                case LogEventType.EndMovingEntities:
                    MoveManager.Instance?
                        .EndMovingEntities
                        ?.Invoke(rpc.ValueRO.Message.ToString());
                    break;
                case LogEventType.EndExperiment:
                    PhaseManager.Instance?
                        .FinishTest();
                    break;
            }

            ecb.DestroyEntity(entity);
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();
    }
}