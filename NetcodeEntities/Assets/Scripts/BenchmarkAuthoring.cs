using UnityEngine;
using Random = Unity.Mathematics.Random;

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
