using System;
using System.Globalization;
using System.IO;
using UnityEngine;

    /// <summary>
    /// This component will log events related to the Phase System, by telling which frame happened which event
    /// This component is thought to be extensive, because it uses one method named <c>Log Event</c>
    /// </summary>
    public class LogsManager : MonoBehaviour
    {
        
#if PLATFORM_STANDALONE
        public string eventsFileName = "events_";
#elif UNITY_ANDROID
        public string eventsFileName = "quest_events_";
#endif
        private string fileName;
        private string filePath;
        private string eventsFilePath;
        
        private StreamWriter eventsWriter;

        private void OnEnable()
        {
            InstantiateManager.Instance.StartingInstantiation += LogEvent;
            InstantiateManager.Instance.FinishedInstantiation += LogEvent;
            PhaseManager.Instance.PhaseStarted += LogEvent;
            PhaseManager.Instance.PhaseFinished += LogEvent;
            MoveManager.Instance.StartMovingEntities += LogEvent;
            MoveManager.Instance.EndMovingEntities += LogEvent;
        }

        private void LogEvent(string eventName)
        {
            WriteEvent(Time.frameCount, eventName);
        }

        private void LogEvent(string eventName, int numberOfInstances)
        {
            WriteEvent(Time.frameCount, eventName, numberOfInstances);
        }

        private void Start()
        {
            string eventsFileFullName = eventsFileName + $"{DateTime.Now:yyyyMMdd_HHmmss}.csv";
            eventsFilePath = Path.Combine(Application.persistentDataPath, eventsFileFullName);

            eventsWriter = new StreamWriter(eventsFilePath, false);

            // Optional but recommended: enable buffering
            eventsWriter.AutoFlush = false;

            // Write headers once
            eventsWriter.WriteLine("Frame,Time,Event,Value");
        }

        private void WriteEvent(int frame, string eventName, int number = -1)
        {
            // Use realtimeSinceStartup to match the external OVR clock
            float timestamp = Time.realtimeSinceStartup;
            if (eventsWriter == null)
            {
                Debug.LogWarning("Events writer is not initialized. Event will not be logged: " + eventName);
                return;
            }
            eventsWriter.WriteLine(string.Format(CultureInfo.InvariantCulture,
                "{0},{1:F3},{2},{3}",
                frame, timestamp, eventName, number == -1 ? -1 : number));
        }

        private void OnApplicationQuit()
        {
            eventsWriter?.Flush();
            eventsWriter?.Close();
        }
    }