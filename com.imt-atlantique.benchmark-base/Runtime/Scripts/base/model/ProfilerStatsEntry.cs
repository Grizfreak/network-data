using System;
using Unity.Profiling;
using UnityEngine.Serialization;

namespace @base.model
{
    /// <summary>Identifies one Unity Profiler stat (category + name) and can create a ProfilerRecorder for it.</summary>
    [Serializable]
    public sealed class ProfilerStatsEntry
    {
        [FormerlySerializedAs("Category")] public string category;
        [FormerlySerializedAs("Name")] public string name;

        public ProfilerStatsEntry(string category, string name)
        {
            this.category = category;
            this.name = name;
        }

        /// <summary>Creates and starts a ProfilerRecorder for this entry's category/name.</summary>
        public ProfilerRecorder ToProfilerRecorder()
        {
            ProfilerCategory profilerCategory = new ProfilerCategory(category);
            return ProfilerRecorder.StartNew(profilerCategory, name);
        }
    }
}