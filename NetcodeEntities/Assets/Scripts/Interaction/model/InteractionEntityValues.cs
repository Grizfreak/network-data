using Unity.Entities;

/// <summary>Per-entity display values (id and randomized stats) shown in the UI when an interaction entity is hovered.</summary>
public struct InteractionEntityValues : IComponentData
{
    public int Id;
    public int RandomInt;
    public float RandomFloat;
}
