using UnityEngine;

// Note: class name differs in casing from the file name (historical).
/// <summary>Exposes the latest client-measured RTT (set by PongReceiveSystem) to the generic IRealtimeRTTProvider consumers.</summary>
public class DotsRttProvider : MonoBehaviour, IRealtimeRTTProvider
{
    public static DotsRttProvider Instance { get; private set; }

    private float latestRttMs;

    private void Awake()
    {
        Instance = this;
    }

    public float GetRttMs()
    {
        return latestRttMs;
    }

    public void SetRttMs(float value)
    {
        latestRttMs = value;
    }
}