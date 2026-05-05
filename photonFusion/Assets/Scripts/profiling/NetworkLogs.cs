using Fusion;
using UnityEngine;

public class NetworkLogs : NetworkBehaviour
{
    private NetworkRunner _runner => NetworkLauncher.Instance.Runner;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        LogsManager manager = PhaseManager.Instance.gameObject.GetComponent<LogsManager>();
        if (manager == null)
        {
            Debug.LogError("Failed to add LogsManager component to NetworkLogs.");
        }
        ProfilerStatsToCsvExporter exporter = PhaseManager.Instance.gameObject.GetComponent<ProfilerStatsToCsvExporter>();
        if (exporter == null)
        {
            Debug.LogError("Failed to add ProfilerStatsToCsvExporter component to NetworkLogs.");
        }

        if (_runner.IsServer)
        {
            //TODO
            InstantiateManager.Instance.StartingInstantiation += SendClientEventSiRpc;
            InstantiateManager.Instance.FinishedInstantiation += SendClientEventFiRpc;
            PhaseManager.Instance.PhaseStarted += SendClientEventPSRpc;
            PhaseManager.Instance.PhaseFinished += SendClientEventPfRpc;
            MoveManager.Instance.StartMovingEntities += SendClientEventSmeRpc;
            MoveManager.Instance.EndMovingEntities += SendClientEventEmeRpc;
            // SEND Client RPCS
            manager.eventsFileName = "photon_server_" + manager.eventsFileName;
            exporter.outputName = "photon_server_" + exporter.outputName;
        }
        else if (_runner.IsClient)
        {
            PhaseManager.Instance.autoLinkingPhase = false;
            manager.eventsFileName = "photon_client_" + manager.eventsFileName;
            exporter.outputName = "photon_client_" + exporter.outputName;
        }
    }

    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
    private void SendClientEventSiRpc(string msg)
    {
        InstantiateManager.Instance.StartingInstantiation.Invoke(msg);
    }
    
    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
    private void SendClientEventFiRpc(string msg, int value)
    {
        InstantiateManager.Instance.FinishedInstantiation.Invoke(msg, value);
    }
    
    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
    private void SendClientEventPSRpc(string msg)
    {
        PhaseManager.Instance.PhaseStarted.Invoke(msg);
    }
    
    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
    private void SendClientEventPfRpc(string msg)
    {
        PhaseManager.Instance.PhaseFinished.Invoke(msg);
    }
    
    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
    private void SendClientEventSmeRpc(string msg)
    {
        MoveManager.Instance.StartMovingEntities.Invoke(msg);
    }
    
    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
    private void SendClientEventEmeRpc(string msg)
    {
        MoveManager.Instance.EndMovingEntities.Invoke(msg);
    }
}
