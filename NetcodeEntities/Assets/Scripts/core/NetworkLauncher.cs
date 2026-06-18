using System.Linq;
using System.Net;
using UnityEngine;
using Unity.NetCode;
using TMPro;
using UnityEngine.UI;
using Unity.Networking.Transport;
using Unity.Entities;
using UnityEngine.SceneManagement;

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
    private BaseLauncher baseLauncher;
    public bool isLaunchedHeadless = false;
    private bool searchForPhaseManager = false;

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
        //baseLauncher = this.GetComponent<BaseLauncher>();
        //NetworkManager.Singleton.OnServerStarted += OnServerStarted;
        //NetworkManager.Singleton.OnServerStopped += OnServerStopped;
        //TODO
        //NetworkManager.Singleton.gameObject.GetComponent<UnityTransport>().MaxSendQueueSize = 1024 * 1024 * 100;
    }

    public void StartTracking(string filter, string filename)
    {
        WiresharkManager.Instance.StartTracking(filter, filename);
    }

    public void StartHost()
    {
        /*NetworkManager.Singleton.OnClientConnectedCallback += OnClientConnected;
        NetworkManager.Singleton.OnClientDisconnectCallback += OnClientDisconnected;
        guidelinesText.text = "Trying to start server...";
        NetworkManager.Singleton.StartHost();*/
        serverWorld = ClientServerBootstrap.CreateServerWorld("Server");
        clientWorld = ClientServerBootstrap.CreateClientWorld("Client");

        var entity = clientWorld.EntityManager.CreateEntity(
            typeof(NetworkStreamRequestConnect));

        clientWorld.EntityManager.SetComponentData(entity,
            new NetworkStreamRequestConnect
            {
                Endpoint = NetworkEndpoint.Parse("127.0.0.1", 7777)
            });

        OnServerStarted();
    }

    public void StartServer()
    {
        /*NetworkManager.Singleton.OnClientConnectedCallback += OnClientConnected;
        NetworkManager.Singleton.OnClientDisconnectCallback += OnClientDisconnected;
        guidelinesText.text = "Trying to start server...";
        NetworkManager.Singleton.StartServer();
        StartTracking("udp port 7777 or tcp port 7777", "ngo_server_capture");*/
        serverWorld = ClientServerBootstrap.CreateServerWorld("Server");

        var entity = serverWorld.EntityManager.CreateEntity(
            typeof(NetworkStreamRequestListen));

        serverWorld.EntityManager.SetComponentData(
            entity,
            new NetworkStreamRequestListen
            {
                Endpoint = NetworkEndpoint.AnyIpv4.WithPort(7777)
            });

        OnServerStarted();

    }

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
        guidelinesText.text = "Connecting...";
    }

    private void Update()
    {
        if (searchForPhaseManager)
        {
            if (PhaseManager.Instance != null)
            {
                searchForPhaseManager = false;
                PhaseManager.Instance.autoLinkingPhase = false;
            }
        }
        
    }

    public void OnClientConnected()
    {
        OnClientStarted();
        guidelinesText.text = "Connected to server ! Waiting for the test to start...";
    }

    public void StartTest()
    {
        /*NetworkManager.SceneManager.LoadScene(
            "Benchmark",
            UnityEngine.SceneManagement.LoadSceneMode.Single);
        baseLauncher.startAutoPhase1 = true;
        DisablePhaseManagerRpc();*/
        SceneManager.LoadScene("Benchmark", LoadSceneMode.Single);
        var entityManager = serverWorld.EntityManager;
        var rpc = entityManager.CreateEntity();

        entityManager.AddComponentData(
            rpc,
            new StartBenchmarkRpc());

        entityManager.AddComponent<SendRpcCommandRequest>(rpc);
    }

    /*[Rpc(SendTo.NotServer)]
    private void DisablePhaseManagerRpc()
    {
        searchForPhaseManager = true;
    }*/

    private void OnClientDisconnected(ulong connectionId)
    {
        Debug.Log(connectionId);
    }

    private void OnServerStarted()
    {
        Debug.Log("Server started on address : " + GetLocalIPv4());
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
        hostButton.gameObject.SetActive(true);
        serverButton.gameObject.SetActive(true);
        quitButton.gameObject.SetActive(false);
        clientButton.gameObject.SetActive(true);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(true);
        guidelinesText.text = "Server stopped ! You can start a new one or connect to another one...";
        CurrentState = LauncherNetworkState.Disconnected;
    }

    public void OnClientStarted()
    {
        if (CurrentState == LauncherNetworkState.Connected)
        {
            return;
        }
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
        hostButton.gameObject.SetActive(true);
        serverButton.gameObject.SetActive(true);
        quitButton.gameObject.SetActive(false);
        clientButton.gameObject.SetActive(true);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(true);
        guidelinesText.text = "Disconnected ! You can start a new one or connect to another one...";
        CurrentState = LauncherNetworkState.Disconnected;
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

public enum LauncherNetworkState
{
    Idle,
    Connecting,
    Connected,
    ServerRunning,
    Disconnected
}
