using UnityEngine;
using UnityEngine.SceneManagement;

public class BaseStart : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    protected virtual void Start()
    {
        SceneManager.LoadScene(1);
    }
}
