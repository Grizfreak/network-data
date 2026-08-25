using Fusion;
using Fusion.Statistics;
using UnityEngine;


public class NetworkBenchmarkPhoton : MonoBehaviour,INetworkBenchmarkProvider
{

    private NetworkRunner Runner =>
        NetworkLauncher.Instance != null ? NetworkLauncher.Instance.Runner : null;
    public float GetRttMs()
    {
        var runner = Runner;

        if (runner == null)
        {
            Debug.LogWarning("NetworkRunner instance is null.");
            return -1f;
        }

        if (!runner.IsRunning)
        {
            return -1f;
        }

        PlayerRef localPlayer = runner.LocalPlayer;

        // Fusion returns seconds
        float rttSeconds = (float)runner.GetPlayerRtt(localPlayer);

        return rttSeconds * 1000f;
    } 
    public long GetBytesSent()
    {
        var runner = Runner;

        if (runner.TryGetFusionStatistics(out var stats))
        {   try
            {
                return (long)stats.SimulationSnapshot.Stats[FusionStatType.OutBandwidth];
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"Error retrieving OutBandwidth stat: {e.Message}");
                return 0;
            }
        }

        return 0;
    }

    public long GetBytesReceived()
    {
        var runner = Runner;

        if (runner.TryGetFusionStatistics(out var stats))
        {   
            try
            {
                return (long)stats.SimulationSnapshot.Stats[FusionStatType.InBandwidth];
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"Error retrieving InBandwidth stat: {e.Message}");
                return 0;
            }
        }

        return 0;
    }
}