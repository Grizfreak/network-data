using Unity.Entities;
using Unity.Mathematics;

/// <summary>Singleton component holding spawn/hover/zone configuration and runtime state for the Interaction scene.</summary>
public struct InteractionSpawnConfig : IComponentData
{
    public Entity Prefab;
    public int NextEntityId;
    public int NumberToSpawn;
    public int RandomIntMin;
    public int RandomIntMax;
    public float RandomFloatMin;
    public float RandomFloatMax;
    public float3 MinSpawn;
    public float3 MaxSpawn;
    public float HoverCellSize;
    public float HoverHalfExtent;
    public float HoverPlaneY;
    public float4 BaseColor;
    public float4 HoverColor;
    public float4 DragColor;
    public float4 ZoneColor;
    public float3 ZoneMin;
    public float3 ZoneMax;
    public bool ZoneEnabled;
    public Entity HoveredEntity;
    public Entity DraggedEntity;
    public float3 DragOffset;
    public bool HoverIndexDirty;
    public bool SpawnRequested;
    public bool DespawnRequested;
    public Random Random;
}

/// <summary>Tag marking an entity as one spawned by InteractionSpawnSystem (as opposed to the prefab or other entities).</summary>
public struct InteractionSpawnedTag : IComponentData
{
}