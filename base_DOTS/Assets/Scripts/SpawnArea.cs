using Unity.Entities;
using Unity.Mathematics;

/// <summary>Singleton component defining the world-space bounding box used to randomize spawn positions.</summary>
public struct SpawnArea : IComponentData
{
    public float3 Min;
    public float3 Max;
}