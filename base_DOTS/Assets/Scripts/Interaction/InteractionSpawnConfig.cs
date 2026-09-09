using Unity.Entities;
using Unity.Mathematics;

/// <summary>Singleton component holding all interaction-demo settings and runtime state: spawn parameters, hover/drag grid settings, colors, the protected zone, and current hover/drag/spawn state.</summary>
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

/// <summary>Tag marking an entity as a cube spawned by InteractionSpawnSystem, distinguishing it from other entities in queries.</summary>
public struct InteractionSpawnedTag : IComponentData
{
}