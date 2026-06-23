using Unity.NetCode;

public class RemoveAutoWorldCreation : ClientServerBootstrap
{
    public override bool Initialize(string defaultWorldName)
    {
        // Don't auto-create worlds
        return true;
    }
}