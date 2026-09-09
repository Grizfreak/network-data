using System;
using System.Collections;
using UnityEngine;

/// <summary>Wave-based movement driver for the GPU-indirect instancing path: flags contiguous ranges of instances as moving via the compute-buffer-backed instantiate manager.</summary>
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

    // Advances a moving "front" of instance indices by movePerWave every timeBeforeMovingCubes
    // seconds, marking each new range as moving via SetMovingRange, until all instances move.
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