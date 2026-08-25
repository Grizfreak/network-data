using System;
using System.Reflection;
using UnityEngine;
using Unity.Netcode;
using Unity.Netcode.Transports.UTP;

public class NetworkBenchmarkNGO : MonoBehaviour, INetworkBenchmarkProvider
{
    private UnityTransport _transport;

    private Func<long> _getBytesSentDelegate;
    private Func<long> _getBytesReceivedDelegate;

    private void Start()
    {
        TryGetTransport();
        SetupReflectionDelegates();
    }

    private void TryGetTransport()
    {
        if (NetworkManager.Singleton == null)
            return;

        _transport = NetworkManager.Singleton.NetworkConfig.NetworkTransport as UnityTransport;
    }

    public float GetRttMs()
    {
        if (_transport == null)
            TryGetTransport();

        if (_transport == null || NetworkManager.Singleton == null || !NetworkManager.Singleton.IsClient)
            return 0f;

        try
        {
            ulong serverClientId = NetworkManager.ServerClientId;
            return _transport.GetCurrentRtt(serverClientId);
        }
        catch
        {
            return 0f;
        }
    }

    private void SetupReflectionDelegates()
    {
        // Try to locate a runtime type that exposes cumulative bytes sent/received.
        string[] candidateTypeNames = new[] {
            "NetworkMetrics",
            "NetworkMetricsStorage",
            "NetworkMetricsProvider",
            "NetworkStats",
            "NetStats"
        };

        foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
        {
            foreach (var typeName in candidateTypeNames)
            {
                Type t = asm.GetType(typeName) ?? asm.GetType("Unity.Multiplayer.Tools.NetStats." + typeName) ?? asm.GetType("Unity.Multiplayer.Tools.MetricTypes." + typeName);
                if (t == null)
                    continue;

                var members = t.GetMembers(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);

                foreach (var m in members)
                {
                    string n = m.Name.ToLowerInvariant();

                    if (_getBytesSentDelegate == null && n.Contains("byt") && (n.Contains("sent") || n.Contains("upload") || n.Contains("uploadbytes")))
                    {
                        var getter = CreateLongGetter(t, m);
                        if (getter != null)
                            _getBytesSentDelegate = getter;
                    }

                    if (_getBytesReceivedDelegate == null && n.Contains("byt") && (n.Contains("recv") || n.Contains("received") || n.Contains("download") || n.Contains("downloadbytes")))
                    {
                        var getter = CreateLongGetter(t, m);
                        if (getter != null)
                            _getBytesReceivedDelegate = getter;
                    }

                    if (_getBytesSentDelegate != null && _getBytesReceivedDelegate != null)
                        return;
                }
            }
        }
    }

    private Func<long> CreateLongGetter(Type t, MemberInfo m)
    {
        try
        {
            if (m is PropertyInfo pi)
            {
                if (pi.GetMethod != null && pi.GetMethod.IsStatic)
                    return () => Convert.ToInt64(pi.GetValue(null));
            }

            if (m is FieldInfo fi)
            {
                if (fi.IsStatic)
                    return () => Convert.ToInt64(fi.GetValue(null));
            }

            if (m is MethodInfo mi)
            {
                if (mi.IsStatic && mi.GetParameters().Length == 0)
                    return () => Convert.ToInt64(mi.Invoke(null, null));
            }
        }
        catch
        {
            // ignore
        }

        return null;
    }

    public long GetBytesSent()
    {
        if (_getBytesSentDelegate == null)
            SetupReflectionDelegates();

        try
        {
            if (_getBytesSentDelegate != null)
                return _getBytesSentDelegate();
        }
        catch
        {
        }

        return 0;
    }

    public long GetBytesReceived()
    {
        if (_getBytesReceivedDelegate == null)
            SetupReflectionDelegates();

        try
        {
            if (_getBytesReceivedDelegate != null)
                return _getBytesReceivedDelegate();
        }
        catch
        {
        }

        return 0;
    }
}