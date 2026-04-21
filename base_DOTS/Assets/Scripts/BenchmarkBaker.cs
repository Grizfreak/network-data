using Unity.Entities;
using Unity.Mathematics;

public class BenchmarkBaker : Baker<BenchmarkAuthoring>
{
    public override void Bake(BenchmarkAuthoring authoring)
    {
        Entity entity = GetEntity(TransformUsageFlags.None);
        
        Entity prefabEntity = GetEntity(authoring.CubePrefab, TransformUsageFlags.Dynamic | TransformUsageFlags.Renderable);

        AddComponent(entity, new Spawner
        {
            Prefab = prefabEntity,
        });
        
        AddComponent(entity, new BenchmarkConfig
        {
            NumberToSpawn = authoring.NumberToSpawn,
            SpawnInstantly = authoring.SpawnInstantly,
            TimeBeforeSpawn = authoring.TimeBeforeSpawn,
            NumberPerWave = authoring.NumberPerWave,
            PercentageMoving = authoring.PercentageMoving,
            TimeBeforeMoving = authoring.TimeBeforeMoving,
            StartSpawn = authoring.StartSpawn,
            StartMove = authoring.StartMove,
            Random = authoring.Random,
            SpawnTimer = authoring.TimeBeforeSpawn,
            MoveTimer = authoring.TimeBeforeMoving,
            SpawnedEntities = 0
        });
        
        var area = new SpawnArea
        {
            Min = new float3(authoring.MinSpawnPosition.x, authoring.MinSpawnPosition.y, authoring.MinSpawnPosition.z),
            Max = new float3(authoring.MaxSpawnPosition.x, authoring.MaxSpawnPosition.y, authoring.MaxSpawnPosition.z),
        };

        AddComponent(entity, new SpawnArea()
        {             
            Min = area.Min,
            Max = area.Max
        });
    }
    
}
