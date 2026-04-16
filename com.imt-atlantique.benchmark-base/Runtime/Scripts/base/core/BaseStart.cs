using UnityEngine;
using UnityEngine.SceneManagement;

public class BaseStart : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        SceneManager.LoadScene("Packages/com.imt-atlantique.benchmark-base/Runtime/Scenes/Benchmark.unity");
    }
}
