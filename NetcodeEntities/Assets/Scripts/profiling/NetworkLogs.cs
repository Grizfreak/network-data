using Unity.Entities;
using UnityEngine;

public class NetworkLogs : MonoBehaviour
{
    void Start()
    {
        var world = ResolveWorld();

        if (world == null)
        {
            Debug.LogWarning("NetworkLogs: Server/Client world not found yet");
            return;
        }

        var configQuery = world.EntityManager.CreateEntityQuery(typeof(LogConfig));

        if (!configQuery.HasSingleton<LogConfig>())
        {
            Debug.LogWarning("LogConfig not ready yet");
            return;
        }

        var config = configQuery.GetSingleton<LogConfig>();

        LogsManager manager = GetComponent<LogsManager>();
        ProfilerStatsToCsvExporter profiler = GetComponent<ProfilerStatsToCsvExporter>();

        manager.eventsFileName = config.Prefix.ToString() + manager.eventsFileName;
        profiler.outputName = config.Prefix.ToString() + profiler.outputName;
        Debug.Log($"NetworkLogs: Updated file names with prefix '{config.Prefix}' on world '{world.Name}'");
    }

    private static World ResolveWorld()
    {
        foreach (var world in World.All)
        {
            if (world.Name == "Server" || world.Name == "Client")
            {
                return world;
            }
        }

        return World.DefaultGameObjectInjectionWorld;
    }
}