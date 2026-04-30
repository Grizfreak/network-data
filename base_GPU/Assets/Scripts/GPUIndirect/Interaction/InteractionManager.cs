using TMPro;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class InteractionManager : MonoBehaviour
{

    [Header("UI Elements")]
    [SerializeField] protected Button spawnButton;
    [SerializeField] protected Button despawnButton;
    [SerializeField] protected TMP_InputField spawnCountInput;
    [SerializeField] protected TMP_Text FPS_Text;

    [Header("Spawn Settings")]
    [SerializeField] protected Mesh mesh;
    [SerializeField] protected Material material;
    [SerializeField] protected GameObject spawnZone;
    [SerializeField] protected int numberToSpawn = 5;

    [Header("Zone Settings")]
    [SerializeField] private GameObject secondPlaneZone;
    [SerializeField] private Color zoneColor = new Color(0.35f, 0.85f, 1f, 1f);

    [Header("Hover Settings")]
    [SerializeField] private Camera hoverCamera;
    [SerializeField] private Color hoverColor = new Color(1f, 0.85f, 0.2f, 1f);
    [SerializeField] private float hoverCellSize = 1f;
    [SerializeField] private float hoverPadding = 0.05f;
    [SerializeField] private bool showDebugRay = false;
    [SerializeField] private Color debugRayColor = Color.cyan;
    [SerializeField] private float debugRayLength = 100f;
    [SerializeField] private bool showDebugSphere = false;
    [SerializeField] private Color debugSphereColor = Color.yellow;
    [SerializeField] private float debugSphereRadius = 0.08f;

    [Header("Node Data")]
    [SerializeField] private Vector2Int randomIntRange = new Vector2Int(0, 1000);
    [SerializeField] private Vector2 randomFloatRange = new Vector2(0f, 1f);
    [SerializeField] private bool logHoveredNodeData = true;

    [Header("Data Display (UI)")]
    [SerializeField] private TMP_Text IDText;
    [SerializeField] private TMP_Text intDataText;
    [SerializeField] private TMP_Text floatDataText;
    [SerializeField] private GameObject Panel;

    protected ComputeBuffer instanceDataBuffer;
    private GraphicsBuffer argsBuffer;
    private GraphicsBuffer.IndirectDrawIndexedArgs[] commandData;
    protected InstanceData[] instanceArray;
    protected RenderParams rp;
    protected bool buffersInitialized = false;
    private int instanceBufferCapacity;
    protected int kernel;
    private Camera cachedHoverCamera;
    private int hoveredInstanceIndex = -1;
    private int[] gridHead;
    private int[] gridNext;
    private int[] instanceCellIndex;
    private float gridMinX;
    private float gridMinZ;
    private float gridMaxX;
    private float gridMaxZ;
    private float gridCellSize;
    private int gridResolutionX;
    private int gridResolutionZ;
    private bool hasDebugHitPoint;
    private Vector3 debugHitPoint;
    private int draggingInstanceIndex = -1;
    private bool isDragging;
    private Vector2 dragPointerOffset;
    private Bounds spawnZoneBounds;
    private Bounds secondPlaneBounds;

    protected struct InstanceData {
        public Vector4 position_scale;
        public int nodeRandomInt;
        public float nodeRandomFloat;
        public float2 nodePadding;
        
        public static int Size()
        {
            return sizeof(float) * 7 + sizeof(int);
        }
    }

    public void Start()
    {
        if (spawnCountInput != null)
        {
            spawnCountInput.text = numberToSpawn.ToString();
            spawnCountInput.onValueChanged.AddListener(OnInstanceValueChanged);
        }
    }

    public bool TryGetHoveredNodeData(out int nodeRandomInt, out float nodeRandomFloat, out int instanceIndex)
    {
        instanceIndex = hoveredInstanceIndex;
        if (instanceArray == null || instanceIndex < 0 || instanceIndex >= instanceArray.Length)
        {
            nodeRandomInt = 0;
            nodeRandomFloat = 0f;
            return false;
        }

        InstanceData hovered = instanceArray[instanceIndex];
        nodeRandomInt = hovered.nodeRandomInt;
        nodeRandomFloat = hovered.nodeRandomFloat;
        return true;
    }

    private void UpdateHoveredNodeDataOutput(int instanceIndex)
    {
        if (instanceArray == null || instanceIndex < 0 || instanceIndex >= instanceArray.Length)
        {
            if (Panel != null)
            {
                Panel.SetActive(false);
            }
            return;
        }

        InstanceData data = instanceArray[instanceIndex];
        string output = "Hover ID=" + instanceIndex + " | int=" + data.nodeRandomInt + " | float=" + data.nodeRandomFloat.ToString("F4");
        if (Panel != null)
        {
            Panel.SetActive(true);
            if (IDText != null)
                IDText.text = "ID: " + instanceIndex;
            if (intDataText != null)
                intDataText.text = "Value 1: " + data.nodeRandomInt;
            if (floatDataText != null)
                floatDataText.text = "Value 2: " + data.nodeRandomFloat.ToString("F4");
        }

        if (logHoveredNodeData)
            Debug.Log(output);
    }

    private InstanceData CreateInstanceData(Vector3 worldPosition)
    {
        int minInt = Mathf.Min(randomIntRange.x, randomIntRange.y);
        int maxIntExclusive = Mathf.Max(randomIntRange.x, randomIntRange.y) + 1;

        float minFloat = Mathf.Min(randomFloatRange.x, randomFloatRange.y);
        float maxFloat = Mathf.Max(randomFloatRange.x, randomFloatRange.y);

        return new InstanceData
        {
            position_scale = new float4(worldPosition.x, worldPosition.y, worldPosition.z, 1f),
            nodeRandomInt = UnityEngine.Random.Range(minInt, maxIntExclusive),
            nodeRandomFloat = UnityEngine.Random.Range(minFloat, maxFloat),
            nodePadding = float2.zero,
        };
    }

    private void SetHoveredInstance(int instanceIndex)
    {
        if (hoveredInstanceIndex == instanceIndex)
            return;

        hoveredInstanceIndex = instanceIndex;
        material.SetInteger("_HoveredInstance", hoveredInstanceIndex);
        material.SetColor("_HoverColor", hoverColor);
        UpdateHoveredNodeDataOutput(hoveredInstanceIndex);
    }

    private void PushZoneMaterialState()
    {
        RefreshSecondZoneBounds();
        material.SetColor("_ZoneColor", zoneColor);
        material.SetVector("_ZoneMin", new Vector4(secondPlaneBounds.min.x, secondPlaneBounds.min.y, secondPlaneBounds.min.z, 1f));
        material.SetVector("_ZoneMax", new Vector4(secondPlaneBounds.max.x, secondPlaneBounds.max.y, secondPlaneBounds.max.z, 1f));
    }

    private void RefreshSecondZoneBounds()
    {
        if (secondPlaneZone != null)
        {
            Renderer secondZoneRenderer = secondPlaneZone.GetComponent<Renderer>();
            if (secondZoneRenderer != null)
            {
                secondPlaneBounds = secondZoneRenderer.bounds;
            }
            else
            {
                secondPlaneBounds = new Bounds(secondPlaneZone.transform.position, secondPlaneZone.transform.localScale);
            }
        }
        else
        {
            secondPlaneBounds = new Bounds(Vector3.zero, Vector3.zero);
        }
    }

    private void RefreshSpawnZoneBounds()
    {
        if (spawnZone == null)
            return;

        Renderer zoneRenderer = spawnZone.GetComponent<Renderer>();
        if (zoneRenderer != null)
        {
            spawnZoneBounds = zoneRenderer.bounds;
        }
    }

    private bool IsPositionInsideSecondZoneXZ(Vector3 position)
    {
        return position.x >= secondPlaneBounds.min.x && position.x <= secondPlaneBounds.max.x &&
               position.z >= secondPlaneBounds.min.z && position.z <= secondPlaneBounds.max.z;
    }

    private void UpdateDrawCount(int instanceCount)
    {
        if (argsBuffer == null || commandData == null || commandData.Length == 0)
            return;

        commandData[0].instanceCount = (uint)Mathf.Max(0, instanceCount);
        argsBuffer.SetData(commandData);
    }

    private void EnsureInstanceBufferCapacity(int requiredCount)
    {
        if (requiredCount <= instanceBufferCapacity && instanceDataBuffer != null)
            return;

        int newCapacity = instanceBufferCapacity > 0 ? instanceBufferCapacity : 1;
        while (newCapacity < requiredCount)
        {
            newCapacity *= 2;
        }

        instanceDataBuffer?.Release();
        instanceDataBuffer = new ComputeBuffer(newCapacity, InstanceData.Size());
        instanceBufferCapacity = newCapacity;
        material.SetBuffer("_InstanceDataBuffer", instanceDataBuffer);
    }

    private void ReleaseAllBuffersAndState()
    {
        hoveredInstanceIndex = -1;
        draggingInstanceIndex = -1;
        isDragging = false;
        dragPointerOffset = Vector2.zero;
        hasDebugHitPoint = false;
        material.SetInteger("_HoveredInstance", -1);
        UpdateHoveredNodeDataOutput(-1);

        instanceDataBuffer?.Release();
        instanceDataBuffer = null;
        instanceBufferCapacity = 0;

        argsBuffer?.Release();
        argsBuffer = null;

        instanceArray = null;
        gridHead = null;
        gridNext = null;
        instanceCellIndex = null;

        buffersInitialized = false;
    }

    private void AppendSpawnWave(int additionalCount)
    {
        if (additionalCount <= 0)
            return;

        RefreshSpawnZoneBounds();
        int oldCount = instanceArray != null ? instanceArray.Length : 0;
        int newCount = oldCount + additionalCount;

        InstanceData[] nextArray = new InstanceData[newCount];
        for (int i = 0; i < oldCount; i++)
        {
            nextArray[i] = instanceArray[i];
        }

        float minX = spawnZoneBounds.min.x;
        float maxX = spawnZoneBounds.max.x;
        float minZ = spawnZoneBounds.min.z;
        float maxZ = spawnZoneBounds.max.z;

        for (int i = oldCount; i < newCount; i++)
        {
            Vector3 randomPos = new Vector3(
                UnityEngine.Random.Range(minX, maxX),
                0f,
                UnityEngine.Random.Range(minZ, maxZ)
            );

            nextArray[i] = CreateInstanceData(randomPos);
        }

        instanceArray = nextArray;
        EnsureInstanceBufferCapacity(newCount);
        instanceDataBuffer.SetData(instanceArray, 0, 0, newCount);
        UpdateDrawCount(newCount);
        BuildHoverGridFromInstances();
    }

    private bool TryGetPointerWorldPosition(out Vector3 worldPosition)
    {
        worldPosition = default;

        Camera activeCamera = cachedHoverCamera != null ? cachedHoverCamera : hoverCamera;
        if (activeCamera == null)
        {
            activeCamera = Camera.main;
            cachedHoverCamera = activeCamera;
        }

        if (activeCamera == null)
            return false;

        if (Pointer.current == null)
            return false;

        Vector2 pointerScreenPosition = Pointer.current.position.ReadValue();
        Ray ray = activeCamera.ScreenPointToRay(pointerScreenPosition);

        if (showDebugRay)
        {
            Debug.DrawRay(ray.origin, ray.direction * debugRayLength, debugRayColor);
        }

        float planeY = instanceArray != null && instanceArray.Length > 0
            ? instanceArray[0].position_scale.y
            : 0f;

        Plane plane = new Plane(Vector3.up, new Vector3(0f, planeY, 0f));
        if (!plane.Raycast(ray, out float enter))
        {
            hasDebugHitPoint = false;
            return false;
        }

        worldPosition = ray.GetPoint(enter);
        debugHitPoint = worldPosition;
        hasDebugHitPoint = true;

        if (showDebugRay)
        {
            Debug.DrawLine(ray.origin, worldPosition, debugRayColor);
        }

        return true;
    }

    private bool TryGetPointerWorldPosition(out Vector3 worldPosition, out Ray ray)
    {
        worldPosition = default;
        ray = default;

        Camera activeCamera = cachedHoverCamera != null ? cachedHoverCamera : hoverCamera;
        if (activeCamera == null)
        {
            activeCamera = Camera.main;
            cachedHoverCamera = activeCamera;
        }

        if (activeCamera == null || Pointer.current == null)
            return false;

        Vector2 pointerScreenPosition = Pointer.current.position.ReadValue();
        ray = activeCamera.ScreenPointToRay(pointerScreenPosition);

        float planeY = instanceArray != null && instanceArray.Length > 0
            ? instanceArray[0].position_scale.y
            : 0f;

        Plane plane = new Plane(Vector3.up, new Vector3(0f, planeY, 0f));
        if (!plane.Raycast(ray, out float enter))
        {
            hasDebugHitPoint = false;
            return false;
        }

        worldPosition = ray.GetPoint(enter);
        debugHitPoint = worldPosition;
        hasDebugHitPoint = true;

        return true;
    }

    private bool IsDragPressed()
    {
        return Mouse.current != null && Mouse.current.leftButton.isPressed;
    }

    private bool WasDragPressedThisFrame()
    {
        return Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame;
    }

    private bool WasDragReleasedThisFrame()
    {
        return Mouse.current != null && Mouse.current.leftButton.wasReleasedThisFrame;
    }

    private int GetCellIndexForPosition(Vector3 position)
    {
        int cellX = Mathf.Clamp((int)((position.x - gridMinX) / gridCellSize), 0, gridResolutionX - 1);
        int cellZ = Mathf.Clamp((int)((position.z - gridMinZ) / gridCellSize), 0, gridResolutionZ - 1);
        return cellZ * gridResolutionX + cellX;
    }

    private bool IsWithinCurrentGridBounds(Vector3 position)
    {
        return position.x >= gridMinX && position.x <= gridMaxX && position.z >= gridMinZ && position.z <= gridMaxZ;
    }

    private bool IsInstanceInSpawnZone(int instanceIndex)
    {
        if (instanceArray == null || instanceIndex < 0 || instanceIndex >= instanceArray.Length)
            return false;

        Vector4 positionScale = instanceArray[instanceIndex].position_scale;
        Vector3 position = new Vector3(positionScale.x, positionScale.y, positionScale.z);
        return spawnZoneBounds.Contains(position);
    }

    private bool IsInstanceInSecondPlaneZone(int instanceIndex)
    {
        if (instanceArray == null || instanceIndex < 0 || instanceIndex >= instanceArray.Length)
            return false;

        Vector4 positionScale = instanceArray[instanceIndex].position_scale;
        Vector3 position = new Vector3(positionScale.x, positionScale.y, positionScale.z);
        return IsPositionInsideSecondZoneXZ(position);
    }

    private void RemoveInstanceFromGrid(int instanceIndex)
    {
        if (instanceCellIndex == null || gridHead == null || gridNext == null)
            return;

        int cellIndex = instanceCellIndex[instanceIndex];
        if (cellIndex < 0)
            return;

        int current = gridHead[cellIndex];
        int previous = -1;

        while (current != -1)
        {
            if (current == instanceIndex)
            {
                if (previous == -1)
                {
                    gridHead[cellIndex] = gridNext[current];
                }
                else
                {
                    gridNext[previous] = gridNext[current];
                }

                gridNext[current] = -1;
                instanceCellIndex[instanceIndex] = -1;
                return;
            }

            previous = current;
            current = gridNext[current];
        }
    }

    private void AddInstanceToGrid(int instanceIndex, Vector3 position)
    {
        if (instanceCellIndex == null || gridHead == null || gridNext == null)
            return;

        int cellIndex = GetCellIndexForPosition(position);
        gridNext[instanceIndex] = gridHead[cellIndex];
        gridHead[cellIndex] = instanceIndex;
        instanceCellIndex[instanceIndex] = cellIndex;
    }

    private void UpdateDraggedInstance(Vector3 worldPosition)
    {
        if (draggingInstanceIndex < 0 || draggingInstanceIndex >= instanceArray.Length)
            return;

        Vector4 positionScale = instanceArray[draggingInstanceIndex].position_scale;
        Vector3 newPosition = new Vector3(
            worldPosition.x + dragPointerOffset.x,
            positionScale.y,
            worldPosition.z + dragPointerOffset.y
        );

        if (instanceCellIndex != null)
        {
            int oldCellIndex = instanceCellIndex[draggingInstanceIndex];
            int newCellIndex = GetCellIndexForPosition(newPosition);
            if (oldCellIndex != newCellIndex)
            {
                RemoveInstanceFromGrid(draggingInstanceIndex);
                AddInstanceToGrid(draggingInstanceIndex, newPosition);
            }
        }

        instanceArray[draggingInstanceIndex].position_scale = new float4(newPosition.x, newPosition.y, newPosition.z, positionScale.w);
        instanceDataBuffer.SetData(instanceArray, draggingInstanceIndex, draggingInstanceIndex, 1);
        debugHitPoint = newPosition;
        SetHoveredInstance(draggingInstanceIndex);

        if (!IsWithinCurrentGridBounds(newPosition))
        {
            BuildHoverGridFromInstances();
        }
    }

    private void BuildHoverGridFromInstances()
    {
        if (instanceArray == null || instanceArray.Length == 0)
            return;

        float minX = float.MaxValue;
        float maxX = float.MinValue;
        float minZ = float.MaxValue;
        float maxZ = float.MinValue;

        for (int i = 0; i < instanceArray.Length; i++)
        {
            Vector4 instancePosition = instanceArray[i].position_scale;
            minX = Mathf.Min(minX, instancePosition.x);
            maxX = Mathf.Max(maxX, instancePosition.x);
            minZ = Mathf.Min(minZ, instancePosition.z);
            maxZ = Mathf.Max(maxZ, instancePosition.z);
        }

        float meshFootprint = 1f;
        if (mesh != null)
        {
            meshFootprint = Mathf.Max(mesh.bounds.size.x, mesh.bounds.size.z);
        }

        gridCellSize = Mathf.Max(hoverCellSize, meshFootprint * 2f);
        gridMinX = minX - hoverPadding;
        gridMinZ = minZ - hoverPadding;
        gridMaxX = maxX + hoverPadding;
        gridMaxZ = maxZ + hoverPadding;
        gridResolutionX = Mathf.Max(1, Mathf.CeilToInt((gridMaxX - gridMinX) / gridCellSize));
        gridResolutionZ = Mathf.Max(1, Mathf.CeilToInt((gridMaxZ - gridMinZ) / gridCellSize));

        int cellCount = gridResolutionX * gridResolutionZ;
        gridHead = new int[cellCount];
        gridNext = new int[instanceArray.Length];
        instanceCellIndex = new int[instanceArray.Length];

        for (int i = 0; i < cellCount; i++)
        {
            gridHead[i] = -1;
        }

        for (int i = 0; i < instanceArray.Length; i++)
        {
            Vector4 instancePosition = instanceArray[i].position_scale;
            int cellIndex = GetCellIndexForPosition(new Vector3(instancePosition.x, instancePosition.y, instancePosition.z));

            gridNext[i] = gridHead[cellIndex];
            gridHead[cellIndex] = i;
            instanceCellIndex[i] = cellIndex;
        }
    }

    private int FindHoveredInstance(Vector3 worldPosition)
    {
        if (gridHead == null || gridNext == null)
            return -1;

        if (!IsWithinCurrentGridBounds(worldPosition))
            return -1;

        int centerCellX = (int)((worldPosition.x - gridMinX) / gridCellSize);
        int centerCellZ = (int)((worldPosition.z - gridMinZ) / gridCellSize);

        if (centerCellX < 0 || centerCellX >= gridResolutionX || centerCellZ < 0 || centerCellZ >= gridResolutionZ)
            return -1;

        float bestDistanceSq = float.MaxValue;
        int bestIndex = -1;
        Vector3 halfExtents = mesh != null ? mesh.bounds.extents : Vector3.one * 0.5f;

        for (int offsetZ = -1; offsetZ <= 1; offsetZ++)
        {
            int cellZ = centerCellZ + offsetZ;
            if (cellZ < 0 || cellZ >= gridResolutionZ)
                continue;

            for (int offsetX = -1; offsetX <= 1; offsetX++)
            {
                int cellX = centerCellX + offsetX;
                if (cellX < 0 || cellX >= gridResolutionX)
                    continue;

                int cellIndex = cellZ * gridResolutionX + cellX;
                for (int candidate = gridHead[cellIndex]; candidate != -1; candidate = gridNext[candidate])
                {
                    Vector4 positionScale = instanceArray[candidate].position_scale;
                    float scaledHalfWidth = halfExtents.x * positionScale.w + hoverPadding;
                    float scaledHalfDepth = halfExtents.z * positionScale.w + hoverPadding;

                    float deltaX = Mathf.Abs(worldPosition.x - positionScale.x);
                    float deltaZ = Mathf.Abs(worldPosition.z - positionScale.z);
                    if (deltaX > scaledHalfWidth || deltaZ > scaledHalfDepth)
                        continue;

                    float distanceSq = deltaX * deltaX + deltaZ * deltaZ;
                    if (distanceSq < bestDistanceSq)
                    {
                        bestDistanceSq = distanceSq;
                        bestIndex = candidate;
                    }
                }
            }
        }

        return bestIndex;
    }

    private void UpdateHoverState()
    {
        if (WasDragPressedThisFrame() && hoveredInstanceIndex >= 0)
        {
            draggingInstanceIndex = hoveredInstanceIndex;
            isDragging = true;

            if (TryGetPointerWorldPosition(out Vector3 pointerWorldPosition))
            {
                Vector4 positionScale = instanceArray[draggingInstanceIndex].position_scale;
                dragPointerOffset = new Vector2(
                    positionScale.x - pointerWorldPosition.x,
                    positionScale.z - pointerWorldPosition.z
                );
            }
        }

        if (isDragging)
        {
            if (WasDragReleasedThisFrame())
            {
                isDragging = false;
                draggingInstanceIndex = -1;
                dragPointerOffset = Vector2.zero;
            }
            else if (TryGetPointerWorldPosition(out Vector3 dragWorldPosition))
            {
                UpdateDraggedInstance(dragWorldPosition);
                return;
            }
        }

        if (!TryGetPointerWorldPosition(out Vector3 worldPosition))
        {
            SetHoveredInstance(-1);
            return;
        }

        SetHoveredInstance(FindHoveredInstance(worldPosition));
    }

    public void SpawnInstances()
    {
        if (!buffersInitialized)
        {
            InitializeBuffers();
        }
        else
        {
            AppendSpawnWave(numberToSpawn);
        }

        spawnButton.interactable = false;
        despawnButton.interactable = true;
    }

    public void DeleteAllCubes()
    {
        if (!buffersInitialized || instanceArray == null || instanceArray.Length == 0)
        {
            ReleaseAllBuffersAndState();

            if (spawnButton != null)
                spawnButton.interactable = true;

            if (despawnButton != null)
                despawnButton.interactable = false;

            return;
        }

        RefreshSecondZoneBounds();

        InstanceData[] survivors = new InstanceData[instanceArray.Length];
        int survivorCount = 0;

        for (int i = 0; i < instanceArray.Length; i++)
        {
            Vector4 positionScale = instanceArray[i].position_scale;
            Vector3 position = new Vector3(positionScale.x, positionScale.y, positionScale.z);
            if (IsPositionInsideSecondZoneXZ(position))
            {
                survivors[survivorCount] = instanceArray[i];
                survivorCount++;
            }
        }

        hoveredInstanceIndex = -1;
        draggingInstanceIndex = -1;
        isDragging = false;
        dragPointerOffset = Vector2.zero;
        hasDebugHitPoint = false;
        material.SetInteger("_HoveredInstance", -1);

        if (survivorCount == 0)
        {
            ReleaseAllBuffersAndState();

            if (spawnButton != null)
                spawnButton.interactable = true;

            if (despawnButton != null)
                despawnButton.interactable = false;

            return;
        }

        instanceArray = new InstanceData[survivorCount];
        for (int i = 0; i < survivorCount; i++)
        {
            instanceArray[i] = survivors[i];
        }

        EnsureInstanceBufferCapacity(survivorCount);
        instanceDataBuffer.SetData(instanceArray, 0, 0, survivorCount);
        UpdateDrawCount(survivorCount);
        BuildHoverGridFromInstances();

        if (spawnButton != null)
            spawnButton.interactable = true;

        if (despawnButton != null)
            despawnButton.interactable = false;
    }

    private void InitializeBuffers()
    {
        
        instanceArray = new InstanceData[numberToSpawn];
        Renderer zoneRenderer = spawnZone.GetComponent<Renderer>();
        if (zoneRenderer == null)
        {
            Debug.LogError("SpawnZone needs a Renderer component.");
            return;
        }
        Bounds bounds = zoneRenderer.bounds;
        spawnZoneBounds = bounds;
        RefreshSecondZoneBounds();

        float minX = bounds.min.x;
        float maxX = bounds.max.x;

        float minZ = bounds.min.z;
        float maxZ = bounds.max.z;
        
        for (int i = 0; i < numberToSpawn; i++)
        {
            Vector3 randomPos = new Vector3(
                UnityEngine.Random.Range(minX, maxX),
                0f,
                UnityEngine.Random.Range(minZ, maxZ)
            );

            instanceArray[i] = CreateInstanceData(randomPos);
        }
        
        instanceDataBuffer = new ComputeBuffer(numberToSpawn, InstanceData.Size());
        instanceBufferCapacity = numberToSpawn;
        
        instanceDataBuffer.SetData(instanceArray);
        material.SetBuffer("_InstanceDataBuffer", instanceDataBuffer);
        material.SetColor("_HoverColor", hoverColor);
        PushZoneMaterialState();
        material.SetInteger("_HoveredInstance", -1);
        cachedHoverCamera = hoverCamera != null ? hoverCamera : Camera.main;
        BuildHoverGridFromInstances();
        
        // arguments used by RenderMeshIndirect
        argsBuffer = new GraphicsBuffer(GraphicsBuffer.Target.IndirectArguments, 1, GraphicsBuffer.IndirectDrawIndexedArgs.size);
        commandData = new GraphicsBuffer.IndirectDrawIndexedArgs[1];
        commandData[0].indexCountPerInstance = mesh.GetIndexCount(0);
        commandData[0].instanceCount = (uint)numberToSpawn;
        commandData[0].startIndex = 0;
        commandData[0].baseVertexIndex = 0;
        commandData[0].startInstance = 0;
        
        argsBuffer.SetData(commandData);
        rp = new RenderParams(material);
        rp.worldBounds = new Bounds(spawnZone.transform.position, new Vector3(500, 500, 500));
        buffersInitialized = true;
    }

    protected virtual void Update()
    {
        FPS_Text.text = "FPS: " + (1f / Time.deltaTime).ToString("F2");
        if (!buffersInitialized)
            return;

        PushZoneMaterialState();
        UpdateHoverState();
        Graphics.RenderMeshIndirect(rp, mesh, argsBuffer, 1);
    }

    private void OnDestroy()
    {
        instanceDataBuffer?.Release();
        instanceDataBuffer = null;

        argsBuffer?.Release();
        argsBuffer = null;
    }

    private void OnDrawGizmos()
    {
        if (!showDebugSphere || !hasDebugHitPoint)
            return;

        Gizmos.color = debugSphereColor;
        Gizmos.DrawSphere(debugHitPoint, debugSphereRadius);
    }

    public void OnInstanceValueChanged(string input)
    {
        if (int.TryParse(input, out int newValue))
        {
            numberToSpawn = newValue;
        }
    }
}
