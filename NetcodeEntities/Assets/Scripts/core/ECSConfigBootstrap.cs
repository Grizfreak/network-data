using Unity.Entities;
using UnityEngine;

public class ECSConfigBootstrap : MonoBehaviour
{
    private bool initialized = false;
    private EntityQuery _configQuery;
    private EntityManager _em;
    void Start()
    {
        if (BaseLoader.Instance == null)
            return;
        var world = ResolveWorld();
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
    private static World ResolveWorld()
    {
        foreach (var world in World.All)
        {
            if (world.Name == "Server" || world.Name == "Client")
            {
                return world;
            }
        }

        return World.DefaultGameObjectInjectionWorld;
    }
}