using System;
using System.Collections;
using UnityEngine;
using Random = UnityEngine.Random;

    /// <summary>Spawns objects at random positions within spawnZone, either all at once or wave by wave, then signals PhaseManager when done.</summary>
    public class InstantiateManager : MonoBehaviour
    {
        public static InstantiateManager Instance;
        public GameObject objectToSpawn;
        public int numberToSpawn;
        public bool spawnInstantly = true;
        public float timeBeforeSpawn;
        public int numberPerWave;
        protected int SpawnedInstances;

        public Action<string> StartingInstantiation;
        public Action<string, int> FinishedInstantiation;
        /// <summary>
        /// GameObject used to get rectangleBounds to spawn objects within. If null, objects will be spawned at the position of this gameObject.
        /// </summary>
        public GameObject spawnZone;

        public Action<GameObject> OnInstanceCreated;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        
        // Start is called once before the first execution of Update after the MonoBehaviour is created
        protected virtual void Start()
        {
            if (BaseLoader.Instance == null) return;
            objectToSpawn = BaseLoader.Instance.Resource.mPrefab;
            numberToSpawn = BaseLoader.Instance.Resource.mAmount;
            spawnInstantly = BaseLoader.Instance.Resource.mSpawnOnce;
            timeBeforeSpawn = BaseLoader.Instance.Resource.mTimeBeforeEachSpawn;
            numberPerWave = BaseLoader.Instance.Resource.mNumberPerWave;
        }

        /// <summary>Starts spawning objects, either all at once or by wave depending on spawnInstantly.</summary>
        public void StartSpawning()
        {
            StartCoroutine(spawnInstantly ? SpawnObjects() : SpawnObjectsByGroup());
        }


        private Vector3 GetRandomSpawnPosition()
        {
            float x = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.x, spawnZone.GetComponent<Renderer>().bounds.max.x);
            float z = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.z, spawnZone.GetComponent<Renderer>().bounds.max.z);
            return new Vector3(x, 0, z);
        }

        protected virtual IEnumerator SpawnObjects()
        {
            yield return new WaitForSeconds(timeBeforeSpawn);
            StartingInstantiation.Invoke("StartedInstantiation");
            for (int i = 0; i < numberToSpawn; i++)
            {
                Vector3 spawnPos = GetRandomSpawnPosition();
                var go = Instantiate(objectToSpawn, spawnPos, transform.rotation);
                if (PhaseManager.Instance.moveAndSpawn)
                {
                    go.GetComponent<ObjectBehaviour>().isMoving = true;
                }
                OnInstanceCreated.Invoke(go);
            }
            FinishedInstantiation.Invoke("FinishedInstantiation", numberToSpawn);
            PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
        }

        protected virtual IEnumerator SpawnObjectsByGroup()
        {
            while (SpawnedInstances < numberToSpawn)
            {
                yield return new WaitForSeconds(timeBeforeSpawn);
                StartingInstantiation.Invoke("StartedInstantiation");
                for (int i = 0; i < numberPerWave; i++)
                {
                    Vector3 spawnPos = GetRandomSpawnPosition();
                    var go = Instantiate(objectToSpawn, spawnPos, transform.rotation);
                    if (PhaseManager.Instance.moveAndSpawn)
                    {
                    go.GetComponent<ObjectBehaviour>().isMoving = true;
                    }
                    OnInstanceCreated.Invoke(go);
                }
                SpawnedInstances+= numberPerWave;
                FinishedInstantiation.Invoke("FinishedInstantiation", SpawnedInstances);
            }
            PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
        }
    }

