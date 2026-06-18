using UnityEngine;

public class NetworkLoader : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        string[] args = System.Environment.GetCommandLineArgs();
        
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--server")
            {
                NetworkLauncher.Instance.isLaunchedHeadless = true;
            }
        }
    }
}
