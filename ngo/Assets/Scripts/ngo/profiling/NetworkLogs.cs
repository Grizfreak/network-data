using System;
using System.Collections;
using Unity.Netcode;
using UnityEngine;

public class NetworkLogs : NetworkBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        LogsManager manager = this.gameObject.GetComponent<LogsManager>();
        if (manager == null)
        {
            Debug.LogWarning("Manager not found");
        }
        ProfilerStatsToCsvExporter profiler = this.gameObject.GetComponent<ProfilerStatsToCsvExporter>();
        if (profiler == null)
        {
            Debug.LogWarning("Profiler not found");
        }

        if (NetworkManager.IsServer)
        {
            InstantiateManager.Instance.StartingInstantiation += SendClientEventSiRpc;
            InstantiateManager.Instance.FinishedInstantiation += SendClientEventFiRpc;
            PhaseManager.Instance.PhaseStarted += SendClientEventPSRpc;
            PhaseManager.Instance.PhaseFinished += SendClientEventPfRpc;
            MoveManager.Instance.StartMovingEntities += SendClientEventSmeRpc;
            MoveManager.Instance.EndMovingEntities += SendClientEventEmeRpc;
            manager.eventsFileName = "ngo_server_"+ manager.eventsFileName;
            profiler.outputName = "ngo_server_" + profiler.outputName;
        }
        else if (NetworkManager.IsClient)
        {
            manager.eventsFileName = "ngo_client_"+ manager.eventsFileName;
            profiler.outputName = "ngo_client_" + profiler.outputName;
        }
    }

    [Rpc(SendTo.NotServer)]
    private void SendClientEventSiRpc(string msg)
    {
        InstantiateManager.Instance.StartingInstantiation.Invoke(msg);
    }
    
    [Rpc(SendTo.NotServer)]
    private void SendClientEventFiRpc(string msg, int value)
    {
        InstantiateManager.Instance.FinishedInstantiation.Invoke(msg, value);
    }
    
    [Rpc(SendTo.NotServer)]
    private void SendClientEventPSRpc(string msg)
    {
        PhaseManager.Instance.PhaseStarted.Invoke(msg);
    }
    
    [Rpc(SendTo.NotServer)]
    private void SendClientEventPfRpc(string msg)
    {
        PhaseManager.Instance.PhaseFinished.Invoke(msg);
    }
    
    [Rpc(SendTo.NotServer)]
    private void SendClientEventSmeRpc(string msg)
    {
        MoveManager.Instance.StartMovingEntities.Invoke(msg);
    }
    
    [Rpc(SendTo.NotServer)]
    private void SendClientEventEmeRpc(string msg)
    {
        MoveManager.Instance.EndMovingEntities.Invoke(msg);
    }
    
}
