using Unity.Entities;

/// <summary>Singleton component holding the entity prefab reference used by SpawnSystem to instantiate benchmark cubes.</summary>
public struct Spawner : IComponentData
{
    //Only non-managed types are allowed
    public Entity Prefab;
}
