using System;
using System.Collections;
using FishNet.Object;
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

        if (NetworkManager.IsServerStarted)
        {
            InstantiateManager.Instance.StartingInstantiation += SendClientEventSiRpc;
            InstantiateManager.Instance.FinishedInstantiation += SendClientEventFiRpc;
            PhaseManager.Instance.PhaseStarted += SendClientEventPSRpc;
            PhaseManager.Instance.PhaseFinished += SendClientEventPfRpc;
            MoveManager.Instance.StartMovingEntities += SendClientEventSmeRpc;
            MoveManager.Instance.EndMovingEntities += SendClientEventEmeRpc;
            manager.eventsFileName = "fishNet_server_"+ manager.eventsFileName;
            profiler.outputName = "fishNet_server_" + profiler.outputName;
        }
        else if (NetworkManager.IsClientStarted)
        {
            manager.eventsFileName = "fishNet_client_"+ manager.eventsFileName;
            profiler.outputName = "fishNet_client_" + profiler.outputName;
        }
    }

    [ObserversRpc]
    private void SendClientEventSiRpc(string msg)
    {
        InstantiateManager.Instance.StartingInstantiation.Invoke(msg);
    }
    
    [ObserversRpc]
    private void SendClientEventFiRpc(string msg, int value)
    {
        InstantiateManager.Instance.FinishedInstantiation.Invoke(msg, value);
    }
    
    [ObserversRpc]
    private void SendClientEventPSRpc(string msg)
    {
        PhaseManager.Instance.PhaseStarted.Invoke(msg);
    }
    
    [ObserversRpc]
    private void SendClientEventPfRpc(string msg)
    {
        PhaseManager.Instance.PhaseFinished.Invoke(msg);
    }
    
    [ObserversRpc]
    private void SendClientEventSmeRpc(string msg)
    {
        MoveManager.Instance.StartMovingEntities.Invoke(msg);
    }
    
    [ObserversRpc]
    private void SendClientEventEmeRpc(string msg)
    {
        MoveManager.Instance.EndMovingEntities.Invoke(msg);
    }
    
}
