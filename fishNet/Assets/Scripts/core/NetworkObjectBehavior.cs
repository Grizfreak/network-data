using FishNet.Object;

public class NetworkObjectBehaviour : NetworkBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    public override void OnStartServer()
    {
        ServerManager.Spawn(this.gameObject);
        if (PhaseManager.Instance.moveAndSpawn)
        {
            this.GetComponent<ObjectBehaviour>().isMoving = true;
        }
    }
    
}
