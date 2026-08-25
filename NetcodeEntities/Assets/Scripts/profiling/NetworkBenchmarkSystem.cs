using Unity.Entities;
using Unity.NetCode;

// Bridges RTT from Netcode into the INetworkBenchmarkProvider.
// Byte counts are filled by ClientBytesCounterSystem / ServerBytesCounterSystem,
// which read the live Netcode streaming buffers and accumulate true deltas.
[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct NetworkBenchmarkSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        if (NetworkBenchmarkDots.Instance == null)
            return;

        foreach (var ack in SystemAPI.Query<RefRO<NetworkSnapshotAck>>())
        {
            // EstimatedRTT is already in milliseconds
            NetworkBenchmarkDots.Instance.SetRtt(
                ack.ValueRO.EstimatedRTT);

            break;
        }
    }
}