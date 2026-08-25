using Unity.Collections;
using Unity.NetCode;

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

public struct LogEventRpc : IRpcCommand
{
    public LogEventType Type;
    public FixedString128Bytes Message;
    public int Value;
}