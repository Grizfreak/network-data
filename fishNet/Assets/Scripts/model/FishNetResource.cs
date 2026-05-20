using UnityEngine;

[CreateAssetMenu(fileName = "FishNetResource", menuName = "Scriptable Objects/FishNetResource")]
public class FishNetResource : BaseResource
{
    [Header("FishNet")]
    public float syncInterval;
}
