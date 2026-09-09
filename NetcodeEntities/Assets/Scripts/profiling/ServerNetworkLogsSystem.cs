using Unity.Entities;
using Unity.NetCode;

/// <summary>Ensures a server-side LogConfig singleton exists, providing the "netcodeEntities_server_" file name prefix used by the log exporters.</summary>
[WorldSystemFilter(WorldSystemFilterFlags.ServerSimulation)]
public partial struct ServerNetworkLogsSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        if (!SystemAPI.HasSingleton<LogConfig>())
        {
            state.EntityManager.CreateSingleton(new LogConfig
            {
                Prefix = "netcodeEntities_server_"
            });
        }

        // All work happens once above; disable so this system isn't scheduled every frame for nothing.
        state.Enabled = false;
    }

    public void OnUpdate(ref SystemState state)
    {
    }
}