using System;
using System.Collections;
using Unity.Mathematics;
using UnityEngine;

public class GPUIndirectInstantiateManager : InstantiateManager
{

    [SerializeField] private Mesh mesh;
    [SerializeField] private Material material;
    [SerializeField] private ComputeShader computeShader;
    private ComputeBuffer instanceDataBuffer;
    private GraphicsBuffer argsBuffer;
    private GraphicsBuffer.IndirectDrawIndexedArgs[] commandData;
    private InstanceData[] instanceArray;
    private RenderParams rp;
    private bool buffersInitialized = false;
    private int kernel;
    
    private struct InstanceData {
        public Vector4 position_scale;
        public float yaw;
        public float isShown;
        public float isMoving;
        public float verticalVelocity;
        
        public static int Size()
        {
            return sizeof(float) * 4 +
                   sizeof(float) +
                   sizeof(float) +
                   sizeof(float) +
                   sizeof(float);
        }
    }

    protected override void Start()
    {
        base.Start();
        computeShader.SetFloat("_MoveSpeed", 5f);
        computeShader.SetFloat("_Gravity", 9.81f);
        computeShader.SetFloat("_JumpForce", 5f);
    }

    protected override IEnumerator SpawnObjects()
    {
        // Initialize buffer
        InitializeBuffers();
        yield return new WaitForSeconds(timeBeforeSpawn);
        StartingInstantiation.Invoke("StartedInstantiation");
        
        for (int i = 0; i < numberToSpawn; i++)
        {
            instanceArray[i].isShown = 1f;
        }
        
        instanceDataBuffer.SetData(instanceArray);
        FinishedInstantiation.Invoke("FinishedInstantiation", numberToSpawn);
        PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
    }

    protected override IEnumerator SpawnObjectsByGroup()
    {
        // Initialize buffer
        InitializeBuffers();
        
        while (SpawnedInstances < numberToSpawn)
        {
            yield return new WaitForSeconds(timeBeforeSpawn);
            StartingInstantiation.Invoke("StartedInstantiation");
            int start = SpawnedInstances;
            int end = Mathf.Min(
                SpawnedInstances + numberPerWave,
                numberToSpawn
            );

            for (int i = start; i < end; i++)
            {
                instanceArray[i].isShown = 1f;
            }

            SpawnedInstances = end;

            instanceDataBuffer.SetData(instanceArray);
            SpawnedInstances+= numberPerWave;
            FinishedInstantiation.Invoke("FinishedInstantiation", SpawnedInstances);
        }
        PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
    }

    private void InitializeBuffers()
    {
        kernel = computeShader.FindKernel("CSMain");
        
        instanceArray = new InstanceData[numberToSpawn];
        Renderer zoneRenderer = spawnZone.GetComponent<Renderer>();
        if (zoneRenderer == null)
        {
            Debug.LogError("SpawnZone needs a Renderer component.");
            return;
        }
        Bounds bounds = zoneRenderer.bounds;

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

            instanceArray[i] = new InstanceData
            {
                position_scale = new float4(randomPos.x, randomPos.y, randomPos.z, 1f),
                yaw = 0f,
                isShown = 0f,
                isMoving = 0f,
                verticalVelocity = 0f
            };
        }
        
        instanceDataBuffer = new ComputeBuffer(
            numberToSpawn,
            InstanceData.Size()
        );
        
        instanceDataBuffer.SetData(instanceArray);
        material.SetBuffer("_InstanceDataBuffer", instanceDataBuffer);
        
        // arguments used by RenderMeshIndirect
        argsBuffer = new GraphicsBuffer(GraphicsBuffer.Target.IndirectArguments, 1, GraphicsBuffer.IndirectDrawIndexedArgs.size);
        commandData = new GraphicsBuffer.IndirectDrawIndexedArgs[1];
        commandData[0].indexCountPerInstance = mesh.GetIndexCount(0);
        commandData[0].instanceCount = (uint)numberToSpawn;
        commandData[0].startIndex = 0;
        commandData[0].baseVertexIndex = 0;
        commandData[0].startInstance = 0;
        
        argsBuffer.SetData(commandData);
        computeShader.SetBuffer(kernel, "_InstanceDataBuffer", instanceDataBuffer);
        rp = new RenderParams(material);
        rp.worldBounds = new Bounds(spawnZone.transform.position, new Vector3(500, 500, 500));
        buffersInitialized = true;
    }

    public void SetMovingRange(int start, int end)
    {
        end = Mathf.Min(end, numberToSpawn);

        for (int i = start; i < end; i++)
        {
            instanceArray[i].isMoving = 1f;
        }

        instanceDataBuffer.SetData(instanceArray);
    }

    private void Update()
    {
        if (!buffersInitialized)
            return;
        computeShader.SetFloat("_DeltaTime", Time.deltaTime);
        int groups = Mathf.CeilToInt(numberToSpawn / 64f);

        computeShader.Dispatch(kernel, groups, 1, 1);
        Graphics.RenderMeshIndirect(rp, mesh, argsBuffer, 1);
    }

    private void OnDestroy()
    {
        instanceDataBuffer?.Release();
        instanceDataBuffer = null;

        argsBuffer?.Release();
        argsBuffer = null;
    }
}
