using UnityEngine;

public class BaseLoader : MonoBehaviour
{
    [Header("Settings Asset")]
    [SerializeField] private BaseResource originalResource;
    
    // This is the version the rest of your game will actually use
    public BaseResource resource { get; private set; }
    
    public static BaseLoader instance;

    void Awake()
    {
        // 1. Singleton Setup
        if (instance == null)
        {
            instance = this;
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
            resource = Instantiate(originalResource);
        }
        else
        {
            Debug.LogError("Original Resource is missing from BaseLoader!");
        }
    }

    void Start()
    {
        string[] args = System.Environment.GetCommandLineArgs();
        
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "-conf_file" && i + 1 < args.Length)
            {
                string filePath = args[i + 1];
                if (System.IO.File.Exists(filePath))
                {
                    string fileContent = System.IO.File.ReadAllText(filePath);
                    
                    // 3. PARSE INTO THE CLONE
                    // This only affects the RAM version, not the .asset file
                    resource.ParseConfiguration(fileContent);
                }
            }
        }
    }
}