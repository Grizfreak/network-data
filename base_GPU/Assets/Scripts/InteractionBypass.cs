using UnityEngine;
using UnityEngine.SceneManagement;

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
                    SceneManager.LoadScene(2);
                }
            }
        }
    }
}
