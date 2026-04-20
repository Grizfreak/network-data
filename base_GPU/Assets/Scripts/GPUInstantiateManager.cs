using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;

public class GPUInstantiateManager : InstantiateManager
{
    [Header("GPU Instancing")]
    public Mesh instanceMesh;
    public Material instanceMaterial;

    private struct InstanceData
    {
        public Vector3 position;
        public Quaternion rotation;
        public float verticalVelocity;
        public bool isMoving;
    }

    private readonly List<InstanceData> _instances = new();
    private readonly Matrix4x4[] _matrices = new Matrix4x4[1023];

    protected override IEnumerator SpawnObjects()
    {
        yield return new WaitForSeconds(timeBeforeSpawn);

        StartingInstantiation?.Invoke("StartedInstantiation");

        for (int i = 0; i < numberToSpawn; i++)
        {
            AddInstance(GetRandomPosition());
        }

        FinishedInstantiation?.Invoke(
            "FinishedInstantiation",
            _instances.Count
        );

        PhaseManager.Instance.PhaseFinished?.Invoke("PhaseFinished");
    }

    public int TotalInstanceCount()
    {
        return _instances.Count;
    }

    public int MovingInstanceCount()
    {
        return _instances.Count(inst => inst.isMoving);
    }

    protected override IEnumerator SpawnObjectsByGroup()
    {
        int spawned = 0;

        while (spawned < numberToSpawn)
        {
            yield return new WaitForSeconds(timeBeforeSpawn);

            StartingInstantiation?.Invoke("StartedInstantiation");

            int toSpawn = Mathf.Min(
                numberPerWave,
                numberToSpawn - spawned
            );

            for (int i = 0; i < toSpawn; i++)
            {
                AddInstance(GetRandomPosition());
            }

            spawned += toSpawn;

            FinishedInstantiation?.Invoke(
                "FinishedInstantiation",
                spawned
            );
        }

        PhaseManager.Instance.PhaseFinished?.Invoke("PhaseFinished");
    }

    private void Update()
    {
        float dt = Time.deltaTime;

        for (int i = 0; i < _instances.Count; i++)
        {
            var inst = _instances[i];

            if (!inst.isMoving)
                continue;

            inst.position += inst.rotation * Vector3.forward * (5f * dt);

            if (inst.position.y <= 0f && inst.verticalVelocity <= 0f)
                inst.verticalVelocity = 5f;

            inst.verticalVelocity -= 1f * dt;
            inst.position.y += inst.verticalVelocity * dt;

            if (inst.position.y < 0f)
            {
                inst.position.y = 0f;
                inst.verticalVelocity = 0f;
            }

            inst.rotation *= Quaternion.Euler(
                0f,
                90f * dt,
                0f
            );

            _instances[i] = inst;
        }
    }
    
    private void LateUpdate()
    {
        RenderInstances();
    }

    private void AddInstance(Vector3 position)
    {
        _instances.Add(new InstanceData
        {
            position = position,
            rotation = Quaternion.identity,
            verticalVelocity = 0f,
            isMoving = false
        });

        // keep package event alive if needed
        OnInstanceCreated?.Invoke(null);
    }

    private void RenderInstances()
    {
        if (instanceMesh == null || instanceMaterial == null)
            return;

        for (int start = 0; start < _instances.Count; start += 1023)
        {
            int count = Mathf.Min(
                1023,
                _instances.Count - start
            );

            for (int i = 0; i < count; i++)
            {
                var inst = _instances[start + i];

                _matrices[i] = Matrix4x4.TRS(
                    inst.position,
                    inst.rotation,
                    Vector3.one
                );
            }

            Graphics.DrawMeshInstanced(
                instanceMesh,
                0,
                instanceMaterial,
                _matrices,
                count,
                null,
                ShadowCastingMode.On,
                true
            );
        }
    }

    private Vector3 GetRandomPosition()
    {
        Renderer r = spawnZone.GetComponent<Renderer>();
        Bounds b = r.bounds;

        float x = Random.Range(b.min.x, b.max.x);
        float z = Random.Range(b.min.z, b.max.z);

        return new Vector3(x, 0f, z);
    }
    
    public int StartMovingWave(int amountToMove)
    {
        int moved = 0;

        for (int i = 0; i < _instances.Count && moved < amountToMove; i++)
        {
            var inst = _instances[i];

            if (inst.isMoving)
                continue;

            inst.isMoving = true;
            _instances[i] = inst;
            moved++;
        }

        return moved;
    }
}