using Unity.Netcode;
using UnityEngine;

public class PingRPC : NetworkBehaviour, IRealtimeRTTProvider
{
    private float timer;
    private int sequenceId;

    private float latestRtt;

    void FixedUpdate()
    {
        if (IsServer)
            return;

        timer += Time.deltaTime;

        if (timer >= 1.0f)
        {
            timer = 0f;

            PingRpc(Time.realtimeSinceStartupAsDouble, sequenceId++);
        }
    }

    [Rpc(SendTo.Server)]
    private void PingRpc(double clientTime, int sequenceId)
    {
        PongRpc(clientTime, sequenceId);
    }

    [Rpc(SendTo.NotServer)]
    private void PongRpc(double originalTime, int sequenceId)
    {
        double rtt = Time.realtimeSinceStartupAsDouble - originalTime;

        Debug.Log($"RTT: {rtt * 1000.0:F2} ms");
        latestRtt = (float)rtt;
    }

    public float GetRttMs()
    {
        return latestRtt * 1000.0f;
    }
}
