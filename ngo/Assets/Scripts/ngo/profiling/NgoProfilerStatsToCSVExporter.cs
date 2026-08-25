using System;
using System.Globalization;
using Unity.Netcode;
using Unity.Netcode.Transports.UTP;
using UnityEngine;

/// <summary>
/// Extends ProfilerStatsToCsvExporter with NGO networking statistics.
/// Appends NGO stats to the SAME CSV row as the base profiler data.
/// </summary>
public class NgoProfilerStatsToCSVExporter : ProfilerStatsToCsvExporter
{

    private UnityTransport _transport;

    protected override void Start()
    {
        base.Start();

        // Append NGO headers to the already-written CSV header line
        if (_textWriter is System.IO.StreamWriter sw)
        {
            try
            {
                sw.Flush();

                var fs = sw.BaseStream;
                var newlineBytes = sw.Encoding
                    .GetBytes(System.Environment.NewLine).Length;

                if (fs.Length >= newlineBytes)
                {
                    fs.Seek(-newlineBytes, System.IO.SeekOrigin.End);

                    sw.Write(",RTT_ms,ConnectedClients");
                    sw.WriteLine();
                    sw.Flush();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning(
                    $"Could not append NGO headers to CSV: {e.Message}");
            }
        }

        TryGetTransport();
    }

    protected override void WriteBucketRow()
    {
        // Let base class write its row first
        base.WriteBucketRow();

        // Retry if transport wasn't ready during Start()
        if (_transport == null)
        {
            TryGetTransport();
        }

        if (_textWriter is System.IO.StreamWriter sw)
        {
            try
            {
                sw.Flush();

                var fs = sw.BaseStream;
                var newlineBytes = sw.Encoding
                    .GetBytes(System.Environment.NewLine).Length;

                if (fs.Length >= newlineBytes)
                {
                    // Remove the newline written by base class
                    fs.Seek(-newlineBytes, System.IO.SeekOrigin.End);

                    float rttMs = GetCurrentRttMs();
                    int connectedClients = GetConnectedClients();

                    sw.Write(",");
                    sw.Write(rttMs.ToString("F1", CultureInfo.InvariantCulture));

                    sw.Write(",");
                    sw.Write(connectedClients);

                    sw.WriteLine();
                    sw.Flush();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning(
                    $"Could not append NGO stats to CSV row: {e.Message}");
            }
        }
    }

    private void TryGetTransport()
    {
        if (NetworkManager.Singleton == null)
        {
            return;
        }

        _transport = NetworkManager.Singleton.NetworkConfig.NetworkTransport
            as UnityTransport;

        if (_transport == null)
        {
            Debug.LogWarning(
                "NgoProfilerStatsToCSVExporter: UnityTransport not found.");
        }
    }

    /// <summary>
    /// RTT in milliseconds.
    /// </summary>
    private float GetCurrentRttMs()
    {
        if (_transport == null)
        {
            return 0f;
        }

        if (NetworkManager.Singleton == null)
        {
            return 0f;
        }

        if (!NetworkManager.Singleton.IsClient)
        {
            return 0f;
        }

        try
        {
            ulong serverClientId = NetworkManager.ServerClientId;

            // Unity Transport returns RTT in milliseconds
            return _transport.GetCurrentRtt(serverClientId);
        }
        catch
        {
            return 0f;
        }
    }

    private int GetConnectedClients()
    {
        if (NetworkManager.Singleton == null)
        {
            return 0;
        }

        return NetworkManager.Singleton.ConnectedClientsList.Count;
    }

}