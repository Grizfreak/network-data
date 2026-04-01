using System.Collections.Generic;
using System.IO;
using UnityEngine;
using Unity.Profiling.LowLevel.Unsafe;

[System.Serializable]
public class ProfilerStat
{
    public string Category;
    public string Name;
    public string Unit;
}

[System.Serializable]
public class ProfilerStatCollection
{
    public List<ProfilerStat> Stats = new List<ProfilerStat>();
}

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