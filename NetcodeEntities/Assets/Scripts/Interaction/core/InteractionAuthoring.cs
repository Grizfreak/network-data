using Unity.Entities;
using Unity.Mathematics;
using UnityEngine;
using Random = Unity.Mathematics.Random;

public class InteractionAuthoring : MonoBehaviour
{
    public GameObject CubePrefab;
    public int NumberToSpawn = 10;
    public int RandomIntMin = 0;
    public int RandomIntMax = 1000;
    public float RandomFloatMin = 0f;
    public float RandomFloatMax = 1f;
    public Vector3 MinSpawnPosition;
    public Vector3 MaxSpawnPosition;
    public int RandomSeed = 1234;
    public Color BaseColor = Color.white;
    public Color HoverColor = new Color(1f, 0.85f, 0.2f, 1f);
    public Color DragColor = new Color(0.35f, 0.9f, 1f, 1f);
    public Color ZoneColor = new Color(0.2f, 1f, 0.5f, 1f);
    public Vector3 ZoneMinPosition = Vector3.zero;
    public Vector3 ZoneMaxPosition = Vector3.one;
    public bool ZoneEnabled = true;
    public float HoverCellSize = 1f;
    public float HoverHalfExtent = 0.5f;
}

public class InteractionBaker : Baker<InteractionAuthoring>
{
    public override void Bake(InteractionAuthoring authoring)
    {
        Entity entity = GetEntity(TransformUsageFlags.None);
        Entity prefabEntity = GetEntity(authoring.CubePrefab, TransformUsageFlags.Dynamic | TransformUsageFlags.Renderable);

        AddComponent(entity, new InteractionSpawnConfig
        {
            Prefab = prefabEntity,
            NextEntityId = 1,
            NumberToSpawn = authoring.NumberToSpawn,
            RandomIntMin = math.min(authoring.RandomIntMin, authoring.RandomIntMax),
            RandomIntMax = math.max(authoring.RandomIntMin, authoring.RandomIntMax),
            RandomFloatMin = math.min(authoring.RandomFloatMin, authoring.RandomFloatMax),
            RandomFloatMax = math.max(authoring.RandomFloatMin, authoring.RandomFloatMax),
            MinSpawn = new float3(authoring.MinSpawnPosition.x, authoring.MinSpawnPosition.y, authoring.MinSpawnPosition.z),
            MaxSpawn = new float3(authoring.MaxSpawnPosition.x, authoring.MaxSpawnPosition.y, authoring.MaxSpawnPosition.z),
            HoverCellSize = math.max(0.01f, authoring.HoverCellSize),
            HoverHalfExtent = math.max(0.01f, authoring.HoverHalfExtent),
            HoverPlaneY = authoring.MinSpawnPosition.y,
            BaseColor = new float4(authoring.BaseColor.r, authoring.BaseColor.g, authoring.BaseColor.b, authoring.BaseColor.a),
            HoverColor = new float4(authoring.HoverColor.r, authoring.HoverColor.g, authoring.HoverColor.b, authoring.HoverColor.a),
            DragColor = new float4(authoring.DragColor.r, authoring.DragColor.g, authoring.DragColor.b, authoring.DragColor.a),
            ZoneColor = new float4(authoring.ZoneColor.r, authoring.ZoneColor.g, authoring.ZoneColor.b, authoring.ZoneColor.a),
            ZoneMin = new float3(math.min(authoring.ZoneMinPosition.x, authoring.ZoneMaxPosition.x), math.min(authoring.ZoneMinPosition.y, authoring.ZoneMaxPosition.y), math.min(authoring.ZoneMinPosition.z, authoring.ZoneMaxPosition.z)),
            ZoneMax = new float3(math.max(authoring.ZoneMinPosition.x, authoring.ZoneMaxPosition.x), math.max(authoring.ZoneMinPosition.y, authoring.ZoneMaxPosition.y), math.max(authoring.ZoneMinPosition.z, authoring.ZoneMaxPosition.z)),
            ZoneEnabled = authoring.ZoneEnabled,
            HoveredEntity = Entity.Null,
            HoverIndexDirty = true,
            SpawnRequested = false,
            DespawnRequested = false,
            Random = new Random((uint)math.max(1, authoring.RandomSeed))
        });
    }
}