using Unity.Entities;
using UnityEngine;

/// <summary>Applies the values loaded from BaseLoader's external resource file onto the ECS BenchmarkConfig singleton once it becomes available.</summary>
public class ECSConfigBootstrap : MonoBehaviour
{
    private bool initialized = false;
    private EntityQuery _configQuery;
    private EntityManager _em;
    void Start()
    {
        if (BaseLoader.Instance == null)
            return;
        var world = WorldResolver.ResolveWorld();
        _em = world.EntityManager;
        _configQuery = _em.CreateEntityQuery(typeof(BenchmarkConfig));
    }

    public void Update()
    {
        if (initialized) return;
        if (!_configQuery.HasSingleton<BenchmarkConfig>())
        {
            Debug.LogWarning("BenchmarkConfig singleton not found yet.");
            return;
        }

        var entity = _configQuery.GetSingletonEntity();
        var config = _em.GetComponentData<BenchmarkConfig>(entity);

        var r = BaseLoader.Instance.Resource;

        config.NumberToSpawn = r.mAmount;
        config.NumberPerWave = r.mNumberPerWave;
        config.TimeBeforeSpawn = r.mTimeBeforeEachSpawn;
        config.PercentageMoving = r.mPercentageMovingCubesPerWave;
        config.TimeBeforeMoving = r.mTimeBeforeMovingCubes;
        config.SpawnInstantly = r.mSpawnOnce;

        config.SpawnTimer = config.TimeBeforeSpawn;
        config.MoveTimer = config.TimeBeforeMoving;

        _em.SetComponentData(entity, config);

        initialized = true;
        Debug.Log("BenchmarkConfig updated from file.");
    }
}