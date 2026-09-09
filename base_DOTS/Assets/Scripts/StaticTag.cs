using Unity.Entities;

/// <summary>Tag marking a spawned entity as not yet moving; converted to MovingTag by MoveSystem.</summary>
public struct StaticTag : IComponentData
{
}