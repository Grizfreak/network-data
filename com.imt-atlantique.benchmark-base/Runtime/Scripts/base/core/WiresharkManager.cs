using System.Diagnostics;
using UnityEngine;
using Debug = UnityEngine.Debug;

/// <summary>Starts and stops a tshark process to capture network traffic to a .pcap file, with a Quest-specific capture mode.</summary>
public class WiresharkManager : MonoBehaviour
{
    public static WiresharkManager Instance { get; private set; }

    private Process _tsharkProcess;
    private string _captureFilePath;

    private bool isQuest = false;
    private string QuestIp = "";

    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        else
        {
            Destroy(gameObject);
        }
    }
    void Start()
    {
        string[] args = System.Environment.GetCommandLineArgs();
        
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--quest")
            {
                isQuest = true;
                Debug.Log("Running for Quest benchmark tracking, Wireshark will be modified.");
            }

            if (args[i] == "--quest-ip" && i + 1 < args.Length)
            {
                QuestIp = args[i + 1];
                Debug.Log("Quest IP set to: " + QuestIp);
            }
        }
    }

    /// <summary>Starts a tshark capture to a timestamped .pcap file in persistent data path, using a Quest-specific filter if running for Quest.</summary>
    public void StartTracking(string filter, string filename)
    {
        if (_tsharkProcess != null && !_tsharkProcess.HasExited)
        {
            Debug.LogWarning("Wireshark is already running.");
            return;
        }

        if (isQuest)
        {
            _captureFilePath = Application.persistentDataPath + "/" + filename + "_quest_capture_" + System.DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".pcap";
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = "tshark", // Ensure tshark is in the system PATH
                Arguments = $"-i \"Wi-Fi 3\" -w \"{_captureFilePath}\" -f \"host {QuestIp} and udp\"",
                UseShellExecute = false,
                CreateNoWindow = true
            };

            try
            {
                _tsharkProcess = Process.Start(startInfo);
                Debug.Log("Wireshark started with filter: " + $"ip.addr == {QuestIp} && udp");
            }
            catch (System.Exception ex)
            {
                Debug.LogError("Failed to start Wireshark: " + ex.Message);
            }
        }
        else
        {
            _captureFilePath = Application.persistentDataPath + "/" + filename + "_" + System.DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".pcap";
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = "tshark", // Ensure tshark is in the system PATH
                Arguments = $"-i \"Wi-Fi\" -w \"{_captureFilePath}\" -f \"{filter}\"",
                UseShellExecute = false,
                CreateNoWindow = true
            };

            try
            {
                _tsharkProcess = Process.Start(startInfo);
                Debug.Log("Wireshark started with filter: " + filter);
            }
            catch (System.Exception ex)
            {
                Debug.LogError("Failed to start Wireshark: " + ex.Message);
            }
        }
    }

    /// <summary>Kills the running tshark process, if any.</summary>
    public void StopTracking()
    {
        if (_tsharkProcess != null && !_tsharkProcess.HasExited)
        {
            _tsharkProcess.Kill();
            _tsharkProcess = null;
            Debug.Log("Wireshark stopped.");
        }
    }

    void OnDestroy()
    {
        StopTracking();
    }
}
