using System;
using System.Collections;
using UnityEngine;
using Random = UnityEngine.Random;

public class InstantiateManager : MonoBehaviour
    {
        public static InstantiateManager instance;
        public GameObject objectToSpawn;
        public int numberToSpawn;
        public bool spawnInstantly = true;
        public float timeBeforeSpawn;
        public int numberPerWave;
        private int _spawnedInstances = 0;

        public Action<string> StartingInstantiation;
        public Action<string, int> FinishedInstantiation;
        /// <summary>
        /// GameObject used to get rectangleBounds to spawn objects within. If null, objects will be spawned at the position of this gameObject.
        /// </summary>
        public GameObject spawnZone;

        public Action<GameObject> OnInstanceCreated;

        private void Awake()
        {
            if (instance == null)
            {
                instance = this;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        
        // Start is called once before the first execution of Update after the MonoBehaviour is created
        private void Start()
        {
            if (BaseLoader.instance == null) return;
            objectToSpawn = BaseLoader.instance.resource.m_Prefab;
            numberToSpawn = BaseLoader.instance.resource.m_Amount;
            spawnInstantly = BaseLoader.instance.resource.m_SpawnOnce;
            timeBeforeSpawn = BaseLoader.instance.resource.m_TimeBeforeEachSpawn;
            numberPerWave = BaseLoader.instance.resource.m_NumberPerWave;
        }

        public void StartSpawning()
        {
            if (spawnInstantly)
            {
                StartCoroutine(SpawnObjects());
            }
            else
            {
                StartCoroutine(SpawnObjectsByGroup());
            }
        }


        private IEnumerator SpawnObjects()
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
            PhaseManager.instance.PhaseFinished.Invoke("PhaseFinished");
        }

        private IEnumerator SpawnObjectsByGroup()
        {
            while (_spawnedInstances < numberToSpawn)
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
                _spawnedInstances+= numberPerWave;
                FinishedInstantiation.Invoke("FinishedInstantiation", _spawnedInstances);
            }
            PhaseManager.instance.PhaseFinished.Invoke("PhaseFinished");
        }
    }

