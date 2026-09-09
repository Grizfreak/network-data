using System.Linq;
using System.Net;
using UnityEngine;
using Unity.NetCode;
using TMPro;
using UnityEngine.UI;
using Unity.Networking.Transport;
using Unity.Entities;
using UnityEngine.SceneManagement;

/// <summary>Drives the menu UI and owns the client/server Netcode worlds: starting host/server/client, tracking connection state, and kicking off the benchmark scene.</summary>
public class NetworkLauncher : MonoBehaviour
{
    public static NetworkLauncher Instance { get; private set; }
    [SerializeField] private TMP_InputField addressInputField;
    [SerializeField] private TMP_Text guidelinesText;
    [SerializeField] private Button hostButton;
    [SerializeField] private Button serverButton;
    [SerializeField] private Button clientButton;
    [SerializeField] private Button quitButton;
    [SerializeField] private Button startButton;

    public LauncherNetworkState CurrentState;
    public float ConnectionStartTime { get; private set; }
    public bool isLaunchedHeadless = false;

    private World serverWorld;
    private World clientWorld;

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(this.gameObject);
        }
        else
        {
            Instance = this;
        }
    }
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    private void Start()
    {
    }

    /// <summary>Starts a Wireshark packet capture using the given filter, writing to the given file.</summary>
    public void StartTracking(string filter, string filename)
    {
        WiresharkManager.Instance.StartTracking(filter, filename);
    }

    /// <summary>Creates a local server world and a client world connected to it (127.0.0.1:7777), for single-process host+client testing.</summary>
    public void StartHost()
    {
        serverWorld = ClientServerBootstrap.CreateServerWorld("Server");
        clientWorld = ClientServerBootstrap.CreateClientWorld("Client");

        var entity = clientWorld.EntityManager.CreateEntity(
            typeof(NetworkStreamRequestConnect));

        clientWorld.EntityManager.SetComponentData(entity,
            new NetworkStreamRequestConnect
            {
                Endpoint = NetworkEndpoint.Parse("127.0.0.1", 7777)
            });
        
        ScriptBehaviourUpdateOrder.AppendWorldToCurrentPlayerLoop(serverWorld);
        ScriptBehaviourUpdateOrder.AppendWorldToCurrentPlayerLoop(clientWorld);

        OnServerStarted();
    }

    /// <summary>Creates a server world listening on port 7777 and starts a packet capture for the benchmark run.</summary>
    public void StartServer()
    {
        foreach (var world in World.All)
        {
            Debug.Log("WORLD: " + world.Name);
        }
        serverWorld = ClientServerBootstrap.CreateServerWorld("Server");

        var entity = serverWorld.EntityManager.CreateEntity(
            typeof(NetworkStreamRequestListen));

        serverWorld.EntityManager.SetComponentData(
            entity,
            new NetworkStreamRequestListen
            {
                Endpoint = NetworkEndpoint.AnyIpv4.WithPort(7777)
            });

        ScriptBehaviourUpdateOrder.AppendWorldToCurrentPlayerLoop(serverWorld);
        StartTracking("udp port 7777 or tcp port 7777", "netcodeEntities_server_capture");
        OnServerStarted();

    }

    /// <summary>Creates a client world and connects it to the given "host:port" address (or the address input field if "null" is passed).</summary>
    public void StartClient(string address)
    {
        if (address == "null")
        {
            address = addressInputField.text;
        }
        string[] split = address.Split(':');

        clientWorld = ClientServerBootstrap.CreateClientWorld("Client");

        var entity = clientWorld.EntityManager.CreateEntity(
            typeof(NetworkStreamRequestConnect));

        clientWorld.EntityManager.SetComponentData(entity,
            new NetworkStreamRequestConnect
            {
                Endpoint = NetworkEndpoint.Parse(split[0], ushort.Parse(split[1]))
            });

        ConnectionStartTime = Time.realtimeSinceStartup;
        CurrentState = LauncherNetworkState.Connecting;
        ScriptBehaviourUpdateOrder.AppendWorldToCurrentPlayerLoop(clientWorld);
        #if !PLATFORM_ANDROID
        StartTracking("udp port 7777 or tcp port 7777", "netcodeEntities_client_capture");
        #endif
        if (!isLaunchedHeadless) guidelinesText.text = "Connecting...";
    }

    /// <summary>Called by ClientConnectionSystem once the client has a NetworkId; updates the UI to reflect the connected state.</summary>
    public void OnClientConnected()
    {
        OnClientStarted();
        if (!isLaunchedHeadless) guidelinesText.text = "Connected to server ! Waiting for the test to start...";
    }

    /// <summary>Broadcasts a StartBenchmarkRpc to clients and loads the Benchmark scene on the server.</summary>
    public void StartTest()
    {
        var entityManager = serverWorld.EntityManager;
        var rpc = entityManager.CreateEntity();

        var ecb = new EntityCommandBuffer(Unity.Collections.Allocator.Temp);

        entityManager.AddComponentData(
            rpc,
            new StartBenchmarkRpc());

        entityManager.AddComponent<SendRpcCommandRequest>(rpc);
        SceneManager.LoadScene("Benchmark", LoadSceneMode.Single);
    }

    private void OnClientDisconnected(ulong connectionId)
    {
        Debug.Log(connectionId);
    }

    private void OnServerStarted()
    {
        Debug.Log("Server started on address : " + GetLocalIPv4());
        if (isLaunchedHeadless) return; // No menu UI exists in a headless build.
        hostButton.gameObject.SetActive(false);
        serverButton.gameObject.SetActive(false);
        quitButton.gameObject.SetActive(true);
        clientButton.gameObject.SetActive(false);
        startButton.gameObject.SetActive(true);
        addressInputField.gameObject.SetActive(false);
        guidelinesText.text = "Server started ! Waiting for client...";
    }

    public void OnServerStopped()
    {
        Debug.Log("Server stopped on address : " + GetLocalIPv4());
        CurrentState = LauncherNetworkState.Disconnected;
        if (isLaunchedHeadless) return; // No menu UI exists in a headless build.
        hostButton.gameObject.SetActive(true);
        serverButton.gameObject.SetActive(true);
        quitButton.gameObject.SetActive(false);
        clientButton.gameObject.SetActive(true);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(true);
        guidelinesText.text = "Server stopped ! You can start a new one or connect to another one...";
    }

    public void OnClientStarted()
    {
        if (CurrentState == LauncherNetworkState.Connected)
        {
            return;
        }
        if (isLaunchedHeadless) return; // No menu UI exists in a headless build.
        hostButton.gameObject.SetActive(false);
        serverButton.gameObject.SetActive(false);
        quitButton.gameObject.SetActive(true);
        clientButton.gameObject.SetActive(false);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(false);
        guidelinesText.text = "Connecting...";
    }

    public void OnClientStopped()
    {
        CurrentState = LauncherNetworkState.Disconnected;
        if (isLaunchedHeadless) return; // No menu UI exists in a headless build.
        hostButton.gameObject.SetActive(true);
        serverButton.gameObject.SetActive(true);
        quitButton.gameObject.SetActive(false);
        clientButton.gameObject.SetActive(true);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(true);
        guidelinesText.text = "Disconnected ! You can start a new one or connect to another one...";
    }

    /// <summary>Disconnects any active worlds and quits the application (or stops play mode in the editor).</summary>
    public void ExitApp()
    {
        Disconnect();
        #if UNITY_EDITOR
        UnityEditor.EditorApplication.isPlaying = false;
        #else
        Application.Quit();
        #endif
    }

    /// <summary>Disposes the client and/or server worlds, if any are active, and resets the UI accordingly.</summary>
    public void Disconnect()
    {
        if (clientWorld != null && clientWorld.IsCreated)
        {
            clientWorld.Dispose();
            clientWorld = null;
            OnClientStopped();
        }

        if (serverWorld != null && serverWorld.IsCreated)
        {
            serverWorld.Dispose();
            serverWorld = null;
            OnServerStopped();
        }
        
    }

    private static string GetLocalIPv4()
    {
        return Dns.GetHostEntry(Dns.GetHostName())
            .AddressList.First(
                f => f.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
            .ToString();
    }

    public void OnDestroy()
    {
        ExitApp();
    }
}

/// <summary>Connection lifecycle state tracked by NetworkLauncher.</summary>
public enum LauncherNetworkState
{
    Idle,
    Connecting,
    Connected,
    Disconnected
}
