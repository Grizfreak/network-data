using Unity.Entities;
using Unity.Collections;

public struct LogConfig : IComponentData
{
    public FixedString64Bytes Prefix;
}