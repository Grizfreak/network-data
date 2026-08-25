using Unity.Collections;
using Unity.Entities;
using Unity.NetCode;

#region CLIENT SENDS PING

[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct PingSenderSystem : ISystem
{
    private float _timer;
    private int _sequenceId;

    public void OnUpdate(ref SystemState state)
    {
        _timer += SystemAPI.Time.DeltaTime;

        if (_timer < 1f)
            return;

        _timer = 0f;

        Entity rpc = state.EntityManager.CreateEntity();

        state.EntityManager.AddComponentData(
            rpc,
            new PingRpc
            {
                ClientTime = SystemAPI.Time.ElapsedTime,
                SequenceId = _sequenceId++
            });

        state.EntityManager.AddComponentData(
            rpc,
            new SendRpcCommandRequest());
    }
}

#endregion

#region SERVER RECEIVES PING AND SENDS PONG

[WorldSystemFilter(WorldSystemFilterFlags.ServerSimulation)]
public partial struct PingReceiveSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        var ecb = new EntityCommandBuffer(Allocator.Temp);

        foreach (var (ping, request, entity) in
                 SystemAPI.Query<
                         RefRO<PingRpc>,
                         RefRO<ReceiveRpcCommandRequest>>()
                     .WithEntityAccess())
        {
            Entity pongEntity = ecb.CreateEntity();

            ecb.AddComponent(
                pongEntity,
                new PongRpc
                {
                    OriginalTime = ping.ValueRO.ClientTime,
                    SequenceId = ping.ValueRO.SequenceId
                });

            ecb.AddComponent(
                pongEntity,
                new SendRpcCommandRequest
                {
                    TargetConnection = request.ValueRO.SourceConnection
                });

            ecb.DestroyEntity(entity);
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();
    }
}

#endregion

#region CLIENT RECEIVES PONG

[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct PongReceiveSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        var ecb = new EntityCommandBuffer(Allocator.Temp);

        foreach (var (pong, entity) in
                 SystemAPI.Query<RefRO<PongRpc>>()
                     .WithEntityAccess())
        {
            float rttMs =
                (float)((SystemAPI.Time.ElapsedTime -
                         pong.ValueRO.OriginalTime) * 1000.0);

            DotsRttProvider.Instance?.SetRttMs(rttMs);

            ecb.DestroyEntity(entity);
        }

        ecb.Playback(state.EntityManager);
        ecb.Dispose();
    }
}

#endregion

#region DEFINE PING AND PONG RPCS

public struct PingRpc : IRpcCommand
{
    public double ClientTime;
    public int SequenceId;
}

public struct PongRpc : IRpcCommand
{
    public double OriginalTime;
    public int SequenceId;
}
#endregion