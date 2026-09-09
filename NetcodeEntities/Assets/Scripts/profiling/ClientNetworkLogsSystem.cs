using Unity.Entities;
using Unity.NetCode;

/// <summary>Ensures a client-side LogConfig singleton exists, providing the "netcodeEntities_client_" file name prefix used by the log exporters.</summary>
[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct ClientNetworkLogsSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        if (!SystemAPI.HasSingleton<LogConfig>())
        {
            state.EntityManager.CreateSingleton(new LogConfig
            {
                Prefix = "netcodeEntities_client_"
            });
        }
    }

    public void OnUpdate(ref SystemState state)
    {
    }
}