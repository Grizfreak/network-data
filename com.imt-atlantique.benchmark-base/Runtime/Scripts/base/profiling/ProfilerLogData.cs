using System.Collections.Generic;
using System.IO;
using UnityEngine;
using Unity.Profiling.LowLevel.Unsafe;

/// <summary>
/// Class describing a profiler stat in the Unity Profiler system
/// </summary>
[System.Serializable]
public class ProfilerStat
{
    public string Category;
    public string Name;
    public string Unit;
}

/// <summary>
/// Class used to aggregate profiler stat (See <c>ProfilerStat</c> class for more informations
/// </summary>
[System.Serializable]
public class ProfilerStatCollection
{
    public List<ProfilerStat> Stats = new List<ProfilerStat>();
}

/// <summary>
/// This component will log all the available ProfilerRecorderHandles in the Unity Profiler system, and export them to a JSON file. This is useful to have a reference of all the available handles, and to be able to use them in the future for more specific profiling. The JSON file will be saved in the persistent data path of the application, with the name "profiler_handles.json".
/// It is currently used as debug purposes
/// </summary>
public class ProfilerManagement : MonoBehaviour
{
    void Start()
    {
        var handles = new List<ProfilerRecorderHandle>();
        ProfilerRecorderHandle.GetAvailable(handles);

        Debug.Log($"Total available ProfilerRecorderHandles: {handles.Count}");

        var collection = new ProfilerStatCollection();

        foreach (var handle in handles)
        {
            var desc = ProfilerRecorderHandle.GetDescription(handle);

            collection.Stats.Add(new ProfilerStat
            {
                Category = desc.Category.ToString(),
                Name = desc.Name,
                Unit = desc.UnitType.ToString()
            });
        }

        string json = JsonUtility.ToJson(collection, true);

        string path = Path.Combine(Application.persistentDataPath, "profiler_handles.json");
        File.WriteAllText(path, json);

        Debug.Log($"Profiler data exported to: {path}");
    }
}