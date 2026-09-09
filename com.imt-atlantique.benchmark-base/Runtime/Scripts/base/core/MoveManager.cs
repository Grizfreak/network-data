using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Serialization;

    /// <summary>Progressively sets a percentage of static cubes to moving, at fixed intervals, until none remain, then signals PhaseManager.</summary>
    public class MoveManager : MonoBehaviour
    {
        public static MoveManager Instance;
        public List<GameObject> staticCubes  = new();
        public List<GameObject> movingCubes = new();

        public float percentageOfMovingCubes;
        public float timeBeforeMovingCubes;

        [FormerlySerializedAs("StartMoving")] public bool startMoving;
        public bool stopMoving;

        public Action<string> StartMovingEntities;
        public Action<string> EndMovingEntities;

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
            if (BaseLoader.Instance != null)
            {
                percentageOfMovingCubes = BaseLoader.Instance.Resource.mPercentageMovingCubesPerWave;
                timeBeforeMovingCubes = BaseLoader.Instance.Resource.mTimeBeforeMovingCubes;
            }
            InstantiateManager.Instance.OnInstanceCreated += OnGameObjectInstantiated;
        }

        // Update is called once per frame
        private void Update()
        {
            if (startMoving)
            {
                startMoving = false;
                StartMovingCubes();
            }

            if (stopMoving)
            {
                stopMoving = false;
                StopMovingCubes();
            }
            
        }

        private void OnGameObjectInstantiated(GameObject go)
        {
            staticCubes.Add(go);
        }

        /// <summary>Begins moving cubes from the static list to the moving list over time.</summary>
        public virtual void StartMovingCubes()
        {
            StartCoroutine(MoveCubesAfterDelay());
        }

        private void StopMovingCubes()
        {
            foreach (GameObject cube in movingCubes)
            {
                cube.GetComponent<ObjectBehaviour>().isMoving = false;
            }
        }

        protected virtual IEnumerator MoveCubesAfterDelay()
        {
            int numberOfCubes = staticCubes.Count +  movingCubes.Count;
            int numberOfCubesToMove = (int) (numberOfCubes * percentageOfMovingCubes / 100);
            while (staticCubes.Count > 0)
            {
                yield return new WaitForSeconds(timeBeforeMovingCubes);
                StartMovingEntities.Invoke("StartedMovingLocally");
                // get random cubes from static and move them to moving cubes (number based on the percentage)
                for (int i = 0; i < numberOfCubesToMove; i++)
                {
                    if (staticCubes.Count == 0) break;
                    int randomIndex = UnityEngine.Random.Range(0, staticCubes.Count);
                    GameObject cubeToMove = staticCubes[randomIndex];
                    staticCubes.RemoveAt(randomIndex);
                    movingCubes.Add(cubeToMove);
                    cubeToMove.GetComponent<ObjectBehaviour>().isMoving = true;
                }
                EndMovingEntities.Invoke("EndedMovingLocally");
            }

            PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
        }
    }
