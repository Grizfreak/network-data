using FishNet;
using FishNet.Managing;
using FishNet.Managing.Timing;
using FishNet.Transporting;
using UnityEngine;

public class NetworkBenchmarkFishNet : MonoBehaviour, INetworkBenchmarkProvider
{
    private NetworkManager _networkManager;
    private Transport _transport;
    private long _bytesReceived;
    private long _bytesSent;

    private void OnEnable()
    {
        TryBindTransport();
    }

    private void OnDisable()
    {
        UnbindTransport();
    }

    public long GetBytesReceived()
    {
        TryBindTransport();
        return _bytesReceived;
    }

    public long GetBytesSent()
    {
        TryBindTransport();
        return _bytesSent;
    }

    public float GetRttMs()
    {
        TryBindTransport();

        TimeManager timeManager = _networkManager != null ? _networkManager.TimeManager : null;
        return timeManager != null ? timeManager.RoundTripTime : 0f;
    }

    private void TryBindTransport()
    {
        NetworkManager networkManager = InstanceFinder.NetworkManager;
        if (networkManager == null)
            return;

        Transport transport = networkManager.TransportManager != null ? networkManager.TransportManager.Transport : null;
        if (transport == null || transport == _transport)
        {
            _networkManager = networkManager;
            return;
        }

        UnbindTransport();

        _networkManager = networkManager;
        _transport = transport;
        _transport.OnClientReceivedData += OnClientReceivedData;
        _transport.OnServerReceivedData += OnServerReceivedData;
    }

    private void UnbindTransport()
    {
        if (_transport != null)
        {
            _transport.OnClientReceivedData -= OnClientReceivedData;
            _transport.OnServerReceivedData -= OnServerReceivedData;
            _transport = null;
        }

        _networkManager = null;
    }

    private void OnClientReceivedData(ClientReceivedDataArgs args)
    {
        _bytesReceived += args.Data.Count;
    }

    private void OnServerReceivedData(ServerReceivedDataArgs args)
    {
        _bytesSent += args.Data.Count;
    }
}
