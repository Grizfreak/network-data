public interface INetworkBenchmarkProvider { 
    public float GetRttMs(); 
    public long GetBytesSent(); 
    public long GetBytesReceived(); 
}