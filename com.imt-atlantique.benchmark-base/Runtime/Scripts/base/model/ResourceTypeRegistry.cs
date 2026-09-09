using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>Maps a JSON "type" string to a BaseResource subclass factory, so config files can select a resource variant.</summary>
public static class ResourceTypeRegistry
{
    private static readonly Dictionary<string, Func<BaseResource>> registry =
        new Dictionary<string, Func<BaseResource>>();

    /// <summary>Registers a factory that creates a BaseResource subclass for the given type name.</summary>
    public static void Register(string type, Func<BaseResource> factory)
    {
        if (string.IsNullOrEmpty(type))
        {
            Debug.LogError("Trying to register a null or empty type.");
            return;
        }

        registry[type] = factory;
    }

    /// <summary>Creates a BaseResource instance for the given type, falling back to the base type if unregistered.</summary>
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