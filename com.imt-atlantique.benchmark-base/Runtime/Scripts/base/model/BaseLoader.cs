using UnityEngine;

/// <summary>
/// This class is responsible for loading the configuration from a .json file and storing it in a ScriptableObject.
/// It uses the Singleton pattern to ensure that there is only one instance of the loader in the scene, and that it can be accessed from anywhere.
/// The loader will create a clone of the original ScriptableObject, which is stored as an asset in the project, and then parse the configuration from the .json file into the clone.
/// This way, the original asset remains unchanged and can be reused across multiple runs of the benchmark with different configurations.
/// </summary>
public class BaseLoader : MonoBehaviour
{
    [Header("Settings Asset")]
    [SerializeField] private BaseResource originalResource;

    [SerializeField] private ProfilerStats originalStats;
    
    // This is the version the rest of your game will actually use
    public BaseResource Resource { get; private set; }
    public ProfilerStats ResourceStats { get; private set; }
    
    public static BaseLoader Instance;

    private void Awake()
    {
        // 1. Singleton Setup
        if (Instance == null)
        {
            Instance = this;
            // Keep the loader alive across scene loads if necessary
            DontDestroyOnLoad(gameObject); 
        }
        else
        {
            Destroy(gameObject);
            return;
        }

        // 2. CREATE THE SAFE CLONE
        // This copies the values from originalResource into a new instance in memory
        if (originalResource != null)
        {
            Resource = Instantiate(originalResource);
        }
        else
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
        // Create a folder named conf_resources in the PersistentDataPath
        if (!System.IO.Directory.Exists(Application.persistentDataPath + "/conf_resources"))
        {
            System.IO.Directory.CreateDirectory(Application.persistentDataPath + "/conf_resources");
        }
        // Check if conf_resources folder contains a file named Base.json or ProfilerStats.json
        TextAsset configFile = System.IO.File.Exists(Application.persistentDataPath + "/conf_resources/Base.json") ? 
            new TextAsset(System.IO.File.ReadAllText(Application.persistentDataPath + "/conf_resources/Base.json")) : null;
        if (configFile != null)        {
            // 3. PARSE INTO THE CLONE
            // This only affects the RAM version, not the .asset file
            Resource.ParseConfiguration(configFile.text);
        }
        else
        {            
            Debug.LogWarning("No configuration file named Base.json found in Resources folder. Running base test");
        }
        TextAsset profilerStats = System.IO.File.Exists(Application.persistentDataPath + "/conf_resources/ProfilerStats.json") ? 
            new TextAsset(System.IO.File.ReadAllText(Application.persistentDataPath + "/conf_resources/ProfilerStats.json")) : null;
        if (profilerStats != null)
        {
            ResourceStats.ParseConfiguration(profilerStats.text);
        }
        else
        {
            Debug.LogWarning("No profiler stats found in BaseLoader. Running base profiler profile");
        }
        #elif UNITY_STANDALONE
        string[] args = System.Environment.GetCommandLineArgs();
        
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--conf-file" && i + 1 < args.Length)
            {
                string filePath = args[i + 1];
                if (System.IO.File.Exists(filePath))
                {
                    string fileContent = System.IO.File.ReadAllText(filePath);
                    
                    // 3. PARSE INTO THE CLONE
                    // This only affects the RAM version, not the .asset file
                    Resource.ParseConfiguration(fileContent);
                }
            }

            if (args[i] != "--conf-profiler" || i + 1 >= args.Length) continue;
            {
                string filePath = args[i + 1];
                if (!System.IO.File.Exists(filePath)) continue;
                string fileContent = System.IO.File.ReadAllText(filePath);

                ResourceStats.ParseConfiguration(fileContent);
            }
        }
        #endif
    }
}