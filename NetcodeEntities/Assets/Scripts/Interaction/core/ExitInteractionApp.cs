using UnityEngine;

/// <summary>Quits the application, or stops play mode when run from the editor.</summary>
public class ExitInteractionApp : MonoBehaviour
{
    public void ExitApp()
    {
        #if UNITY_EDITOR
        UnityEditor.EditorApplication.isPlaying = false;
        #else
        Application.Quit();
        #endif
    }
}
