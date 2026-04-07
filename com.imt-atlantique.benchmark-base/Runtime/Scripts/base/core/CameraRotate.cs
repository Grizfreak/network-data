using UnityEngine;

public class CameraRotate : MonoBehaviour
{
    #if PLATFORM_ANDROID
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        this.transform.Rotate(0, 180, 0);
    }
    #endif
}
