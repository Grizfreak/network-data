using System;
using System.Collections;
using FishNet.Object;
using FishNet.Transporting;
using UnityEngine;

public class FishnetEndLogic : NetworkBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    private bool finishedClient = false;
    // Start is called once before the first execution of Update after the MonoBehaviour is created

    public override void OnStartServer()
    {
        PhaseManager.Instance.FinishingExperimentation += FinishExperiment;
    }

    public override void OnStartClient()
    {
        ClientManager.OnClientConnectionState += OnClientDisconnected;
    }
    
    private void FinishExperiment()
    {
        PhaseManager.Instance.FinishTest(false);
        StartCoroutine(SendRpcPeriodically(FinishExperimentRpc, 1f,0f, 60f));
    }
    
    [ObserversRpc]
    public void FinishExperimentRpc()
    {
        CallbackServerFinishRpc();
        PhaseManager.Instance.FinishTest();
    }
    
    [ServerRpc(RequireOwnership = false)]
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

    private void OnClientDisconnected(ClientConnectionStateArgs args)
    {
        if (args.ConnectionState == LocalConnectionState.Stopped)
        {
            Debug.Log("Client disconnected in a non-good way.. exiting the app");
            PhaseManager.Instance.FinishTest();
        }
    }

    void OnDestroy()
    {
        WiresharkManager.Instance.StopTracking();
    }
}