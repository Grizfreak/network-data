using Unity.Entities;
using Unity.NetCode;
using Unity.Burst;
using UnityEngine;

[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct ClientConnectionSystem : ISystem
{
    private bool _connected;
    private const float TimeoutSeconds = 10f;

    public void OnUpdate(ref SystemState state)
    {
        bool hasNetworkId =
            !SystemAPI.QueryBuilder()
                .WithAll<NetworkId>()
                .Build()
                .IsEmpty;

        // CONNECTED
        if (hasNetworkId && !_connected)
        {
            _connected = true;
            NetworkLauncher.Instance?.OnClientConnected();
        }

        // DISCONNECTED
        if (!hasNetworkId && _connected)
        {
            _connected = false;
            NetworkLauncher.Instance?.OnClientStopped();
        }

        // TIMEOUT (only while connecting)
        var launcher = NetworkLauncher.Instance;

        if (!_connected &&
            launcher != null &&
            launcher.CurrentState == LauncherNetworkState.Connecting)
        {
            float elapsed = Time.realtimeSinceStartup - launcher.ConnectionStartTime;

            if (elapsed > TimeoutSeconds)
            {
                launcher.OnClientStopped();
                launcher.CurrentState = LauncherNetworkState.Disconnected;

                UnityEngine.Debug.Log("Connection timeout.");
            }
        }
    }
}
