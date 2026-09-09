using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>Jumps straight to the interaction demo scene (scene index 2) when the app is launched with the --interaction command-line flag.</summary>
public class InteractionBypass : MonoBehaviour
{
    void Start()
    {
        string[] args = System.Environment.GetCommandLineArgs();
        if (args.Length > 1)
        {
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--interaction")
                {
                    SceneManager.LoadScene(2);
                }
            }
        }
    }
}
