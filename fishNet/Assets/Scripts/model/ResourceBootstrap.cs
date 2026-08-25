using UnityEngine;

public static class ResourceBootstrap
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void Register()
    {
        ResourceTypeRegistry.Register("fishNet", ScriptableObject.CreateInstance<FishNetResource>);
    }
}