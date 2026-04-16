using UnityEngine;
using UnityEditor;
using System.IO;

public static class ScriptableObjectJsonExporter
{
    [MenuItem("Tools/Export ScriptableObject to JSON", false, 100)]
    public static void ExportSelected()
    {
        Object selected = Selection.activeObject;

        if (selected == null)
        {
            Debug.LogError("No object selected.");
            return;
        }

        if (!(selected is ScriptableObject so))
        {
            Debug.LogError("Selected object is not a ScriptableObject.");
            return;
        }

        // Convert to JSON
        string json = JsonUtility.ToJson(so, true);

        // Inject type manually
        string type = so.GetType().Name.Replace("Resource", "").ToLower();

        json = "{\n  \"type\": \"" + type + "\",\n" + json.Substring(1);

        // Ask user where to save
        string path = EditorUtility.SaveFilePanel(
            "Save JSON",
            Application.dataPath,
            so.name + ".json",
            "json"
        );

        if (string.IsNullOrEmpty(path))
            return;

        // Write file
        File.WriteAllText(path, json);

        Debug.Log($"JSON exported to: {path}");
    }
}