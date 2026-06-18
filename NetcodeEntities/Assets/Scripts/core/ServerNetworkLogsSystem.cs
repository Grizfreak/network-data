using Unity.Entities;
using Unity.NetCode;

[WorldSystemFilter(WorldSystemFilterFlags.ServerSimulation)]
public partial struct ServerNetworkLogsSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        UnityEngine.Debug.Log("Server world");
    }

    public void OnUpdate(ref SystemState state)
    {
    }
}