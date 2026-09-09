/// <summary>Implemented by network layers that can report RTT and cumulative bytes sent/received for CSV export.</summary>
public interface INetworkBenchmarkProvider {
    public float GetRttMs();
    public long GetBytesSent();
    public long GetBytesReceived();
}