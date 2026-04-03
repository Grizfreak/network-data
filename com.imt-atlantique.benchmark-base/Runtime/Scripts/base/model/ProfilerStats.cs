using @base.model;
using UnityEngine;

[CreateAssetMenu(fileName = "ProfilerStats", menuName = "Scriptable Objects/ProfilerStats")]
public class ProfilerStats : ScriptableObject
    {
        public ProfilerStatsEntry[] Entries;

        public ProfilerStats(ProfilerStatsEntry[] entries)
        {
            Entries = entries;
        }
        
        public void ParseConfiguration(string fileContent)
        {
            // JsonUtility.FromJsonOverwrite takes the JSON string and 
            // injects the values directly into this ScriptableObject instance.
            JsonUtility.FromJsonOverwrite(fileContent, this);
        }
    }
