using System.Diagnostics;
using UnityEngine;
using Debug = UnityEngine.Debug;
/*
    * WiresharkManager.cs
    * 
    * This class intends to manage the Wireshark process, allowing to start and stop it as needed, and to capture the network traffic of the application for analysis.
    * It can be used to automate the process of capturing network traffic during testing or debugging sessions, making it easier to analyze the communication between the application and external services.
    * This without using proprietary solutions, which might have differents features and limitations.
    *
*/
public class WiresharkManager : MonoBehaviour
{
    public static WiresharkManager Instance { get; private set; }

    private Process _tsharkProcess;
    private string _captureFilePath;

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

    public void StartTracking(string filter, string filename)
    {
        if (_tsharkProcess != null && !_tsharkProcess.HasExited)
        {
            Debug.LogWarning("Wireshark is already running.");
            return;
        }

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

    public void StopTracking()
    {
        if (_tsharkProcess != null && !_tsharkProcess.HasExited)
        {
            _tsharkProcess.Kill();
            _tsharkProcess = null;
            Debug.Log("Wireshark stopped.");
        }
    }
}
