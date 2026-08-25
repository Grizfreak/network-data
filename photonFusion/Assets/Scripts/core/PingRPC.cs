using Fusion;
using UnityEngine;

public class PingRPC : NetworkBehaviour, IRealtimeRTTProvider
{
    private float timer;
    private int sequenceId;

    private float latestRtt;

    void FixedUpdate()
    {
        if (Runner.IsServer)
            return;

        timer += Time.deltaTime;

        if (timer >= 1.0f)
        {
            timer = 0f;

            PingRpc(Time.realtimeSinceStartupAsDouble, sequenceId++);
        }
    }

    [Rpc(RpcSources.Proxies, RpcTargets.StateAuthority)]
    private void PingRpc(double clientTime, int sequenceId)
    {
        PongRpc(clientTime, sequenceId);
    }

    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
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
