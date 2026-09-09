using Unity.Entities;

/// <summary>Singleton referencing the prefab entity that SpawnSystem instantiates.</summary>
public struct Spawner : IComponentData
{
    //Only non-managed types are allowed
    public Entity Prefab;
}
