using Unity.Entities;

/// <summary>Shared helper for locating the benchmark's own Server/Client ECS world, falling back to the default injection world.</summary>
public static class WorldResolver
{
    // Prefer the benchmark's own Server/Client world over the default injection world, which may not host the singleton.
    public static World ResolveWorld()
    {
        foreach (var world in World.All)
        {
            if (world.Name == "Server" || world.Name == "Client")
            {
                return world;
            }
        }

        return World.DefaultGameObjectInjectionWorld;
    }
}
