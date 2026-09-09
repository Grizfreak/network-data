using UnityEngine;

/// <summary>On Android, rotates the camera 180° on start to compensate for Quest headset orientation.</summary>
public class CameraRotate : MonoBehaviour
{
    #if PLATFORM_ANDROID
    void Start()
    {
        this.transform.Rotate(0, 180, 0);
    }
    #endif
}
