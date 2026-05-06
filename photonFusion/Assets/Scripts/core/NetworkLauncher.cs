using System;
using System.Collections.Generic;
using UnityEngine;
using Fusion;
using Fusion.Sockets;
using TMPro;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using Unity.VisualScripting;
using Fusion.Statistics;

public class NetworkLauncher : MonoBehaviour, INetworkRunnerCallbacks
{
    public static NetworkLauncher Instance;
    public NetworkRunner Runner;
    [SerializeField] private TMP_Text guidelinesText;
    [SerializeField] private Button hostButton;
    [SerializeField] private Button serverButton;
    [SerializeField] private Button clientButton;
    [SerializeField] private Button quitButton;
    [SerializeField] private Button startButton;
    private BaseLauncher baseLauncher;
    public bool isLaunchedHeadless = false;
    
    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    private void Start()
    {
        baseLauncher = this.GetComponent<BaseLauncher>();
    }

    private async void StartGame(GameMode mode)
    {
        try
        {
            Runner = Instantiate(new GameObject()).AddComponent<NetworkRunner>();
            Runner.AddCallbacks(this);
            var scene = SceneRef.FromIndex(SceneManager.GetActiveScene().buildIndex);
            var sceneInfo = new NetworkSceneInfo();
            if (scene.IsValid)
            {
                sceneInfo.AddSceneRef(scene, LoadSceneMode.Additive);
            }

            await Runner.StartGame(new StartGameArgs()
            {
                GameMode = mode,
                SessionName = "Test",
                Scene = scene,
                SceneManager = gameObject.AddComponent<NetworkSceneManagerDefault>()
            });

            if (Runner.IsServer)
            {
                Debug.Log("Server started !");
                hostButton.gameObject.SetActive(false);
                serverButton.gameObject.SetActive(false);
                quitButton.gameObject.SetActive(true);
                clientButton.gameObject.SetActive(false);
                startButton.gameObject.SetActive(true);
                guidelinesText.text = "Server started ! Waiting for client...";
            }
            else if (Runner.IsClient)
            {
                guidelinesText.text = "Connected to server ! Waiting for the test to start...";
                hostButton.gameObject.SetActive(false);
                serverButton.gameObject.SetActive(false);
                quitButton.gameObject.SetActive(true);
                clientButton.gameObject.SetActive(false);
                startButton.gameObject.SetActive(false);
            }

            Runner.SetupStatistics();
            if (Runner.TryGetFusionStatistics(out var statisticsManager))
            {
                Debug.Log("Successfully obtained statistics manager from NetworkRunner.");
                var obj = FindAnyObjectByType(typeof(FusionStatisticsRoot));
                if (obj != null)
                {
                    var statsRoot = obj as FusionStatisticsRoot;
                    statsRoot.ToggleCollapse();
                }
                else
                {
                    Debug.LogError("Failed to find an object of type FusionStatisticsRoot in the scene.");
                }
            }
        }
        catch (Exception e)
        {
            Debug.LogError(e);
            guidelinesText.text = "Failed to start server.";
        }
    }
    
    public void ExitApp()
    {
        Disconnect();
#if UNITY_EDITOR
        UnityEditor.EditorApplication.isPlaying = false;
#else
        Application.Quit();
#endif
    }
    
    public void Disconnect()
    {
        if (Runner != null)
        {
            Runner.Shutdown();
            Runner = null;
        }
        hostButton.gameObject.SetActive(true);
        serverButton.gameObject.SetActive(true);
        quitButton.gameObject.SetActive(false);
        clientButton.gameObject.SetActive(true);
        startButton.gameObject.SetActive(false);
    }
    
    public void StartServer()
    {
        guidelinesText.text = "Trying to start server...";
        StartGame(GameMode.Server);
    }

    public void StartClient()
    {
        guidelinesText.text = "Trying to connect to server...";
        StartGame(GameMode.Client);
    }

    public void StartHost()
    {
        guidelinesText.text = "Trying to start server...";
        StartGame(GameMode.Host);
    }
    
    public void StartTest()
    {
        if (Runner != null && Runner.IsServer)
        {
            Runner.LoadScene(SceneRef.FromIndex(1), LoadSceneMode.Single);
        }
    }

    void INetworkRunnerCallbacks.OnPlayerJoined(NetworkRunner runner, PlayerRef player)
    {
        if (runner.IsServer && isLaunchedHeadless)
        {
            StartTest();
        }
    }
    void INetworkRunnerCallbacks.OnPlayerLeft(NetworkRunner runner, PlayerRef player) { }
    void INetworkRunnerCallbacks.OnInput(NetworkRunner runner, NetworkInput input) { }
    void INetworkRunnerCallbacks.OnInputMissing(NetworkRunner runner, PlayerRef player, NetworkInput input) { }
    void INetworkRunnerCallbacks.OnShutdown(NetworkRunner runner, ShutdownReason shutdownReason)
    {
        Debug.Log($"[FUSION] Shutdown reason: {shutdownReason}");
        guidelinesText.text = $"Did not connect to server: {shutdownReason}, Try again.";
        Runner.Shutdown();
    }
    void INetworkRunnerCallbacks.OnConnectedToServer(NetworkRunner runner) { }
    void INetworkRunnerCallbacks.OnDisconnectedFromServer(NetworkRunner runner, NetDisconnectReason reason) {
        Debug.LogError($"Disconnected from server: {reason}");
        guidelinesText.text = $"Disconnected from server: {reason}";
    }
    void INetworkRunnerCallbacks.OnConnectRequest(NetworkRunner runner, NetworkRunnerCallbackArgs.ConnectRequest request, byte[] token) { }
    void INetworkRunnerCallbacks.OnConnectFailed(NetworkRunner runner, NetAddress remoteAddress, NetConnectFailedReason reason)
    {
        Debug.LogError($"Failed to connect to server at {remoteAddress}: {reason}");
        guidelinesText.text = $"Failed to connect to server at {remoteAddress}: {reason}";
        Disconnect();
    }
    void INetworkRunnerCallbacks.OnSessionListUpdated(NetworkRunner runner, List<SessionInfo> sessionList) { }
    void INetworkRunnerCallbacks.OnCustomAuthenticationResponse(NetworkRunner runner, Dictionary<string, object> data) { }
    void INetworkRunnerCallbacks.OnHostMigration(NetworkRunner runner, HostMigrationToken hostMigrationToken) { }
    void INetworkRunnerCallbacks.OnSceneLoadDone(NetworkRunner runner) { }
    void INetworkRunnerCallbacks.OnSceneLoadStart(NetworkRunner runner) { }
    void INetworkRunnerCallbacks.OnObjectExitAOI(NetworkRunner runner, NetworkObject obj, PlayerRef player) { }
    void INetworkRunnerCallbacks.OnObjectEnterAOI(NetworkRunner runner, NetworkObject obj, PlayerRef player) { }
    void INetworkRunnerCallbacks.OnReliableDataReceived(NetworkRunner runner, PlayerRef player, ReliableKey key, ReadOnlySpan<byte> data) { }
    void INetworkRunnerCallbacks.OnReliableDataProgress(NetworkRunner runner, PlayerRef player, ReliableKey key, float progress) { }
}
