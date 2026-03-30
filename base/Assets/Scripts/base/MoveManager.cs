using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MoveManager : MonoBehaviour
{
    public static MoveManager instance;
    public List<GameObject> staticCubes  = new List<GameObject>();
    public List<GameObject> movingCubes = new List<GameObject>();

    public float percentageOfMovingCubes;
    public float timeBeforeMovingCubes;

    public bool StartMoving;

    public Action<string> StartMovingEntities;
    public Action<string> EndMovingEntities;

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
    void Start()
    {
        InstantiateManager.instance.OnInstanceCreated += OnGameObjectInstantiated;
    }

    // Update is called once per frame
    void Update()
    {
        if (StartMoving)
        {
            StartMoving = false;
            StartMovingCubes();
        }
    }

    private void OnGameObjectInstantiated(GameObject go)
    {
        staticCubes.Add(go);
    }

    public void StartMovingCubes()
    {
        StartCoroutine(MoveCubesAfterDelay());
    }

    IEnumerator MoveCubesAfterDelay()
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

        PhaseManager.instance.PhaseFinished.Invoke("PhaseFinished");
    }
}
