using Unity.Entities;

public struct Spawner : IComponentData
{
    //Only non-managed types are allowed
    public Entity Prefab;
}
