using System;
using System.Collections.Generic;
using UnityEngine;

public static class ResourceTypeRegistry
{
    private static readonly Dictionary<string, Func<BaseResource>> registry =
        new Dictionary<string, Func<BaseResource>>();

    public static void Register(string type, Func<BaseResource> factory)
    {
        if (string.IsNullOrEmpty(type))
        {
            Debug.LogError("Trying to register a null or empty type.");
            return;
        }

        registry[type] = factory;
    }

    public static BaseResource Create(string type)
    {
        if (!string.IsNullOrEmpty(type) && registry.TryGetValue(type, out var factory))
        {
            return factory();
        }

        // Fallback to base type
        return ScriptableObject.CreateInstance<BaseResource>();
    }
}