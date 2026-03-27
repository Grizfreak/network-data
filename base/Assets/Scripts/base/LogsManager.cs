using System;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.Profiling;
using System.Diagnostics;

public class LogsManager : MonoBehaviour
{
    private string fileName;
    private string filePath;
    private int m_frameCount;
    private float m_deltaTime;
    
    // CPU Profiling
    private Process process;
    private TimeSpan lastTotalProcessorTime;
    private float lastCpuCheckTime;

    private void Start()
    {
        process = Process.GetCurrentProcess();
        lastTotalProcessorTime = process.TotalProcessorTime;
        lastCpuCheckTime = Time.realtimeSinceStartup;
        
        fileName = $"perf_{DateTime.Now:yyyyMMdd_HHmmss}.csv";
        filePath = Path.Combine(Application.persistentDataPath, fileName);

        // Write CSV header once with all metrics
        File.WriteAllText(filePath, "Time,FPS,CPU_Usage,RAM_MB\n");
    }

    private void LateUpdate()
    {
        m_deltaTime += Time.unscaledDeltaTime;
        m_frameCount++;

        // Log metrics every second
        if (m_deltaTime >= 1f)
        {
            float fps = m_frameCount / m_deltaTime;
            float cpuUsage = GetCPUUsage();
            float ramUsage = GetRAMUsageMB();

            // Write all metrics in a single line
            WriteData(Time.time, fps, cpuUsage, ramUsage);

            m_deltaTime = 0f;
            m_frameCount = 0;
        }
    }

    private void WriteData(float time, float fps, float cpuUsage, float ramUsage)
    {
        using (StreamWriter sw = new StreamWriter(filePath, true))
        {
            sw.WriteLine(string.Format(CultureInfo.InvariantCulture, "{0:F2},{1:F2},{2:F2},{3:F2}",
                time, fps, cpuUsage, ramUsage));
        }
    }

    // Placeholder methods for CPU/GPU usage — implement according to platform
    private float GetCPUUsage()
    {
        float now = Time.realtimeSinceStartup;
        TimeSpan newTotalProcessorTime = process.TotalProcessorTime;

        float cpuUsage = (float)((newTotalProcessorTime - lastTotalProcessorTime).TotalMilliseconds /
                                 ((now - lastCpuCheckTime) * 1000 * Environment.ProcessorCount)) * 100f;

        lastTotalProcessorTime = newTotalProcessorTime;
        lastCpuCheckTime = now;

        return cpuUsage;
    }
    
    private float GetRAMUsageMB()
    {
        return process.WorkingSet64 / (1024f * 1024f);
    }
}