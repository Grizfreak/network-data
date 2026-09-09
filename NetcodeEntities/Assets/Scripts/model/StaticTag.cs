using Unity.Entities;

/// <summary>Tag marking a spawned entity as not yet moving; MoveSystem converts these to MovingTag over time.</summary>
public struct StaticTag : IComponentData
{
}