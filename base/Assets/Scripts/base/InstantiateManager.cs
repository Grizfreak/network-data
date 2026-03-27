using UnityEngine;

    public class InstantiateManager : MonoBehaviour
    {
        public GameObject objectToSpawn;
        public int numberToSpawn;

        /// <summary>
        /// GameObject used to get rectangleBounds to spawn objects within. If null, objects will be spawned at the position of this gameObject.
        /// </summary>
        public GameObject spawnZone;
        // Start is called once before the first execution of Update after the MonoBehaviour is created
        private void Start()
        {
            for (int i = 0; i < numberToSpawn; i++)
            {
                float x = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.x, spawnZone.GetComponent<Renderer>().bounds.max.x);
                float z = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.z, spawnZone.GetComponent<Renderer>().bounds.max.z);
                Vector3 spawnPos = new Vector3(x, 0, z);
                Instantiate(objectToSpawn, spawnPos, transform.rotation);
            }
        }
    }

