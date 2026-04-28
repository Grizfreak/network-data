using System;
using System.Collections;
using UnityEngine;

public class GPUIndirectMoveManager : MoveManager
{
    private GPUIndirectInstantiateManager instantiateManager;
    
    protected override void Start()
    {
        if (BaseLoader.Instance != null)
        {
            percentageOfMovingCubes =
                BaseLoader.Instance.Resource.mPercentageMovingCubesPerWave;

            timeBeforeMovingCubes =
                BaseLoader.Instance.Resource.mTimeBeforeMovingCubes;
        }

        instantiateManager = (GPUIndirectInstantiateManager) InstantiateManager.Instance;
    }
    
    public override void StartMovingCubes()
    {
        StartCoroutine(MoveByWave());
    }

    private IEnumerator MoveByWave()
    {
        int totalToMove = instantiateManager.numberToSpawn;
        int movedCount = 0;

        int movePerWave = Mathf.CeilToInt(
            totalToMove * (percentageOfMovingCubes / 100f)
        );

        while (movedCount < totalToMove)
        {
            yield return new WaitForSeconds(
                timeBeforeMovingCubes
            );
            StartMovingEntities.Invoke(
                "StartedMovingLocally"
            );
            int start = movedCount;
            int end = movedCount + movePerWave;

            instantiateManager.SetMovingRange(
                start,
                end
            );
            EndMovingEntities.Invoke(
                "EndedMovingLocally"
            );
            movedCount = Mathf.Min(
                end,
                totalToMove
            );
        }
        PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
    }
}