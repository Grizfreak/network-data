using Unity.Burst;
using Unity.Entities;
using Unity.Mathematics;
using Unity.Transforms;

[BurstCompile]
public partial struct ApplyMovementSystem : ISystem
{
    public void OnUpdate(ref SystemState state)
    {
        float dt = SystemAPI.Time.DeltaTime;

        foreach (var (transform, velocity)
                 in SystemAPI.Query<
                     RefRW<LocalTransform>,
                     RefRW<Velocity>>()
                 .WithAll<MovingTag>())
        {
            var currentTransform = transform.ValueRW;

            // -------------------------------------------------
            // MOVE FORWARD
            // Equivalent to:
            // transform.position += transform.forward * speed
            // -------------------------------------------------

            float3 forward = math.forward(currentTransform.Rotation);

            currentTransform.Position +=
                forward *
                velocity.ValueRO.Speed *
                dt;

            // -------------------------------------------------
            // JUMP
            // Equivalent to old Jump()
            // -------------------------------------------------

            float y = currentTransform.Position.y;

            // Ground check
            if (y <= 0f)
            {
                velocity.ValueRW.JumpVelocity = 5f;
            }

            velocity.ValueRW.JumpVelocity -= 1f * dt;

            y += velocity.ValueRW.JumpVelocity * dt;

            if (y <= 0f)
            {
                y = 0f;
            }

            currentTransform.Position.y = y;

            // -------------------------------------------------
            // ROTATE IN PLACE
            // Equivalent to:
            // transform.Rotate(0, 90 * dt, 0)
            // -------------------------------------------------

            quaternion rotationDelta =
                quaternion.RotateY(
                    math.radians(90f * dt));

            currentTransform.Rotation =
                math.mul(
                    currentTransform.Rotation,
                    rotationDelta);

            // Write back
            transform.ValueRW = currentTransform;
        }
    }
}