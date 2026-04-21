using Unity.Entities;
using UnityEngine;

public class ECSConfigBootstrap : MonoBehaviour
{
    
    public BenchmarkAuthoring authoring;
    void Awake()
    {
        if (BaseLoader.Instance == null)
            return;

        var r = BaseLoader.Instance.Resource;

        authoring.NumberToSpawn = r.mAmount;
        authoring.NumberPerWave = r.mNumberPerWave;
        authoring.TimeBeforeSpawn = r.mTimeBeforeEachSpawn;
        authoring.PercentageMoving = r.mPercentageMovingCubesPerWave;
        authoring.TimeBeforeMoving = r.mTimeBeforeMovingCubes;
        authoring.SpawnInstantly = r.mSpawnOnce;
    }
}