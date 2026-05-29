using FishNet.Object;
using UnityEngine;

public class PingRPC : NetworkBehaviour, IRealtimeRTTProvider
{
    private float timer;
    private int sequenceId;

    private float latestRtt;

    void FixedUpdate()
    {
        if (!IsClientStarted)
            return;

        timer += Time.deltaTime;

        if (timer >= 1.0f)
        {
            timer = 0f;

            PingRpc(Time.realtimeSinceStartupAsDouble, sequenceId++);
        }
    }

    [ServerRpc(RequireOwnership = false)]
    private void PingRpc(double clientTime, int sequenceId)
    {
        PongRpc(clientTime, sequenceId);
    }

    [ObserversRpc(ExcludeOwner = true)]
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
