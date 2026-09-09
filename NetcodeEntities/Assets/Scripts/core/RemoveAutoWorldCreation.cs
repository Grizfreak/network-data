using Unity.NetCode;

/// <summary>Netcode bootstrap override that suppresses automatic client/server world creation, since NetworkLauncher creates worlds explicitly.</summary>
public class RemoveAutoWorldCreation : ClientServerBootstrap
{
    public override bool Initialize(string defaultWorldName)
    {
        // Returning true tells Netcode this bootstrap handled initialization, so it skips its default world creation.
        return true;
    }
}