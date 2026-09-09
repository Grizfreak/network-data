using @base.model;
using UnityEngine;

/// <summary>ScriptableObject listing the set of ProfilerStatsEntry to record during a benchmark run.</summary>
[CreateAssetMenu(fileName = "ProfilerStats", menuName = "Scriptable Objects/ProfilerStats")]
public class ProfilerStats : ScriptableObject
    {
        public ProfilerStatsEntry[] Entries;

        public ProfilerStats(ProfilerStatsEntry[] entries)
        {
            Entries = entries;
        }
        
        /// <summary>Overwrites Entries with values parsed from a JSON config string.</summary>
        public void ParseConfiguration(string fileContent)
        {
            // JsonUtility.FromJsonOverwrite takes the JSON string and
            // injects the values directly into this ScriptableObject instance.
            JsonUtility.FromJsonOverwrite(fileContent, this);
        }
    }
