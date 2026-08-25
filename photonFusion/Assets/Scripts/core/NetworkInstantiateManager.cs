using System.Collections;
using Fusion;
using UnityEngine;

public class NetworkInstantiateManager : InstantiateManager
{
    private NetworkRunner _runner => NetworkLauncher.Instance.Runner;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    protected override IEnumerator SpawnObjects()
        {
            yield return new WaitForSeconds(timeBeforeSpawn);
            StartingInstantiation.Invoke("StartedInstantiation");
            for (int i = 0; i < numberToSpawn; i++)
            {
                float x = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.x, spawnZone.GetComponent<Renderer>().bounds.max.x);
                float z = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.z, spawnZone.GetComponent<Renderer>().bounds.max.z);
                Vector3 spawnPos = new Vector3(x, 0, z);
                var go = _runner.Spawn(objectToSpawn, spawnPos, transform.rotation);
                if (PhaseManager.Instance.moveAndSpawn)
                {
                    go.GetComponent<ObjectBehaviour>().isMoving = true;
                }
                OnInstanceCreated.Invoke(go.gameObject);
            }
            FinishedInstantiation.Invoke("FinishedInstantiation", numberToSpawn);
            PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
        }

        protected override IEnumerator SpawnObjectsByGroup()
        {
            while (SpawnedInstances < numberToSpawn)
            {
                yield return new WaitForSeconds(timeBeforeSpawn);
                StartingInstantiation.Invoke("StartedInstantiation");
                for (int i = 0; i < numberPerWave; i++)
                {
                    float x = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.x, spawnZone.GetComponent<Renderer>().bounds.max.x);
                    float z = Random.Range(spawnZone.GetComponent<Renderer>().bounds.min.z, spawnZone.GetComponent<Renderer>().bounds.max.z);
                    Vector3 spawnPos = new Vector3(x, 0, z);
                    var go = _runner.Spawn(objectToSpawn, spawnPos, transform.rotation);
                    if (PhaseManager.Instance.moveAndSpawn)
                    {
                        go.GetComponent<ObjectBehaviour>().isMoving = true;
                    }
                    OnInstanceCreated.Invoke(go.gameObject);
                }
                SpawnedInstances+= numberPerWave;
                FinishedInstantiation.Invoke("FinishedInstantiation", SpawnedInstances);
            }
            PhaseManager.Instance.PhaseFinished.Invoke("PhaseFinished");
        }
}
