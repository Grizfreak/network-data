using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>Waits for a PhaseManager to appear after a scene change, then triggers phase 1 automatically.</summary>
    public class BaseLauncher : MonoBehaviour
    {
        private bool searchingForPhaseManager;
        public bool startAutoPhase1 = true;
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
                phaseManager = PhaseManager.Instance;
                if (phaseManager != null)
                {
                    searchingForPhaseManager = false;
                }
            }
            if (phaseManager != null && startAutoPhase1)
            {
                phaseManager.AskPhase1Start.Invoke();
                startAutoPhase1 = false;
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
