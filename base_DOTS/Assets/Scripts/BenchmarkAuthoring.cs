using UnityEngine;
using Random = Unity.Mathematics.Random;

/// <summary>Inspector-facing settings for the benchmark spawn/move scenario, baked into BenchmarkConfig and SpawnArea by BenchmarkBaker.</summary>
public class BenchmarkAuthoring : MonoBehaviour
{
    public GameObject CubePrefab;
    public int NumberToSpawn;
    public bool SpawnInstantly;
    public float TimeBeforeSpawn;
    public int NumberPerWave;
    public float PercentageMoving;
    public float TimeBeforeMoving;
    public bool StartSpawn;
    public bool StartMove;
    public Vector3 MinSpawnPosition;
    public Vector3 MaxSpawnPosition;
    public Random Random = new Random(1234);
}
