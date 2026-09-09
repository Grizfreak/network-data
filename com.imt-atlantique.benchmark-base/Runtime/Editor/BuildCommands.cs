using System.Linq;
using UnityEditor;

/// <summary>Editor menu commands to build the benchmark player for PC and Android with profiler support enabled.</summary>
public class BuildCommands
{
    /// <summary>Paths of all enabled scenes in the build settings.</summary>
    public static string[] Scenes =>
        EditorBuildSettings.scenes
            .Where(s => s.enabled)
            .Select(s => s.path)
            .ToArray();

    static void PerformBuildPC()
    {
        EditorUserBuildSettings.SwitchActiveBuildTarget(
            BuildTargetGroup.Standalone,
            BuildTarget.StandaloneWindows64
        );
        BuildPlayerOptions buildPlayerOptions = new BuildPlayerOptions();
        buildPlayerOptions.target = BuildTarget.StandaloneWindows64;
        BuildOptions buildOptions = new BuildOptions();
        buildOptions |= BuildOptions.Development;
        buildOptions |= BuildOptions.ConnectWithProfiler;
        buildPlayerOptions.options = buildOptions;
        buildPlayerOptions.scenes = Scenes;
        buildPlayerOptions.locationPathName = "Build/pc/benchmark.exe";
        BuildPipeline.BuildPlayer(buildPlayerOptions);
    }

    static void PerformBuildAndroid()
    {
        EditorUserBuildSettings.SwitchActiveBuildTarget(
            BuildTargetGroup.Android,
            BuildTarget.Android
        );
        BuildPlayerOptions buildPlayerOptions = new BuildPlayerOptions();
        buildPlayerOptions.target = BuildTarget.Android;
        BuildOptions buildOptions = new BuildOptions();
        buildOptions |= BuildOptions.Development;
        buildOptions |= BuildOptions.ConnectWithProfiler;
        buildPlayerOptions.options = buildOptions;
        buildPlayerOptions.scenes = Scenes;
        buildPlayerOptions.locationPathName = "Build/android/benchmark.apk";
        BuildPipeline.BuildPlayer(buildPlayerOptions);
    }
}
