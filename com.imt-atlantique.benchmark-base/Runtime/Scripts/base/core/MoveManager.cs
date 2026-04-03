using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Serialization;

    /// <summary>
    /// This component will manage the movement of the cubes, by moving a percentage of them after a certain amount of time. It will also invoke events when the movement starts and ends, to allow other components to react to these events. The movement is done by changing the isMoving property of the ObjectBehaviour component attached to each cube. The percentage of cubes to move and the time before moving can be set in the inspector or loaded from the BaseLoader resource. The movement will continue until there are no more static cubes left, at which point it will invoke the PhaseFinished event from the PhaseManager.
    /// </summary>
    public class MoveManager : MonoBehaviour
    {
        public static MoveManager Instance;
        public List<GameObject> staticCubes  = new();
        public List<GameObject> movingCubes = new();

        public float percentageOfMovingCubes;
        public float timeBeforeMovingCubes;

        [FormerlySerializedAs("StartMoving")] public bool startMoving;

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
        private void Start()
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
            if (!startMoving) return;
            startMoving = false;
            StartMovingCubes();
        }

        private void OnGameObjectInstantiated(GameObject go)
        {
            staticCubes.Add(go);
        }

        public void StartMovingCubes()
        {
            StartCoroutine(MoveCubesAfterDelay());
        }

        private IEnumerator MoveCubesAfterDelay()
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
