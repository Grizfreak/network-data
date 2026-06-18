using Unity.Entities;
using Unity.Mathematics;

public struct BenchmarkConfig : IComponentData
{
    //Only non-managed types are allowed
    public int NumberToSpawn;
    public bool SpawnInstantly;
    public float TimeBeforeSpawn;
    public int NumberPerWave;
    public float PercentageMoving;
    public float TimeBeforeMoving;
    public bool StartSpawn;
    public bool StartMove;
    public Random Random;
    public int SpawnedEntities;
    public float SpawnTimer;
    public float MoveTimer;
    public bool MoveInitialized;
    public int RemainingToMove;
}
