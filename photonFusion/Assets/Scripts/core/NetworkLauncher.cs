using System;
using System.Collections.Generic;
using UnityEngine;
using Fusion;
using Fusion.Sockets;
using TMPro;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class NetworkLauncher : MonoBehaviour, INetworkRunnerCallbacks
{
    public static NetworkLauncher Instance;
    private NetworkRunner _runner;
    [SerializeField] private TMP_Text guidelinesText;
    [SerializeField] private Button hostButton;
    [SerializeField] private Button serverButton;
    [SerializeField] private Button clientButton;
    [SerializeField] private Button quitButton;
    [SerializeField] private Button startButton;
    private BaseLauncher baseLauncher;
    public bool isLaunchedHeadless = false;
    private bool searchForPhaseManager = false;
    
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
            _runner = Instantiate(new GameObject()).AddComponent<NetworkRunner>();
        
            var scene = SceneRef.FromIndex(SceneManager.GetActiveScene().buildIndex);
            var sceneInfo = new NetworkSceneInfo();
            if (scene.IsValid)
            {
                sceneInfo.AddSceneRef(scene, LoadSceneMode.Additive);
            }

            await _runner.StartGame(new StartGameArgs()
            {
                GameMode = mode,
                SessionName = "Test",
                Scene = scene,
                SceneManager = gameObject.AddComponent<NetworkSceneManagerDefault>()
            });

            if (_runner.IsServer)
            {
                Debug.Log("Server started !");
                hostButton.gameObject.SetActive(false);
                serverButton.gameObject.SetActive(false);
                quitButton.gameObject.SetActive(true);
                clientButton.gameObject.SetActive(false);
                startButton.gameObject.SetActive(true);
                guidelinesText.text = "Server started ! Waiting for client...";
            }
            else if (_runner.IsClient)
            {
                guidelinesText.text = "Connected to server ! Waiting for the test to start...";
                hostButton.gameObject.SetActive(false);
                serverButton.gameObject.SetActive(false);
                quitButton.gameObject.SetActive(true);
                clientButton.gameObject.SetActive(false);
                startButton.gameObject.SetActive(false);
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
        if (_runner != null)
        {
            _runner.Shutdown();
            _runner = null;
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
        if (_runner != null && _runner.IsServer)
        {
            _runner.LoadScene(SceneRef.FromIndex(SceneUtility.GetBuildIndexByScenePath("Assets/Scenes/Benchmark.unity")));
        }
    }

    void INetworkRunnerCallbacks.OnPlayerJoined(NetworkRunner runner, PlayerRef player) { }
    void INetworkRunnerCallbacks.OnPlayerLeft(NetworkRunner runner, PlayerRef player) { }
    void INetworkRunnerCallbacks.OnInput(NetworkRunner runner, NetworkInput input) { }
    void INetworkRunnerCallbacks.OnInputMissing(NetworkRunner runner, PlayerRef player, NetworkInput input) { }
    void INetworkRunnerCallbacks.OnShutdown(NetworkRunner runner, ShutdownReason shutdownReason) { }
    void INetworkRunnerCallbacks.OnConnectedToServer(NetworkRunner runner) { }
    void INetworkRunnerCallbacks.OnDisconnectedFromServer(NetworkRunner runner, NetDisconnectReason reason) { }
    void INetworkRunnerCallbacks.OnConnectRequest(NetworkRunner runner, NetworkRunnerCallbackArgs.ConnectRequest request, byte[] token) { }
    void INetworkRunnerCallbacks.OnConnectFailed(NetworkRunner runner, NetAddress remoteAddress, NetConnectFailedReason reason) { }
    void INetworkRunnerCallbacks.OnUserSimulationMessage(NetworkRunner runner, SimulationMessagePtr message) { }
    void INetworkRunnerCallbacks.OnSessionListUpdated(NetworkRunner runner, List<SessionInfo> sessionList) { }
    void INetworkRunnerCallbacks.OnCustomAuthenticationResponse(NetworkRunner runner, Dictionary<string, object> data) { }
    void INetworkRunnerCallbacks.OnHostMigration(NetworkRunner runner, HostMigrationToken hostMigrationToken) { }
    void INetworkRunnerCallbacks.OnSceneLoadDone(NetworkRunner runner) { }
    void INetworkRunnerCallbacks.OnSceneLoadStart(NetworkRunner runner) { }
    void INetworkRunnerCallbacks.OnObjectExitAOI(NetworkRunner runner, NetworkObject obj, PlayerRef player) { }
    void INetworkRunnerCallbacks.OnObjectEnterAOI(NetworkRunner runner, NetworkObject obj, PlayerRef player) { }
    void INetworkRunnerCallbacks.OnReliableDataReceived(NetworkRunner runner, PlayerRef player, ReliableKey key, ArraySegment<byte> data) { }
    void INetworkRunnerCallbacks.OnReliableDataProgress(NetworkRunner runner, PlayerRef player, ReliableKey key, float progress) { }
}
