using System;
using System.Globalization;
using System.IO;
using @base.model;
using Unity.Profiling;
using UnityEngine;

/// <summary>
/// This component will export the specified Profiler stats to a CSV file in the application persistent data path.
/// Data is written in time-based buckets (default: every 0.5s) so that the X axis reflects real elapsed time,
/// making graphs readable regardless of FPS fluctuations.
/// cf. https://docs.unity3d.com/ScriptReference/Unity.Profiling.ProfilerRecorder.html
/// </summary>
public class ProfilerStatsToCsvExporter : MonoBehaviour
{
    public string outputName = $"profiler_stats";

    [SerializeField]
    [Tooltip("Duration of each time bucket in seconds. One CSV row is written per bucket.")]
    private float bucketDuration = 0.5f;

    [SerializeField]
    [Tooltip("Input values found via ProfilerRecorderHandle.GetAvailable")]
    private ProfilerStats profilerStatsFile;

    [Header("Optional provider for network benchmarks (RTT, bytes sent/received)")]
    [SerializeField]
    private bool includeNetworkStats = false;
    [SerializeField]
    private MonoBehaviour networkBenchmarkProviderBehaviour;

    private INetworkBenchmarkProvider _networkBenchmarkProvider;

    // --- Network bucket state ---
    private float _bucketRttSum;
    private int _bucketRttSamples;

    private long _lastBytesSent;
    private long _lastBytesReceived;

    private long _bucketBytesSentDelta;
    private long _bucketBytesReceivedDelta;

    private bool _networkBaselineInitialized;


    private const char OutputSeparator = ',';

    private ProfilerStatsEntry[] profilerStats = {
        new ("GC", "GC.Collect"),
        new ("Internal", "Main Thread"),
        new ("Memory", "Total Used Memory"),
        new ("Memory", "Audio Used Memory"),
        new ("Memory", "GC Used Memory"),
        new ("PlayerLoop", "PlayerLoop"),
        new ("Render", "Batches Count"),
        new ("Render", "CPU Main Thread Frame Time"),
        new ("Render", "CPU Render Thread Frame Time"),
        new ("Render", "CPU Total Frame Time"),
        new ("Render", "Draw Calls Count"),
        new ("Render", "FrameTime.GPU"),
        new ("Render", "GPU Frame Time"),
        new ("Render", "Gfx.WaitForPresentOnGfxThread"),
        new ("Render", "Render Textures Bytes"),
        new ("Render", "Render Textures Count"),
        new ("Render", "SetPass Calls Count"),
        new ("Render", "Shadow Casters Count"),
        new ("Render", "Triangles Count"),
        new ("Render", "Vertices Count"),
        new ("VSync", "WaitForTargetFPS")
    };

    protected TextWriter _textWriter;
    private ProfilerRecorder[] _profilerRecorders;
    private float _lastFlushTime;

    // --- Time bucket state ---
    private float _bucketAccumulator;
    private float _bucketFpsSum;
    private float _bucketFrameTimeSum;
    private int _bucketFrameCount;
    private long[] _bucketProfilerSums;   // sum of profiler values within the bucket
    private int _bucketProfilerSamples;   // number of samples accumulated
    private int _lastFrameNumber;         // frame number of the last frame in the bucket

    protected virtual void Start()
    {
        _networkBenchmarkProvider =
            networkBenchmarkProviderBehaviour as INetworkBenchmarkProvider;

        if (networkBenchmarkProviderBehaviour != null &&
            _networkBenchmarkProvider == null)
        {
            Debug.LogError(
                $"{networkBenchmarkProviderBehaviour.name} does not implement INetworkBenchmarkProvider");
        }

        // Apply new profiler data from file
        if (profilerStatsFile != null)
        {
            profilerStats = profilerStatsFile.Entries;
        }

        // If data is passed from BaseLoader, get them
        if (BaseLoader.Instance != null && BaseLoader.Instance.ResourceStats != null)
        {
            profilerStats = BaseLoader.Instance.ResourceStats.Entries;
        }

        var outputFile = outputName + $"-{DateTime.Now:yyyy.MM.dd-HH.mm}.csv";
        var outputFilePath = Path.Combine(Application.persistentDataPath, outputFile);
        _textWriter = new StreamWriter(outputFilePath, true);
        Debug.Log("Writing Profiler Stats to " + outputFilePath);

        // --- Header ---
        _textWriter.Write("Time (s)");           // Real elapsed time — use as X axis
        _textWriter.Write(OutputSeparator);
        _textWriter.Write("Frame");              // Last frame number in the bucket
        _textWriter.Write(OutputSeparator);
        _textWriter.Write("FPS");                // Average FPS over the bucket
        _textWriter.Write(OutputSeparator);
        _textWriter.Write("FrameTimeMs");        // Average frame time over the bucket
        _textWriter.Write(OutputSeparator);
        _textWriter.Write("RTT (ms)");
        _textWriter.Write(OutputSeparator);

        _textWriter.Write("Upload (bytes/sec)");
        _textWriter.Write(OutputSeparator);

        _textWriter.Write("Download (bytes/sec)");
        _textWriter.Write(OutputSeparator);

        _profilerRecorders = new ProfilerRecorder[profilerStats.Length];
        _bucketProfilerSums = new long[profilerStats.Length];

        for (int i = 0; i < profilerStats.Length; i++)
        {
            _profilerRecorders[i] = profilerStats[i].ToProfilerRecorder();

            if (_profilerRecorders[i].Valid == false)
            {
                Debug.LogError(
                    $"ProfilerRecorder for {profilerStats[i].name} ({profilerStats[i].category}) is not valid. " +
                    $"Either there's a typo or this ProfilerRecorder is not available on this platform.");
                continue;
            }

            _textWriter.Write(profilerStats[i].name);
            AppendStatUnitToText(_profilerRecorders[i], _textWriter);

            bool isLastColumn = i == profilerStats.Length - 1;
            AppendSeparatorToText(_textWriter, isLastColumn);
        }

        // Initialise bucket state
        ResetBucket();
    }

    protected virtual void OnDisable()
    {
        // Flush any partial bucket so no data is lost on exit
        if (_bucketFrameCount > 0)
        {
            WriteBucketRow();
        }
        if (_textWriter != null)
        {
            _textWriter.Flush();
            _textWriter.Dispose();
        }
        if (_profilerRecorders != null)
        {
            foreach (ProfilerRecorder profilerRecorder in _profilerRecorders)
            {
                profilerRecorder.Dispose();
            }
        }
        Debug.Log("Disabling ProfilerStatsToCsvExporter and disposed recorders.");
    }

    protected virtual void Update()
    {
        float dt = Time.unscaledDeltaTime;

        // Accumulate into current bucket
        _bucketAccumulator   += dt;
        _bucketFpsSum        += (dt > 0f ? 1f / dt : 0f);
        _bucketFrameTimeSum  += dt * 1000f;   // convert to ms
        _bucketFrameCount++;
        _lastFrameNumber = Time.frameCount;

        for (int i = 0; i < _profilerRecorders.Length; i++)
        {
            _bucketProfilerSums[i] += _profilerRecorders[i].LastValue;
        }
        _bucketProfilerSamples++;

        //Network system
        if (includeNetworkStats && _networkBenchmarkProvider != null)
        {
            _bucketRttSum += _networkBenchmarkProvider.GetRttMs();
            _bucketRttSamples++;

            long currentSent = _networkBenchmarkProvider.GetBytesSent();
            long currentReceived = _networkBenchmarkProvider.GetBytesReceived();

            if (!_networkBaselineInitialized)
            {
                _lastBytesSent = currentSent;
                _lastBytesReceived = currentReceived;
                _networkBaselineInitialized = true;
            }
            else
            {
                _bucketBytesSentDelta += currentSent - _lastBytesSent;
                _bucketBytesReceivedDelta += currentReceived - _lastBytesReceived;

                _lastBytesSent = currentSent;
                _lastBytesReceived = currentReceived;
            }
        }

        // When bucket is full, write one row and reset
        if (_bucketAccumulator >= bucketDuration)
        {
            WriteBucketRow();
            ResetBucket();
        }

        // Periodic flush to disk (every second)
        if (_lastFlushTime + 1f < Time.realtimeSinceStartup)
        {
            _lastFlushTime = Time.realtimeSinceStartup;
            _textWriter.Flush();
        }
    }

    /// <summary>
    /// Writes one averaged row to the CSV representing the completed time bucket.
    /// </summary>
    protected virtual void WriteBucketRow()
    {
        float avgFps       = _bucketFrameCount > 0 ? _bucketFpsSum      / _bucketFrameCount : 0f;
        float avgFrameTime = _bucketFrameCount > 0 ? _bucketFrameTimeSum / _bucketFrameCount : 0f;

        // Timestamp = end of the bucket (real elapsed time since startup)
        _textWriter.Write(Time.realtimeSinceStartup.ToString("F3", CultureInfo.InvariantCulture));
        _textWriter.Write(OutputSeparator);

        _textWriter.Write(GetLongAsChars(_lastFrameNumber));
        _textWriter.Write(OutputSeparator);

        _textWriter.Write(avgFps.ToString("F2", CultureInfo.InvariantCulture));
        _textWriter.Write(OutputSeparator);

        _textWriter.Write(avgFrameTime.ToString("F3", CultureInfo.InvariantCulture));
        _textWriter.Write(OutputSeparator);
        if (includeNetworkStats)
        {
            float avgRtt = _bucketRttSamples > 0
                ? _bucketRttSum / _bucketRttSamples
                : 0f;

            float uploadRate = _bucketAccumulator > 0f
                ? _bucketBytesSentDelta / _bucketAccumulator
                : 0f;

            float downloadRate = _bucketAccumulator > 0f
                ? _bucketBytesReceivedDelta / _bucketAccumulator
                : 0f;

            _textWriter.Write(avgRtt.ToString("F2", CultureInfo.InvariantCulture));
            _textWriter.Write(OutputSeparator);

            _textWriter.Write(uploadRate.ToString("F0", CultureInfo.InvariantCulture));
            _textWriter.Write(OutputSeparator);

            _textWriter.Write(downloadRate.ToString("F0", CultureInfo.InvariantCulture));
            _textWriter.Write(OutputSeparator);
        }
        int samples = _bucketProfilerSamples > 0 ? _bucketProfilerSamples : 1;
        for (int i = 0; i < _profilerRecorders.Length; i++)
        {
            long avgValue = _bucketProfilerSums[i] / samples;
            _textWriter.Write(GetLongAsChars(avgValue));

            bool isLastColumn = i == _profilerRecorders.Length - 1;
            AppendSeparatorToText(_textWriter, isLastColumn);
        }
    }

    /// <summary>
    /// Resets all bucket accumulators to start a new time window.
    /// </summary>
    protected virtual void ResetBucket()
    {
        _bucketAccumulator  = 0f;
        _bucketFpsSum       = 0f;
        _bucketFrameTimeSum = 0f;
        _bucketFrameCount   = 0;
        _bucketProfilerSamples = 0;

        if (includeNetworkStats)
        {
            _bucketRttSum = 0f;
            _bucketRttSamples = 0;
            _bucketBytesSentDelta = 0;
            _bucketBytesReceivedDelta = 0;
        }

        for (int i = 0; i < _bucketProfilerSums.Length; i++)
        {
            _bucketProfilerSums[i] = 0;
        }
    }

    // -------------------------------------------------------------------------
    // Helpers (unchanged from original)
    // -------------------------------------------------------------------------

    private static void AppendSeparatorToText(TextWriter textWriter, bool isLastColumn = false)
    {
        if (isLastColumn)
        {
            textWriter.WriteLine();
        }
        else
        {
            textWriter.Write(OutputSeparator);
        }
    }

    private static void AppendStatUnitToText(ProfilerRecorder profilerRecorder, TextWriter textWriter)
    {
        switch (profilerRecorder.UnitType)
        {
            case ProfilerMarkerDataUnit.TimeNanoseconds:
                textWriter.Write(" (ns)");
                break;
            case ProfilerMarkerDataUnit.Bytes:
                textWriter.Write(" (bytes)");
                break;
            case ProfilerMarkerDataUnit.Percent:
                textWriter.Write(" (%)");
                break;
            case ProfilerMarkerDataUnit.FrequencyHz:
                textWriter.Write(" (Hz)");
                break;
            case ProfilerMarkerDataUnit.Undefined:
            case ProfilerMarkerDataUnit.Count:
            default:
                break;
        }
    }

    private static readonly char[] LongAsCharsBuffer = new char[20]; // 19 digits + sign

    private static ReadOnlySpan<char> GetLongAsChars(long value)
    {
        int bufferIndex = 0;

        if (value == 0)
        {
            LongAsCharsBuffer[bufferIndex] = '0';
            return new Span<char>(LongAsCharsBuffer, bufferIndex, 1);
        }

        if (value < 0)
        {
            LongAsCharsBuffer[bufferIndex] = '-';
            bufferIndex++;
            value = -value;
        }

        int length = 1;
        for (long r = value / 10; r > 0; r /= 10)
        {
            length++;
        }

        for (int i = length - 1; i >= 0; i--)
        {
            LongAsCharsBuffer[bufferIndex + i] = (char)('0' + (value % 10));
            value /= 10;
        }

        return new ReadOnlySpan<char>(LongAsCharsBuffer).Slice(bufferIndex, length);
    }

}