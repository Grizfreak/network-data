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
using System.Threading.Tasks;
using System.Diagnostics;
using System.Text.RegularExpressions;
using Debug = UnityEngine.Debug;

public class NetworkLauncher : MonoBehaviour, INetworkRunnerCallbacks, IWiresharkTracking
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
                ParseServerPortAndConnectWireshark();
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

            var statistics = Runner.SetupStatistics();
            await Task.Yield();
            if (Runner.TryGetFusionStatistics(out var statisticsManager))
            {
                Debug.Log("Successfully obtained statistics manager from NetworkRunner.");
                var statsRoot = statistics?.Root;
                if (statsRoot != null)
                {
                    statsRoot.ToggleCollapse();
                }
                else
                {
                    Debug.LogWarning("Fusion statistics root was not ready yet, so the panel was not collapsed.");
                }
            }
            else
            {
                Debug.LogWarning("Fusion statistics are not available in this build configuration.");
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
        if (PhaseManager.Instance != null)
        {
            Debug.LogError("Client disconnected in a non-good way.. exiting the app");
            PhaseManager.Instance.FinishTest();
        }
    }
    void INetworkRunnerCallbacks.OnConnectedToServer(NetworkRunner runner)
    {
        Debug.Log("Successfully connected to server.");
        ParseServerPortAndConnectWireshark();
    }
    void INetworkRunnerCallbacks.OnDisconnectedFromServer(NetworkRunner runner, NetDisconnectReason reason) {
        Debug.LogError($"Disconnected from server: {reason}");
        guidelinesText.text = $"Disconnected from server: {reason}";
        if (PhaseManager.Instance != null)
        {
            Debug.LogError("Client disconnected in a non-good way.. exiting the app");
            PhaseManager.Instance.FinishTest();
        }
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

    public async void ParseServerPortAndConnectWireshark()
    {
        await Task.Delay(1000);

        int pid = Process.GetCurrentProcess().Id;

        ProcessStartInfo psi = new ProcessStartInfo
        {
            FileName = "netstat",
            Arguments = "-ano -p udp",
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        Process process = Process.Start(psi);

        string output = process.StandardOutput.ReadToEnd();

        process.WaitForExit();

        string[] lines = output.Split('\n');

        foreach (string line in lines)
        {
            if (!line.Contains(pid.ToString()))
                continue;

            Match match = Regex.Match(
                line,
                @"UDP\s+\S+:(\d+)"
            );

            if (match.Success)
            {
                string port = match.Groups[1].Value;

                Debug.Log($"Detected Fusion UDP port: {port}");

                string filter = $"udp port {port} or tcp port {port}";
                
                if (Runner.IsServer)
                {
                    StartTracking(filter, "photon_server_capture");
                }
                else if
                (Runner.IsClient)
                {
                    StartTracking(filter, "photon_client_capture");
                }

                return;
            }
        }

        Debug.LogWarning("Could not detect Fusion UDP port.");
    }
    public void StartTracking(string filter, string filename)
    {
        WiresharkManager.Instance.StartTracking(filter, filename);
    }
}
