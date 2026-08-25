using Unity.Entities;
using Unity.NetCode;

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
    }

    public void OnUpdate(ref SystemState state)
    {
    }
}