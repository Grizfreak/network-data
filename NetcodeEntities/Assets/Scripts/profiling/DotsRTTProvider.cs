using UnityEngine;

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