using System;
using System.Collections;
using System.Linq;
using System.Net;
using FishNet.Connection;
using FishNet.Managing;
using FishNet.Managing.Scened;
using FishNet.Object;
using FishNet.Transporting;
using TMPro;
using UnityEngine;
using UnityEngine.Serialization;
using UnityEngine.UI;

public class NetworkLauncher : NetworkBehaviour
{
    public static NetworkLauncher Instance;
    [SerializeField] private TMP_InputField addressInputField;
    [SerializeField] private TMP_Text guidelinesText;
    [SerializeField] private Button hostButton;
    [SerializeField] private Button serverButton;
    [SerializeField] private Button clientButton;
    [SerializeField] private Button quitButton;
    [SerializeField] private Button startButton;
    [SerializeField] private NetworkManager _networkManager;
    private BaseLauncher baseLauncher;

    private bool isServer = false;
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

    public void StartHost()
    {
        StartServer();
        StartClient(GetLocalIPv4());
    }

    public void StartServer()
    {
        isServer = true;
        _networkManager.ServerManager.OnServerConnectionState += OnServerStartStop;
        _networkManager.ServerManager.OnAuthenticationResult += OnClientConnection;
        _networkManager.ServerManager.StartConnection();
    }

    public void StartClient(string address)
    {
        // Cut address by : if it contains a port
        if (address == "null")
        {
            address = addressInputField.text;
        }
        var port = "";
        if (address.Contains(":"))
        {
            address = address.Split(':')[0];
            port = address.Split(':')[1];
        }
        _networkManager.TransportManager.Transport.SetClientAddress(address);
        try
        {
            _networkManager.TransportManager.Transport.SetPort(ushort.Parse(port));
        } catch (Exception e)
        {
            Debug.LogWarning("Failed to set port, using default port. Exception: " + e);
        }
        if (!isServer)
        {
            _networkManager.ClientManager.OnClientConnectionState += OnClientStartStop;
        }
        hostButton.gameObject.SetActive(false);
        serverButton.gameObject.SetActive(false);
        quitButton.gameObject.SetActive(true);
        clientButton.gameObject.SetActive(false);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(false);
        guidelinesText.text = "Connecting...";
        _networkManager.ClientManager.StartConnection();
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
        //ExitApp();
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
        if (_networkManager.IsServerOnlyStarted)
        {
            _networkManager.ServerManager.StopConnection(true);
            return;
        }
        if (_networkManager.IsServerStarted)
        {
            _networkManager.ClientManager.StopConnection();
            _networkManager.ServerManager.StopConnection(true);
        }
        else if (_networkManager.IsClientStarted)
        {
            _networkManager.ClientManager.StopConnection();
        }
    }

    public void OnServerStartStop(ServerConnectionStateArgs args)
    {
        if (args.ConnectionState == LocalConnectionState.Started)
        {
            Debug.Log("Server started on address : " + GetLocalIPv4() +":7777");
            hostButton.gameObject.SetActive(false);
            serverButton.gameObject.SetActive(false);
            quitButton.gameObject.SetActive(true);
            clientButton.gameObject.SetActive(false);
            startButton.gameObject.SetActive(true);
            addressInputField.gameObject.SetActive(false);
            guidelinesText.text = "Server started ! Waiting for client...";
        }
        else if (args.ConnectionState == LocalConnectionState.Stopped)
        {
            Debug.Log("Server stopped on address : " + GetLocalIPv4() +":7777");
            hostButton.gameObject.SetActive(true);
            serverButton.gameObject.SetActive(true);
            quitButton.gameObject.SetActive(false);
            clientButton.gameObject.SetActive(true);
            startButton.gameObject.SetActive(false);
            addressInputField.gameObject.SetActive(true);
            guidelinesText.text = "Server stopped ! You can start a new one or connect to another one...";
        }
    }

    public void OnClientStartStop(ClientConnectionStateArgs args)
    {
        if (args.ConnectionState == LocalConnectionState.Started)
        {
            guidelinesText.text = "Connected to server ! Waiting for the test to start...";
        }
        else if (args.ConnectionState == LocalConnectionState.Stopped)
        {
            hostButton.gameObject.SetActive(true);
            serverButton.gameObject.SetActive(true);
            quitButton.gameObject.SetActive(false);
            clientButton.gameObject.SetActive(true);
            startButton.gameObject.SetActive(false);
            addressInputField.gameObject.SetActive(true);
            guidelinesText.text = "Disconnected ! You can start a new one or connect to another one...";
        }
    }

    public void OnClientConnection(NetworkConnection conn, bool authenticated)
    {
        if (authenticated)
        {
            Debug.Log("Client has connected successfully to the server with connectionId: " + conn.ClientId);
            if (isLaunchedHeadless)
            {
                StartCoroutine(DelayedStartTest());
            }
        }
        else
        {
            Debug.LogWarning("Client failed to connect to the server with connectionId: " + conn.ClientId);
        }
    }

    IEnumerator DelayedStartTest()
    {
        yield return new WaitForSeconds(0.5f);
        StartTest();
    }

    public void StartTest()
    {
        DisablePhaseManagerRpc();
        SceneLoadData sld = new SceneLoadData("Benchmark");
        sld.ReplaceScenes = ReplaceOption.All;
        base.SceneManager.OnLoadEnd += OnLoadEnd;
        base.SceneManager.LoadGlobalScenes(sld);
    }

    private void OnLoadEnd(SceneLoadEndEventArgs args)
    {
        base.SceneManager.OnLoadEnd -= OnLoadEnd;
        BaseLoader.Instance
            .GetComponent<BaseLauncher>()
            .startAutoPhase1 = true;
    }

    [ObserversRpc(BufferLast = true)]
    private void DisablePhaseManagerRpc()
    {
        BaseLoader.Instance.GetComponent<DisablePhaseLinkingForClients>().setSearch(true);
    }
}
