using Unity.Entities;
using Unity.NetCode;
using Unity.Burst;
using UnityEngine;

[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct ClientConnectionSystem : ISystem
{
    private bool _connected;
    private bool _inGameSent;

    private bool _sentDisconnect;
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
            if (_inGameSent)
            {
                Debug.Log("Client disconnected (was in-game).");
                Debug.Log("Finishing test due to client disconnection.");
                PhaseManager.Instance.FinishTest();
            }
            else
            {
                NetworkLauncher.Instance?.OnClientStopped();
            }
            
        }

        // 🧠 NEW: READY CHECK FOR INGAME
        if (_connected && !_inGameSent)
        {
            if (IsClientReadyForGameplay(ref state))
            {
                foreach (var entity in SystemAPI.QueryBuilder()
                             .WithAll<NetworkId>()
                             .WithNone<NetworkStreamInGame>()
                             .Build()
                             .ToEntityArray(state.WorldUpdateAllocator))
                {
                    state.EntityManager.AddComponent<NetworkStreamInGame>(entity);
                }
                PhaseManager.Instance.autoLinkingPhase = false;
                _inGameSent = true;
                Debug.Log("Client entered InGame (ready).");
            }
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
                if (_inGameSent)
                {
                    if (!_sentDisconnect)
                    {
                        _sentDisconnect = true;
                        Debug.Log("Client disconnected (was in-game).");
                        Debug.Log("Finishing test due to client disconnection.");
                        PhaseManager.Instance.FinishTest();
                    }
                    else
                    {
                        return;
                    }
                }
                else
                {
                    NetworkLauncher.Instance?.OnClientStopped();
                }
                launcher.CurrentState = LauncherNetworkState.Disconnected;
                UnityEngine.Debug.Log("Connection timeout.");
            }
        }
    }

    private bool IsClientReadyForGameplay(ref SystemState state)
    {
        // 1. Ghost collection must exist
        bool ghostCollectionExists =
            !SystemAPI.QueryBuilder()
                .WithAll<GhostCollection>()
                .Build()
                .IsEmpty;

        // 2. OPTIONAL: ensure SubScene/entities exist
        bool hasSceneEntities =
            !SystemAPI.QueryBuilder()
                .WithAll<SpawnArea>()
                .Build()
                .IsEmpty;

        return ghostCollectionExists && hasSceneEntities;
    }
}
