using UnityEngine;

public class NetworkBenchmarkDots : MonoBehaviour, INetworkBenchmarkProvider
{
    public static NetworkBenchmarkDots Instance { get; private set; }

    private float _rttMs;
    // Cumulative totals since session start (or since the last Reset call).
    // We keep separate client and server accumulators so both sides can call
    // SetBytesSent/SetBytesReceived with their own numbers and the right one
    // wins per role via INetworkBenchmarkProvider.
    private long _bytesSent;
    private long _bytesReceived;

    private void Awake()
    {
        Instance = this;
    }

    public float GetRttMs()
    {
        return _rttMs;
    }

    public long GetBytesSent()
    {
        return _bytesSent;
    }

    public long GetBytesReceived()
    {
        return _bytesReceived;
    }

    public void SetRtt(float value)
    {
        _rttMs = value;
    }

    public void SetBytesSent(long value)
    {
        _bytesSent = value;
    }

    public void SetBytesReceived(long value)
    {
        _bytesReceived = value;
    }

    /// <summary>
    /// Adds <paramref name="delta"/> to the cumulative bytes-sent counter.
    /// Called by the per-direction measurement systems each frame with the
    /// increase in Netcode buffer length since the previous sample.
    /// </summary>
    public void AddBytesSent(long delta)
    {
        if (delta > 0)
            _bytesSent += delta;
    }

    /// <summary>
    /// Adds <paramref name="delta"/> to the cumulative bytes-received counter.
    /// </summary>
    public void AddBytesReceived(long delta)
    {
        if (delta > 0)
            _bytesReceived += delta;
    }
}