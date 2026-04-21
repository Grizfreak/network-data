using UnityEngine;

    /// <summary>
    /// This component will manage the behavior of the cubes, by moving them forward, making them jump and rotate in place. The movement is done by changing the position and rotation of the transform component of the cube. The movement is done in the FixedUpdate method, which is called at a fixed interval, to ensure that the movement is smooth and consistent. The speed of the movement can be set in the inspector or loaded from the BaseLoader resource. The movement will only happen if the isMoving property is true, which is set by the MoveManager component when it starts moving the cubes.
    /// </summary>
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