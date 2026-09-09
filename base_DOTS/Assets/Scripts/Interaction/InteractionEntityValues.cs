using Unity.Entities;

/// <summary>Per-spawned-cube identity and random display values, read by the UI via InteractionValuesApi.</summary>
public struct InteractionEntityValues : IComponentData
{
    public int Id;
    public int RandomInt;
    public float RandomFloat;
}
