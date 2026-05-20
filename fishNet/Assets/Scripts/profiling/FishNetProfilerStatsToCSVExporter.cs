using System;
using System.Globalization;
using System.IO;
using FishNet;
using FishNet.Managing;
using FishNet.Managing.Timing;
using FishNet.Transporting;
using UnityEngine;

/// <summary>
/// Extends ProfilerStatsToCsvExporter with FishNet networking metrics.
/// Uses the same CSV append strategy as PhotonProfilerStatsToCsvExporter.
/// </summary>
public class FishNetProfilerStatsToCsvExporter : ProfilerStatsToCsvExporter
{
#if UNITY_STANDALONE

    // ------------------------------------------------------------------------
    // FISHNET
    // ------------------------------------------------------------------------

    private NetworkManager _networkManager;
    private Transport _transport;

    private ulong _inBytes;
    private ulong _outBytes;

    private float _rttSum;
    private int _rttCount;

    // ------------------------------------------------------------------------
    // UNITY
    // ------------------------------------------------------------------------

    protected override void Start()
    {
        base.Start();

        // --------------------------------------------------------------------
        // APPEND EXTRA HEADERS
        // --------------------------------------------------------------------

        if (_textWriter is StreamWriter sw)
        {
            try
            {
                sw.Flush();

                var fs = sw.BaseStream;

                int newlineBytes =
                    sw.Encoding
                        .GetBytes(Environment.NewLine)
                        .Length;

                if (fs.Length >= newlineBytes)
                {
                    fs.Seek(
                        -newlineBytes,
                        SeekOrigin.End
                    );

                    sw.Write(
                        ",NetInBytesPerSec" +
                        ",NetOutBytesPerSec" +
                        ",RTT_ms"
                    );

                    sw.WriteLine();
                    sw.Flush();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning(
                    $"Could not append FishNet headers: {e.Message}"
                );
            }
        }

        // --------------------------------------------------------------------
        // SETUP NETWORK MANAGER
        // --------------------------------------------------------------------

        _networkManager =
            InstanceFinder.NetworkManager;

        if (_networkManager != null)
        {
            _transport =
                _networkManager.TransportManager.Transport;

            if (_transport != null)
            {
                _transport.OnClientReceivedData +=
                    OnClientReceive;

                _transport.OnServerReceivedData +=
                    OnServerSend;
            }
        }
    }

    protected override void Update()
    {
        base.Update();

        if (_networkManager != null)
        {
            TimeManager tm =
                _networkManager.TimeManager;

            if (tm != null)
            {
                _rttSum += tm.RoundTripTime;
                _rttCount++;
            }
        }
    }

    protected override void OnDisable()
    {
        if (_transport != null)
        {
            _transport.OnClientReceivedData -=
                OnClientReceive;

            _transport.OnServerReceivedData -=
                OnServerSend;
        }

        base.OnDisable();
    }

    // ------------------------------------------------------------------------
    // CSV ROW APPEND
    // ------------------------------------------------------------------------

    protected override void WriteBucketRow()
    {
        // Let base write normal profiler row first
        base.WriteBucketRow();

        float avgRtt =
            _rttCount > 0
                ? _rttSum / _rttCount
                : 0f;

        float inRate =
            (float)_inBytes / 0.5f;

        float outRate =
            (float)_outBytes / 0.5f;

        // --------------------------------------------------------------------
        // APPEND EXTRA VALUES TO EXISTING LINE
        // --------------------------------------------------------------------

        if (_textWriter is StreamWriter sw)
        {
            try
            {
                sw.Flush();

                var fs = sw.BaseStream;

                int newlineBytes =
                    sw.Encoding
                        .GetBytes(Environment.NewLine)
                        .Length;

                if (fs.Length >= newlineBytes)
                {
                    fs.Seek(
                        -newlineBytes,
                        SeekOrigin.End
                    );

                    sw.Write(",");

                    sw.Write(
                        inRate.ToString(
                            "F2",
                            CultureInfo.InvariantCulture
                        )
                    );

                    sw.Write(",");

                    sw.Write(
                        outRate.ToString(
                            "F2",
                            CultureInfo.InvariantCulture
                        )
                    );

                    sw.Write(",");

                    sw.Write(
                        avgRtt.ToString(
                            "F1",
                            CultureInfo.InvariantCulture
                        )
                    );

                    sw.WriteLine();
                    sw.Flush();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning(
                    $"Could not append FishNet stats: {e.Message}"
                );
            }
        }

        // Reset networking accumulators after row write
        _inBytes = 0;
        _outBytes = 0;

        _rttSum = 0f;
        _rttCount = 0;
    }

    // ------------------------------------------------------------------------
    // FISHNET EVENTS
    // ------------------------------------------------------------------------

    private void OnClientReceive(
        ClientReceivedDataArgs args)
    {
        _inBytes +=
            (ulong)args.Data.Count;
    }

    private void OnServerSend(
        ServerReceivedDataArgs args)
    {
        _outBytes +=
            (ulong)args.Data.Count;
    }

#endif
}