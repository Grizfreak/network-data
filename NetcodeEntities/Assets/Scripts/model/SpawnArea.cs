using Unity.Entities;
using Unity.Mathematics;

public struct SpawnArea : IComponentData
{
    public float3 Min;
    public float3 Max;
}