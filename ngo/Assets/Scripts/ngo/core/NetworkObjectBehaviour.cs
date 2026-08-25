using Unity.Netcode;
using UnityEngine;

public class NetworkObjectBehaviour : NetworkBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        if (NetworkManager.IsServer)
        {
            GetComponent<NetworkObject>().Spawn();
            if (PhaseManager.Instance.moveAndSpawn)
            {
                this.GetComponent<ObjectBehaviour>().isMoving = true;
            }
        }
    }
    
}
