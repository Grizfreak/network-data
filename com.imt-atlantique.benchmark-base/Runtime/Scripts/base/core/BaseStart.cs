using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>Loads scene at build index 1 on start, used as the entry point to jump into the benchmark scene.</summary>
public class BaseStart : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    protected virtual void Start()
    {
        SceneManager.LoadScene(1);
    }
}
