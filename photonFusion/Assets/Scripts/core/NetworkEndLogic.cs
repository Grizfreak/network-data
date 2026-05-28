using Fusion;
using UnityEngine;

public class NetworkEndLogic : NetworkBehaviour
{

    public override void Spawned()
    {
        Debug.Log($"Spawned: {name}");
    }

    public void Start()
    {
        PhaseManager.Instance.FinishingExperimentation += DisconnectClientsThenStop;
    }

    private void DisconnectClientsThenStop()
    {
        if (NetworkLauncher.Instance.Runner != null)
        {
            if (NetworkLauncher.Instance.Runner.IsServer)
            {
                RPC_DisconnectClients();
                PhaseManager.Instance.FinishTest();
            }
        }
    }

    [Rpc(RpcSources.StateAuthority, RpcTargets.Proxies)]
    private void RPC_DisconnectClients()
    {
        Debug.Log("Disconnecting clients...");
        if (NetworkLauncher.Instance.Runner != null)
        {
            if (NetworkLauncher.Instance.Runner.IsServer)
            {
                return;
            }
            PhaseManager.Instance.FinishTest();
            NetworkLauncher.Instance.Runner.Shutdown();
        }
    }

    void OnDestroy()
    {
        WiresharkManager.Instance.StopTracking();
    }
}
