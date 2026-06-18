using Unity.Entities;
using Unity.NetCode;

[WorldSystemFilter(WorldSystemFilterFlags.ClientSimulation)]
public partial struct ClientNetworkLogsSystem : ISystem
{
    public void OnCreate(ref SystemState state)
    {
        UnityEngine.Debug.Log("Client world");
    }

    public void OnUpdate(ref SystemState state)
    {
    }
}