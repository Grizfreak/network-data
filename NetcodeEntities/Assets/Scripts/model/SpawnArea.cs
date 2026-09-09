using Unity.Entities;
using Unity.Mathematics;

/// <summary>Axis-aligned bounding box used by SpawnSystem to pick random spawn positions.</summary>
public struct SpawnArea : IComponentData
{
    public float3 Min;
    public float3 Max;
}