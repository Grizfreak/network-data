using System.Collections.Generic;
using System.IO;
using UnityEngine;
using Unity.Profiling.LowLevel.Unsafe;

/// <summary>Describes one profiler stat (category, name and unit) in the Unity Profiler system.</summary>
[System.Serializable]
public class ProfilerStat
{
    public string Category;
    public string Name;
    public string Unit;
}

/// <summary>A serializable list of ProfilerStat, used to export available stats to JSON.</summary>
[System.Serializable]
public class ProfilerStatCollection
{
    public List<ProfilerStat> Stats = new List<ProfilerStat>();
}

// NOTE: file is named "ProfilerLogData.cs" but defines ProfilerStat, ProfilerStatCollection and ProfilerManagement (no class named ProfilerLogData); not renamed here as the class may be referenced by Unity meta/GUID and a rename is risky without further verification.
/// <summary>
/// Debug utility that dumps every available ProfilerRecorderHandle on this platform to "profiler_handles.json",
/// so valid category/name pairs can be found for use in ProfilerStatsEntry.
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