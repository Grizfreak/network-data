using UnityEngine;

/// <summary>Reads command-line arguments at startup to auto-launch a headless dedicated server when run with --server.</summary>
public class NetworkLoader : MonoBehaviour
{
    void Start()
    {
        string[] args = System.Environment.GetCommandLineArgs();

        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--server")
            {
                NetworkLauncher.Instance.StartServer();
                NetworkLauncher.Instance.isLaunchedHeadless = true;
            }
        }
    }
}
