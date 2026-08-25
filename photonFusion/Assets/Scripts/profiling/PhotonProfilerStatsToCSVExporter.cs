using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using @base.model;
using Fusion;
using Fusion.Statistics;
using Unity.Profiling;
using UnityEngine;

/// <summary>
/// This component will export the specified Profiler stats to a CSV file in the application persistent data path.
/// Data is written in time-based buckets (default: every 0.5s) so that the X axis reflects real elapsed time,
/// making graphs readable regardless of FPS fluctuations.
/// cf. https://docs.unity3d.com/ScriptReference/Unity.Profiling.ProfilerRecorder.html
/// </summary>
public class PhotonProfilerStatsToCsvExporter : ProfilerStatsToCsvExporter
{
    private FusionStatisticsManager _statsManager;
    protected override void Start()
    {
        base.Start();

        // Append additional CSV header columns to the header line written by the base class.
        if (_textWriter is System.IO.StreamWriter sw)
        {
            try
            {
                sw.Flush();
                var fs = sw.BaseStream;
                var newlineBytes = sw.Encoding.GetBytes(System.Environment.NewLine).Length;
                if (fs.Length >= newlineBytes)
                {
                    fs.Seek(-newlineBytes, System.IO.SeekOrigin.End);
                    sw.Write(",Ping_ms,TotalBytesReceived,TotalBytesSent,PacketsIn,PacketsOut,InputBandwidthIn,InputBandwidthOut,ObjectBandwidthIn,ObjectBandwidthOut");
                    sw.WriteLine();
                    sw.Flush();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"Could not append headers in PhotonProfilerStatsToCsvExporter: {e.Message}");
            }
        }

        NetworkRunner runner = NetworkLauncher.Instance?.Runner;
        if (runner != null)
        {
            if (runner.TryGetFusionStatistics(out _statsManager))
            {
                Debug.Log("Successfully obtained FusionStatisticsManager from NetworkRunner.");
            }
            else
            {
                Debug.LogWarning("Failed to obtain FusionStatisticsManager from NetworkRunner.");
            }
        }
    }

    // After the base class writes a full CSV row (and ends the line), append Fusion values
    // by seeking back before the newline and writing the extra columns.
    protected override void WriteBucketRow()
    {
        // Let base write its columns and end the line
        base.WriteBucketRow();

        // Retry acquisition if the runner/stats manager was not ready in Start.
        if (_statsManager == null)
        {
            var runner = NetworkLauncher.Instance?.Runner;
            if (runner != null)
            {
                runner.TryGetFusionStatistics(out _statsManager);
            }
        }

        if (_textWriter is System.IO.StreamWriter sw)
        {
            try
            {
                sw.Flush();
                var fs = sw.BaseStream;
                var newlineBytes = sw.Encoding.GetBytes(System.Environment.NewLine).Length;
                if (fs.Length >= newlineBytes)
                {
                    fs.Seek(-newlineBytes, System.IO.SeekOrigin.End);

                    // Collect Fusion stats (safe-null checks)
                    float rttMs = 0f;
                    long inBytes = 0;
                    long outBytes = 0;
                    long inPackets = 0;
                    long outPackets = 0;
                    long inputInBytes = 0;
                    long inputOutBytes = 0;
                    long objectInBytes = 0;
                    long objectOutBytes = 0;

                    if (_statsManager != null && _statsManager.SimulationSnapshot != null)
                    {
                        var s = _statsManager.SimulationSnapshot.Stats;
                        rttMs = GetStatOrZero(s, FusionStatType.RoundTripTime) * 1000f;
                        inBytes = (long)GetStatOrZero(s, FusionStatType.InBandwidth);
                        outBytes = (long)GetStatOrZero(s, FusionStatType.OutBandwidth);
                        inPackets = (long)GetStatOrZero(s, FusionStatType.InPackets);
                        outPackets = (long)GetStatOrZero(s, FusionStatType.OutPackets);
                        inputInBytes = (long)GetStatOrZero(s, FusionStatType.InputInBandwidth);
                        inputOutBytes = (long)GetStatOrZero(s, FusionStatType.InputOutBandwidth);

                        if (_statsManager.ObjectSnapshot != null && _statsManager.ObjectSnapshot.NetworkObjectStatistics != null)
                        {
                            foreach (var objectStats in _statsManager.ObjectSnapshot.NetworkObjectStatistics.Values)
                            {
                                if (objectStats == null)
                                {
                                    continue;
                                }

                                if (objectStats.TryGetValue(FusionObjectStatType.InBandwidth, out var objectIn))
                                {
                                    objectInBytes += (long)objectIn;
                                }

                                if (objectStats.TryGetValue(FusionObjectStatType.OutBandwidth, out var objectOut))
                                {
                                    objectOutBytes += (long)objectOut;
                                }
                            }
                        }
                    }

                    sw.Write(",");
                    sw.Write(rttMs.ToString("F1", CultureInfo.InvariantCulture));
                    sw.Write(",");
                    sw.Write(inBytes);
                    sw.Write(",");
                    sw.Write(outBytes);
                    sw.Write(",");
                    sw.Write(inPackets);
                    sw.Write(",");
                    sw.Write(outPackets);
                    sw.Write(",");
                    sw.Write(inputInBytes);
                    sw.Write(",");
                    sw.Write(inputOutBytes);
                    sw.Write(",");
                    sw.Write(objectInBytes);
                    sw.Write(",");
                    sw.Write(objectOutBytes);
                    sw.WriteLine();
                    sw.Flush();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"Could not append Fusion stats to CSV row: {e.Message}");
            }
        }
    }

    private static float GetStatOrZero(Dictionary<FusionStatType, float> stats, FusionStatType statType)
    {
        return stats != null && stats.TryGetValue(statType, out var value) ? value : 0f;
    }
}