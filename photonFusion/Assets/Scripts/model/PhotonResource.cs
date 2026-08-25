using UnityEngine;

[CreateAssetMenu(fileName = "PhotonResource", menuName = "Scriptable Objects/PhotonResource")]
public class PhotonResource : BaseResource
{
    [Header("Photon")]
    public float syncInterval;
}
