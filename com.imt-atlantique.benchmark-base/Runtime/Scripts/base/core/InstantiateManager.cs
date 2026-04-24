using System;
using System.Collections;
using UnityEngine;
using Random = UnityEngine.Random;

    /// <summary>
    /// This component will manage the instantiation of the cubes, by instantiating a certain number of them at random positions within a defined area. The number of cubes to instantiate, the time before instantiating, and the number of cubes to instantiate per wave can be set in the inspector or loaded from the BaseLoader resource. The instantiation can be done all at once or by group, depending on the spawnInstantly boolean. The component will also invoke events when the instantiation starts and ends, to allow other components to react to these events. The OnInstanceCreated event is also invoked for each instantiated object, allowing other components to keep track of the instantiated objects. The instantiation will continue until the defined number of cubes is instantiated, at which point it will invoke the PhaseFinished event from the PhaseManager.
    /// </summary>
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

        public void StartSpawning()
        {
            StartCoroutine(spawnInstantly ? SpawnObjects() : SpawnObjectsByGroup());
        }


        protected virtual IEnumerator SpawnObjects()
        {
            yield return new WaitForSeconds(timeBeforeSpawn);
            StartingInstantiation.Invoke("StartedInstantiation");
            for (int i = 0; i < numberToSpawn; i++)
            {
                float x = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.x, spawnZone.GetComponent<Renderer>().bounds.max.x);
                float z = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.z, spawnZone.GetComponent<Renderer>().bounds.max.z);
                Vector3 spawnPos = new Vector3(x, 0, z);
                var go = Instantiate(objectToSpawn, spawnPos, transform.rotation);
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
                    float x = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.x, spawnZone.GetComponent<Renderer>().bounds.max.x);
                    float z = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.z, spawnZone.GetComponent<Renderer>().bounds.max.z);
                    Vector3 spawnPos = new Vector3(x, 0, z);
                    var go = Instantiate(objectToSpawn, spawnPos, transform.rotation);
                    OnInstanceCreated.Invoke(go);
                }
                SpawnedInstances+= numberPerWave;
                FinishedInstantiation.Invoke("FinishedInstantiation", SpawnedInstances);
            }
            PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
        }
    }

