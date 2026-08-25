using Unity.Collections;
using Unity.Entities;
using Unity.NetCode;

// Measures exact byte counts flowing through Unity Netcode for Entities by
// summing the live length of the public per-connection data buffers each frame.
// The buffers are Netcode's command/snapshot streaming buffers, so the deltas
// we observe correspond to actual application data written to (or read from)
// the transport pipelines.
//
// Per-entity deltas are tracked so we never double-count when a buffer is
// reused by the Netcode systems.
//
// Direction mapping (per world role):
//   Client world
//     - OutgoingCommandDataStreamBuffer    -> bytes sent      (client -> server)
//     - IncomingCommandDataStreamBuffer    -> bytes received  (server -> client, commands acked back)
//     - SnapshotDataBuffer                 -> bytes received  (server -> client, snapshots)
//   Server world
//     - OutgoingCommandDataStreamBuffer    -> bytes sent      (server -> client)
//     - IncomingCommandDataStreamBuffer    -> bytes received  (client -> server)
//     - SnapshotDataBuffer                 -> bytes sent      (server -> client snapshots)

[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
[UpdateInGroup(typeof(Unity.NetCode.NetworkReceiveSystemGroup), OrderLast = true)]
public partial struct ClientBytesCounterSystem : ISystem
{
    private NativeHashMap<Entity, int> _outgoingSeen;
    private NativeHashMap<Entity, int> _incomingCmdSeen;
    private NativeHashMap<Entity, int> _snapshotSeen;

    public void OnCreate(ref SystemState state)
    {
        _outgoingSeen = new NativeHashMap<Entity, int>(16, Allocator.Persistent);
        _incomingCmdSeen = new NativeHashMap<Entity, int>(16, Allocator.Persistent);
        _snapshotSeen = new NativeHashMap<Entity, int>(64, Allocator.Persistent);

        state.RequireForUpdate<NetworkStreamInGame>();
    }

    public void OnDestroy(ref SystemState state)
    {
        if (_outgoingSeen.IsCreated) _outgoingSeen.Dispose();
        if (_incomingCmdSeen.IsCreated) _incomingCmdSeen.Dispose();
        if (_snapshotSeen.IsCreated) _snapshotSeen.Dispose();
    }

    public void OnUpdate(ref SystemState state)
    {
        var provider = NetworkBenchmarkDots.Instance;
        if (provider == null)
            return;

        var em = state.EntityManager;

        // Client sends commands to the server.
        foreach (var (buf, entity) in
                 SystemAPI.Query<DynamicBuffer<OutgoingCommandDataStreamBuffer>>().WithEntityAccess())
        {
            int currentLen = buf.Length;
            int previousLen = 0;
            _outgoingSeen.TryGetValue(entity, out previousLen);

            if (currentLen > previousLen)
                provider.AddBytesSent(currentLen - previousLen);

            _outgoingSeen[entity] = currentLen;
        }
        ReapMissing(_outgoingSeen, em);

        // Client receives commands from the server (small overhead stream).
        foreach (var (buf, entity) in
                 SystemAPI.Query<DynamicBuffer<IncomingCommandDataStreamBuffer>>().WithEntityAccess())
        {
            int currentLen = buf.Length;
            int previousLen = 0;
            _incomingCmdSeen.TryGetValue(entity, out previousLen);

            if (currentLen > previousLen)
                provider.AddBytesReceived(currentLen - previousLen);

            _incomingCmdSeen[entity] = currentLen;
        }
        ReapMissing(_incomingCmdSeen, em);

        // Client receives snapshots from the server (the bulk of the data).
        foreach (var (buf, entity) in
                 SystemAPI.Query<DynamicBuffer<SnapshotDataBuffer>>().WithEntityAccess())
        {
            int currentLen = buf.Length;
            int previousLen = 0;
            _snapshotSeen.TryGetValue(entity, out previousLen);

            if (currentLen > previousLen)
                provider.AddBytesReceived(currentLen - previousLen);

            _snapshotSeen[entity] = currentLen;
        }
        ReapMissing(_snapshotSeen, em);
    }

    private static void ReapMissing(NativeHashMap<Entity, int> seen, EntityManager em)
    {
        using var keys = seen.GetKeyArray(Allocator.Temp);
        for (int i = 0; i < keys.Length; i++)
        {
            if (!em.Exists(keys[i]))
                seen.Remove(keys[i]);
        }
    }
}

[WorldSystemFilter(WorldSystemFilterFlags.ServerSimulation)]
[UpdateInGroup(typeof(Unity.NetCode.NetworkReceiveSystemGroup), OrderLast = true)]
public partial struct ServerBytesCounterSystem : ISystem
{
    private NativeHashMap<Entity, int> _outgoingSeen;
    private NativeHashMap<Entity, int> _incomingCmdSeen;
    private NativeHashMap<Entity, int> _snapshotSeen;

    public void OnCreate(ref SystemState state)
    {
        _outgoingSeen = new NativeHashMap<Entity, int>(16, Allocator.Persistent);
        _incomingCmdSeen = new NativeHashMap<Entity, int>(16, Allocator.Persistent);
        _snapshotSeen = new NativeHashMap<Entity, int>(64, Allocator.Persistent);

        state.RequireForUpdate<NetworkStreamInGame>();
    }

    public void OnDestroy(ref SystemState state)
    {
        if (_outgoingSeen.IsCreated) _outgoingSeen.Dispose();
        if (_incomingCmdSeen.IsCreated) _incomingCmdSeen.Dispose();
        if (_snapshotSeen.IsCreated) _snapshotSeen.Dispose();
    }

    public void OnUpdate(ref SystemState state)
    {
        var provider = NetworkBenchmarkDots.Instance;
        if (provider == null)
            return;

        var em = state.EntityManager;

        // Server sends commands (acks) back to clients.
        foreach (var (buf, entity) in
                 SystemAPI.Query<DynamicBuffer<OutgoingCommandDataStreamBuffer>>().WithEntityAccess())
        {
            int currentLen = buf.Length;
            int previousLen = 0;
            _outgoingSeen.TryGetValue(entity, out previousLen);

            if (currentLen > previousLen)
                provider.AddBytesSent(currentLen - previousLen);

            _outgoingSeen[entity] = currentLen;
        }
        ReapMissing(_outgoingSeen, em);

        // Server receives commands from clients.
        foreach (var (buf, entity) in
                 SystemAPI.Query<DynamicBuffer<IncomingCommandDataStreamBuffer>>().WithEntityAccess())
        {
            int currentLen = buf.Length;
            int previousLen = 0;
            _incomingCmdSeen.TryGetValue(entity, out previousLen);

            if (currentLen > previousLen)
                provider.AddBytesReceived(currentLen - previousLen);

            _incomingCmdSeen[entity] = currentLen;
        }
        ReapMissing(_incomingCmdSeen, em);

        // Server sends snapshots to clients (the bulk of the data).
        foreach (var (buf, entity) in
                 SystemAPI.Query<DynamicBuffer<SnapshotDataBuffer>>().WithEntityAccess())
        {
            int currentLen = buf.Length;
            int previousLen = 0;
            _snapshotSeen.TryGetValue(entity, out previousLen);

            if (currentLen > previousLen)
                provider.AddBytesSent(currentLen - previousLen);

            _snapshotSeen[entity] = currentLen;
        }
        ReapMissing(_snapshotSeen, em);
    }

    private static void ReapMissing(NativeHashMap<Entity, int> seen, EntityManager em)
    {
        using var keys = seen.GetKeyArray(Allocator.Temp);
        for (int i = 0; i < keys.Length; i++)
        {
            if (!em.Exists(keys[i]))
                seen.Remove(keys[i]);
        }
    }
}