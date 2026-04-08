using System.Linq;
using System.Net;
using TMPro;
using Unity.Netcode;
using Unity.Netcode.Transports.UTP;
using Unity.Networking.Transport;
using UnityEngine;
using UnityEngine.Serialization;
using UnityEngine.UI;

public class NetworkLauncher : NetworkBehaviour
{
    BaseLauncher baseLauncher;
    [SerializeField] private TMP_InputField addressInputField;
    [SerializeField] private TMP_Text guidelinesText;
    [SerializeField] private Button hostButton;
    [SerializeField] private Button serverButton;
    [SerializeField] private Button clientButton;
    [SerializeField] private Button quitButton;
    [SerializeField] private Button startButton;

    private void Start()
    {
        NetworkManager.Singleton.OnServerStarted += OnServerStarted;
        NetworkManager.Singleton.OnServerStopped += OnServerStopped;
        baseLauncher = this.GetComponent<BaseLauncher>();
    }

    public void StartHost()
    {
        NetworkManager.Singleton.OnClientConnectedCallback += OnClientConnected;
        NetworkManager.Singleton.OnClientDisconnectCallback += OnClientDisconnected;
        guidelinesText.text = "Trying to start server...";
        NetworkManager.Singleton.StartHost();
    }

    public void StartServer()
    {
        NetworkManager.Singleton.OnClientConnectedCallback += OnClientConnected;
        NetworkManager.Singleton.OnClientDisconnectCallback += OnClientDisconnected;
        guidelinesText.text = "Trying to start server...";
        NetworkManager.Singleton.StartServer();
    }

    public void StartClient(string address)
    {
        try
        {
            if (address.Equals("null"))
            {
                address = addressInputField.text;
            }

            // split address within : cause it should contains port also
            string[] splitted = address.Split(':');

            NetworkManager.Singleton.GetComponent<UnityTransport>().ConnectionData.Address = splitted[0];
            NetworkManager.Singleton.GetComponent<UnityTransport>().ConnectionData.Port = ushort.Parse(splitted[1]);
        }
        catch (System.Exception e)
        {
            Debug.LogWarning("Error happened in parsing data for connection. See error below");
            Debug.Log(e.Message);
        }

        NetworkManager.Singleton.OnClientStarted += OnClientStarted;
        NetworkManager.Singleton.OnClientConnectedCallback += OnClientConnected;
        guidelinesText.text = "Trying to connect...";
        NetworkManager.Singleton.StartClient();
    }

    private void OnClientConnected(ulong connectionId)
    {
        Debug.Log(connectionId);
        if (IsClient)
        {
            guidelinesText.text = "Connected to server ! Waiting for the test to start...";
        }
    }

    public void StartTest()
    {
        /*NetworkManager.SceneManager.LoadScene(
            "Packages/com.imt-atlantique.benchmark-base/Runtime/Scenes/Benchmark.unity",
            UnityEngine.SceneManagement.LoadSceneMode.Single);*/
    }

    private void OnClientDisconnected(ulong connectionId)
    {
        Debug.Log(connectionId);
        if (IsClient)
        {
            
        }
    }

    private void OnServerStarted()
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

    private void OnServerStopped(bool stopReason)
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

    private void OnClientStarted()
    {
        hostButton.gameObject.SetActive(false);
        serverButton.gameObject.SetActive(false);
        quitButton.gameObject.SetActive(true);
        clientButton.gameObject.SetActive(false);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(false);
        guidelinesText.text = "Connecting...";
    }

    private void OnClientStopped(bool stopReason)
    {
        hostButton.gameObject.SetActive(true);
        serverButton.gameObject.SetActive(true);
        quitButton.gameObject.SetActive(false);
        clientButton.gameObject.SetActive(true);
        startButton.gameObject.SetActive(false);
        addressInputField.gameObject.SetActive(true);
        guidelinesText.text = "Disconnected ! You can start a new one or connect to another one...";
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
        if (NetworkManager.Singleton != null)
        {
            if (IsServer)
            {
                NetworkManager.Singleton.OnClientConnectedCallback -= OnClientConnected;
                NetworkManager.Singleton.OnClientDisconnectCallback -= OnClientDisconnected;
            }
            else if (IsClient)
            {
                NetworkManager.Singleton.OnClientStarted -= OnClientStarted;
                NetworkManager.Singleton.OnClientConnectedCallback -= OnClientConnected;
                OnClientStopped(false);
            }
            NetworkManager.Singleton.Shutdown();
        }
    }

    private static string GetLocalIPv4()
    {
        return Dns.GetHostEntry(Dns.GetHostName())
            .AddressList.First(
                f => f.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
            .ToString();
    }

    public override void OnDestroy()
    {
        ExitApp();
    }
}
