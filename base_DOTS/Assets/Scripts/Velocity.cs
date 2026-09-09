using Unity.Entities;

/// <summary>Per-entity linear and jump speed used by ApplyMovementSystem.</summary>
    public struct Velocity : IComponentData
    {
        public float Speed;
        public float JumpVelocity;
    }