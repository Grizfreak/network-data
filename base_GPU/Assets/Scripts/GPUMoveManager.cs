using System.Collections;
using UnityEngine;

/// <summary>
/// GPU version respecting original wave-based movement:
/// only a percentage of cubes starts moving per wave.
/// </summary>
public class GPUMoveManager : MoveManager
{
    protected override void Start()
    {
        if (BaseLoader.Instance != null)
        {
            percentageOfMovingCubes =
                BaseLoader.Instance.Resource.mPercentageMovingCubesPerWave;

            timeBeforeMovingCubes =
                BaseLoader.Instance.Resource.mTimeBeforeMovingCubes;
        }
    }

    public override void StartMovingCubes()
    {
        StartCoroutine(MoveByWave());
    }

    private IEnumerator MoveByWave()
    {
        int total =
            ((GPUInstantiateManager) InstantiateManager.Instance).TotalInstanceCount();

        int amountPerWave = Mathf.Max(
            1,
            Mathf.RoundToInt(
                total * percentageOfMovingCubes / 100f
            )
        );

        while (
            ((GPUInstantiateManager) InstantiateManager.Instance).MovingInstanceCount()
            < total
        )
        {
            yield return new WaitForSeconds(
                timeBeforeMovingCubes
            );

            StartMovingEntities?.Invoke(
                "StartedMovingLocally"
            );

            ((GPUInstantiateManager) InstantiateManager.Instance).StartMovingWave(
                amountPerWave
            );

            EndMovingEntities?.Invoke(
                "EndedMovingLocally"
            );
        }

        PhaseManager.Instance.PhaseFinished?.Invoke(
            "PhaseFinished"
        );
    }
}