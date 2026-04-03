using System;
using Unity.Profiling;
using UnityEngine.Serialization;

namespace @base.model
{
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
			
        public ProfilerRecorder ToProfilerRecorder()
        {
            ProfilerCategory profilerCategory = new ProfilerCategory(category);
            return ProfilerRecorder.StartNew(profilerCategory, name);
        }
    }
}