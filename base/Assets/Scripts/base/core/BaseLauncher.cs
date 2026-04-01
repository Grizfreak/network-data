using UnityEngine;

public class BaseLauncher : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        UnityEngine.SceneManagement.SceneManager.LoadScene("Benchmark");
        PhaseManager.instance.AskPhase1Start.Invoke();
    }
}
