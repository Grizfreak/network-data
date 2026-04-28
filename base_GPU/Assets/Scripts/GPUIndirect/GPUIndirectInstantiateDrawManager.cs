using System;
using System.Collections;
using Unity.Mathematics;
using UnityEngine;

public class GPUIndirectInstantiateDrawManager : GPUIndirectInstantiateManager
{
    private ComputeBuffer argsBuffer;
    private uint[] args = new uint[5];

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
        
        args[1] = (uint)numberToSpawn;
        argsBuffer.SetData(args);
        instanceDataBuffer.SetData(instanceArray);
        FinishedInstantiation.Invoke("FinishedInstantiation", numberToSpawn);
        buffersInitialized = true;
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
            args[1] = (uint)SpawnedInstances;
            argsBuffer.SetData(args);
            instanceDataBuffer.SetData(instanceArray);
            FinishedInstantiation.Invoke("FinishedInstantiation", SpawnedInstances);
            buffersInitialized = true;
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
        argsBuffer = new ComputeBuffer(
            1,
            args.Length * sizeof(uint),
            ComputeBufferType.IndirectArguments
        );
        args[0] = (uint)mesh.GetIndexCount(0);
        args[1] = 0; // IMPORTANT: start hidden
        args[2] = (uint)mesh.GetIndexStart(0);
        args[3] = (uint)mesh.GetBaseVertex(0);
        args[4] = 0;

        argsBuffer.SetData(args);
        computeShader.SetBuffer(kernel, "_InstanceDataBuffer", instanceDataBuffer);
        rp = new RenderParams(material);
        rp.worldBounds = new Bounds(spawnZone.transform.position, new Vector3(500, 500, 500));
    }

    public override void SetMovingRange(int start, int end)
    {
        end = Mathf.Min(end, numberToSpawn);

        for (int i = start; i < end; i++)
        {
            instanceArray[i].isMoving = 1f;
        }

        instanceDataBuffer.SetData(instanceArray);
    }

    protected override void Update()
    {
        if (!buffersInitialized)
            return;
        computeShader.SetFloat("_DeltaTime", Time.deltaTime);
        int groups = Mathf.CeilToInt(numberToSpawn / 64f);

        computeShader.Dispatch(kernel, groups, 1, 1);
        
        Graphics.DrawMeshInstancedIndirect(
            mesh,
            0,
            material,
            rp.worldBounds,
            argsBuffer
        );
    }

    private void OnDestroy()
    {
        instanceDataBuffer?.Release();
        instanceDataBuffer = null;

        argsBuffer?.Release();
        argsBuffer = null;
    }
}
