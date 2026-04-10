using UnityEngine;
using System.IO;

public class BaseLoader : MonoBehaviour
{
    [Header("Settings Asset")]
    [SerializeField] private BaseResource originalResource;

    [SerializeField] private ProfilerStats originalStats;

    public BaseResource Resource { get; private set; }
    public ProfilerStats ResourceStats { get; private set; }

    public static BaseLoader Instance;

    // 🔹 Internal helper to read "type" from JSON
    [System.Serializable]
    private class ResourceTypeProbe
    {
        public string type;
    }

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        else
        {
            Destroy(gameObject);
            return;
        }

        if (originalResource == null)
        {
            Debug.LogError("Original Resource is missing from BaseLoader!");
        }

        if (originalStats != null)
        {
            ResourceStats = Instantiate(originalStats);
        }
        else
        {
            Debug.LogError("Profiler Resource is missing from BaseLoader!");
        }
    }

    private void Start()
    {
#if PLATFORM_ANDROID
        string basePath = Application.persistentDataPath + "/conf_resources";

        if (!Directory.Exists(basePath))
        {
            Directory.CreateDirectory(basePath);
        }

        string resourcePath = basePath + "/Base.json";
        if (File.Exists(resourcePath))
        {
            string json = File.ReadAllText(resourcePath);
            Resource = CreateResourceFromJson(json);
        }
        else
        {
            Debug.LogWarning("No Base.json found. Using default resource.");
            Resource = Instantiate(originalResource);
        }

        string profilerPath = basePath + "/ProfilerStats.json";
        if (File.Exists(profilerPath))
        {
            string json = File.ReadAllText(profilerPath);
            ResourceStats.ParseConfiguration(json);
        }
        else
        {
            Debug.LogWarning("No profiler stats found. Using default profiler.");
        }

#elif UNITY_STANDALONE
        string[] args = System.Environment.GetCommandLineArgs();

        string resourceJson = null;
        string profilerJson = null;

        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--conf-file" && i + 1 < args.Length)
            {
                string path = args[i + 1];
                if (File.Exists(path))
                {
                    resourceJson = File.ReadAllText(path);
                }
            }

            if (args[i] == "--conf-profiler" && i + 1 < args.Length)
            {
                string path = args[i + 1];
                if (File.Exists(path))
                {
                    profilerJson = File.ReadAllText(path);
                }
            }
        }

        // ✅ Resource loading
        if (!string.IsNullOrEmpty(resourceJson))
        {
            Resource = CreateResourceFromJson(resourceJson);
        }
        else
        {
            Debug.LogWarning("No resource config provided. Using default.");
            Resource = Instantiate(originalResource);
        }

        // ✅ Profiler loading
        if (!string.IsNullOrEmpty(profilerJson))
        {
            ResourceStats.ParseConfiguration(profilerJson);
        }
#endif
    }

    // 🔥 Core: type-agnostic factory
    private BaseResource CreateResourceFromJson(string json)
    {
        if (originalResource == null)
        {
            Debug.LogError("Cannot create resource: originalResource is null.");
            return null;
        }

        // 1. Extract type
        var probe = JsonUtility.FromJson<ResourceTypeProbe>(json);

        // 2. Create correct instance via registry
        BaseResource resource = ResourceTypeRegistry.Create(probe?.type);

        // 3. Copy default values from original asset
        JsonUtility.FromJsonOverwrite(JsonUtility.ToJson(originalResource), resource);

        // 4. Apply JSON overrides
        JsonUtility.FromJsonOverwrite(json, resource);

        return resource;
    }
}