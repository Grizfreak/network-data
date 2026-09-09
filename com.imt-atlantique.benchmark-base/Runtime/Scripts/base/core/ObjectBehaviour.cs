using UnityEngine;

    /// <summary>Moves, jumps and rotates a cube each FixedUpdate while isMoving is true.</summary>
    public class ObjectBehaviour : MonoBehaviour
    {
        public float speed = 5f;
        private float _velocity;
        public bool isMoving;
        // Update is called once per frame
        private void FixedUpdate()
        {
            if (isMoving)
            {
                Move();
                Jump();
                RotatePlace();
            }
        }

        private void Move()
        {
            // Randomly move forward
            transform.position += transform.forward * (speed * Time.deltaTime);
        }

        private void Jump()
        {
            Vector3 pos = transform.position;
            if (pos.y <= 0f)
            {
                // Ground contact: relaunch upward instead of accumulating downward velocity.
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