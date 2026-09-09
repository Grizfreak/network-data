using Unity.Entities;
using Unity.NetCode;

/// <summary>Netcode bootstrap override that suppresses automatic client/server world creation, since NetworkLauncher creates worlds explicitly.</summary>
public class RemoveAutoWorldCreation : ClientServerBootstrap
{
    // NOTE: `defaultWorldName` is unused for naming a Server/Client world (NetworkLauncher names those itself),
    // but the parameter cannot be removed: this overrides Unity.NetCode.ClientServerBootstrap.Initialize(string),
    // whose signature is fixed by the framework (it is invoked by Netcode's own bootstrap discovery, not by code in this repo).
    public override bool Initialize(string defaultWorldName)
    {
        // Unity.Entities.DefaultWorldInitialization asserts that World.DefaultGameObjectInjectionWorld is set once
        // Initialize() returns true (see ClientServerBootstrap.Initialize's own default implementation, which always
        // creates a world for this). We don't want Netcode's default Server+Client worlds, so create an empty
        // placeholder world instead — it has no systems and NetworkLauncher creates the real Server/Client worlds
        // later on demand, but this satisfies the assertion and gives World.All a safe non-null default until then.
        World.DefaultGameObjectInjectionWorld = new World(defaultWorldName, WorldFlags.Game);
        return true;
    }
}