using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>Lets a build launched with the "--interaction" command-line argument skip straight to the interaction scene, for automated/headless benchmark runs.</summary>
public class InteractionBypass : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        // get args from command line
        string[] args = System.Environment.GetCommandLineArgs();
        if (args.Length > 1)
        {
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--interaction")
                {
                    SceneManager.LoadScene(2); // Build index 2: the interaction scene.
                }
            }
        }
    }
}
