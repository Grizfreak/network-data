using Unity.Entities;
using Unity.Collections;

/// <summary>Singleton carrying the file name prefix ("..._client_"/"..._server_") used when naming exported log/CSV files.</summary>
public struct LogConfig : IComponentData
{
    public FixedString64Bytes Prefix;
}