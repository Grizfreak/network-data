using Unity.Collections;
using Unity.NetCode;

/// <summary>Kinds of benchmark lifecycle events that can be relayed from server to client via LogEventRpc.</summary>
public enum LogEventType : byte
{
    StartingInstantiation,
    FinishedInstantiation,
    PhaseStarted,
    PhaseFinished,
    StartMovingEntities,
    EndMovingEntities,
    EndExperiment
}

/// <summary>RPC used to mirror server-side benchmark/log events (spawn progress, phase changes, etc.) onto the client's LogsManager/PhaseManager/MoveManager.</summary>
public struct LogEventRpc : IRpcCommand
{
    public LogEventType Type;
    public FixedString128Bytes Message;
    public int Value;
}