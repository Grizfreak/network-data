using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// This class is responsible for launching the benchmark by loading the Benchmark scene and starting the first phase when the PhaseManager is found.
/// </summary>
    public class BaseLauncher : MonoBehaviour
    {
        private bool searchingForPhaseManager;
        private PhaseManager phaseManager;
        // Start is called once before the first execution of Update after the MonoBehaviour is created
        private void Start()
        {
            SceneManager.activeSceneChanged += OnSceneChanged;
        }

        private void Update()
        {
            if (searchingForPhaseManager)
            {
                phaseManager = FindAnyObjectByType<PhaseManager>();
                if (phaseManager != null)
                {
                    searchingForPhaseManager = false;
                    phaseManager.AskPhase1Start.Invoke();
                }
            }
        }
    
    
        private void OnSceneChanged(Scene current, Scene next)
        {
            // wait for PhaseManager to exist and then call PhaseManager.instance.AskPhase1Start.Invoke();
            searchingForPhaseManager = true;
        }

        private void OnDisable()
        {
            SceneManager.activeSceneChanged -= OnSceneChanged;
        }
    }
