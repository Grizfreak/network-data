using UnityEngine;

/// <summary>UI hook that quits the application (or stops play mode in the editor).</summary>
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
