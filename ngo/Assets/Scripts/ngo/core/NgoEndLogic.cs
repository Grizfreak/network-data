using System;
using System.Collections;
using Unity.Netcode;
using Unity.Networking.Transport;
using UnityEngine;

public class NgoEndLogic : NetworkBehaviour
{
    private bool finishedClient = false;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        if (NetworkManager.Singleton.IsServer)
        {
            PhaseManager.Instance.FinishingExperimentation += FinishExperiment;
        }

        if (NetworkManager.Singleton.IsClient)
        {
            NetworkManager.Singleton.OnClientDisconnectCallback += OnClientDisconnected;
        }
    }
    
    private void FinishExperiment()
    {
        PhaseManager.Instance.FinishTest(false);
        StartCoroutine(SendRpcPeriodically(FinishExperimentRpc, 1f,0f, 60f));
    }
    
    [Rpc(SendTo.NotServer)]
    public void FinishExperimentRpc()
    {
        CallbackServerFinishRpc();
        PhaseManager.Instance.FinishTest();
    }
    
    [Rpc(SendTo.Server)]
    public void CallbackServerFinishRpc()
    {
        finishedClient = true;
    }
    
        
    private IEnumerator SendRpcPeriodically(Action rpcMethod, float interval, float waitBeforeStoppingMovingCubes, float timeBeforeQuittingEarly)
    {
        float timeElapsed = 0f;
        bool activated = false;
        bool quittedEarly = false;
        while (!finishedClient)
        {
            rpcMethod.Invoke();
            yield return new WaitForSeconds(interval);
            
            if (timeElapsed > waitBeforeStoppingMovingCubes && !activated)
            {
                activated = true;
                MoveManager.Instance.stopMoving = true;
            }
            else
            {
                timeElapsed += interval;
            }

            if (timeElapsed > timeBeforeQuittingEarly && !quittedEarly)
            {
                quittedEarly = true;
                Debug.Log("Client took too long time to respond, exiting the server.");
                PhaseManager.Instance.FinishTest();
            }
        }
        PhaseManager.Instance.FinishTest();
    }

    private void OnClientDisconnected(ulong connectionId)
    {
        Debug.Log("Client disconnected in a non-good way.. exiting the app");
        PhaseManager.Instance.FinishTest();
    }
}
