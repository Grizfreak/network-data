using System;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.Profiling;
using System.Diagnostics;
using Unity.Profiling;

public class LogsManager : MonoBehaviour
{
    private string fileName;
    private string filePath;
    private string eventsFilePath;
    private int m_frameCount;
    private float m_deltaTime;
    
    private StreamWriter dataWriter;
    private StreamWriter eventsWriter;
    private float flushTimer = 0f;
    
    // CPU Profiling
    private ProfilerRecorder mainThreadRecorder;
    private ProfilerRecorder renderThreadRecorder;

    private void OnEnable()
    {
        InstantiateManager.instance.StartingInstantiation += LogEvent;
        InstantiateManager.instance.FinishedInstantiation += LogEvent;
        PhaseManager.instance.PhaseFinished += LogEvent;
        MoveManager.instance.StartMovingEntities += LogEvent;
        MoveManager.instance.EndMovingEntities += LogEvent;
    }

    public void LogEvent(string eventName)
    {
        WriteEvent(Time.frameCount, eventName);
    }
    
    public void LogEvent(string eventName, int numberOfInstances)
    {
        WriteEvent(Time.frameCount, eventName, numberOfInstances);
    }
    
    /*private void OnDisable()
    {
        if (mainThreadRecorder.Valid) mainThreadRecorder.Dispose();
        if (renderThreadRecorder.Valid) renderThreadRecorder.Dispose();
    }*/
    
    private void Start()
    {
        /*mainThreadRecorder = ProfilerRecorder.StartNew(
            ProfilerCategory.Internal,
            "Main Thread",
            15 // keep a small buffer
        );

        renderThreadRecorder = ProfilerRecorder.StartNew(
            ProfilerCategory.Internal,
            "Render Thread",
            15
        );*/
        
        string eventsFileName = $"events_{DateTime.Now:yyyyMMdd_HHmmss}.csv";
        eventsFilePath = Path.Combine(Application.persistentDataPath, eventsFileName);
        
        eventsWriter = new StreamWriter(eventsFilePath, false);

        // Optional but recommended: enable buffering
        eventsWriter.AutoFlush = false;

        // Write headers once
        eventsWriter.WriteLine("Frame,Event,Value");
    }

    /*private void LateUpdate()
    {
        m_deltaTime += Time.unscaledDeltaTime;
        m_frameCount++;

        // Log metrics every second
        if (m_deltaTime >= 1f)
        {
            float fps = m_frameCount / m_deltaTime;
            float mainThreadMs = GetRecorderMs(mainThreadRecorder);
            float renderThreadMs = GetRecorderMs(renderThreadRecorder);
            float ramUsage = GetRAMUsageMB();

            // Write all metrics in a single line
            WriteData(Time.time, fps, mainThreadMs, renderThreadMs, ramUsage);

            m_deltaTime = 0f;
            m_frameCount = 0;
        }
        
        flushTimer += Time.unscaledDeltaTime;

        if (flushTimer >= 2f) // flush every 2 seconds (tweak if needed)
        {
            dataWriter.Flush();
            eventsWriter.Flush();
            flushTimer = 0f;
        }
    }*/
    
    /*private float GetRecorderMs(ProfilerRecorder recorder)
    {
        if (!recorder.Valid)
            return -1f;

        if (recorder.Count == 0)
            return 0f;

        return recorder.LastValue / 1_000_000f; // ns → ms
    }

    private void WriteData(float time, float fps, float mainThread, float renderThread, float ramUsage)
    {
        dataWriter.WriteLine(string.Format(CultureInfo.InvariantCulture,
            "{0:F2},{1:F2},{2:F2},{3:F2},{4:F2}",
            time, fps, mainThread, renderThread, ramUsage));
    }*/
    
    private void WriteEvent(int time, string eventName, int number = -1)
    {
        eventsWriter.WriteLine(string.Format(CultureInfo.InvariantCulture,
            "{0},{1},{2}",
            time, eventName, number == -1 ? -1 : number));
    }

    // Placeholder methods for CPU/GPU usage — implement according to platform
    
    /*private float GetRAMUsageMB()
    {
        return Profiler.GetTotalAllocatedMemoryLong() / (1024f * 1024f);
    }*/
    
    private void OnApplicationQuit()
    {
        dataWriter?.Flush();
        dataWriter?.Close();

        eventsWriter?.Flush();
        eventsWriter?.Close();
    }
}