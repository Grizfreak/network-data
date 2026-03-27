using UnityEngine;

public class ObjectBehaviour : MonoBehaviour
{
    public float speed = 5f;
    private float _velocity;

    // Update is called once per frame
    private void FixedUpdate()
    {
        Move();
        Jump();
        RotatePlace();
    }

    private void Move()
    {
        // Randomly move forward
        transform.position += transform.forward * speed * Time.deltaTime;
    }

    private void Jump()
    {
        Vector3 pos = transform.position;
        if (pos.y <= 0f)
        {
            _velocity = 5f;
        }
        float dt = Time.deltaTime;
        _velocity -= 1f * dt;
        pos.y += _velocity * dt;
        if (pos.y <= 0f)
        {
            pos.y = 0f;
        }
        transform.position = pos;
    }

    private void RotatePlace()
    {
        // Randomly rotate in a direction
        this.transform.Rotate(0, 90 * Time.deltaTime, 0);
    }
}