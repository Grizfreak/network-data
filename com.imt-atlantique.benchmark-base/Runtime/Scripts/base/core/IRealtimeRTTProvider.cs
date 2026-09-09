using Unity;

/// <summary>Implemented by network layers that can report round-trip time computed from RPC round trips.</summary>
public interface IRealtimeRTTProvider
{
    public float GetRttMs();
}