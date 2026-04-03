using System;
using System.Collections;
using UnityEngine;

/// <summary>
/// This component will manage the different phases of the benchmark, by invoking events when each phase starts and ends, to allow other components to react to these events. The phases are defined as follows:
/// Phase 1: Players connect to the server and then start instantiation phase
/// Phase 2: Objects instantiate via InstantiateManager per wave defined in the manager
/// Phase 3: Objects instantiated move one by one, everything is defined in MoveManager
/// </summary>
    public class PhaseManager : MonoBehaviour
    {
        public static PhaseManager Instance;
        public bool startPhase1;
        public bool startPhase2;
        public bool startPhase3;
        public bool autoLinkingPhase = true;
        public float waitingPhase1Time = 2f;
        public float waitBetweenPhases = 2f;
        public float waitBeforeQuittingApp = 5f;
        private int _currentPhase;
        public Action<string> PhaseStarted;
        public Action<string> PhaseFinished;
        public Action AskPhase1Start;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        private void Start()
        {
            if (BaseLoader.Instance != null)
            {
                waitingPhase1Time = BaseLoader.Instance.Resource.mWaitingPhase1Time;
                waitBetweenPhases = BaseLoader.Instance.Resource.mWaitBetweenPhases;
                waitBeforeQuittingApp = BaseLoader.Instance.Resource.mWaitBeforeQuittingApp;
            }
            AskPhase1Start += StartPhase1;
            PhaseFinished += OnPhaseFinished;
        }

        private void Update()
        {
            if (startPhase1)
            {
                startPhase1 = false;
                StartPhase1();
            }

            if (startPhase2)
            {
                startPhase2 = false;
                StartPhase2();
            }

            if (startPhase3)
            {
                startPhase3 = false;
                StartPhase3();
            }
        }

        private void OnPhaseFinished(string eventName)
        {
            _currentPhase++;
            if (!autoLinkingPhase) return;
            switch (_currentPhase)
            {
                case 1:
                    StartPhase2();
                    break;
                case 2:
                    StartPhase3();
                    break;
                case 3:
                    FinishTest();
                    break;
                default:
                    Debug.Log("All phases finished");
                    break;
            }
        }

        private void StartPhase1()
        {
            Debug.Log("Phase 1 starting...");
            Debug.Log("Phase 1 intends for players to connect to the server and then start instantiation phase");
            // Depending on the configuration player should connect and phase 1 will start
            //i.e. this works here in base but should be changed depending on your network implementation
            PhaseStarted.Invoke("PhaseStarted");
            StartCoroutine(WaitAndStartPhase1());
        }

        private void StartPhase2()
        {
            Debug.Log("Phase 2 starting...");
            Debug.Log("Phase 2 intends for objects to instantiate via InstantiateManager per wave defined in the manager");
            PhaseStarted.Invoke("PhaseStarted");
            StartCoroutine(WaitAndStartPhase2());
        }

        private void StartPhase3()
        {
            Debug.Log("Phase 3 starting...");
            Debug.Log("Phase 3 intends for objects instantiated to move one by one, everything is defined in MoveManager");
            PhaseStarted.Invoke("PhaseStarted");
            StartCoroutine(WaitAndStartPhase3());
        }

        private void FinishTest()
        {
            Debug.Log("Phase 3 finished");
            Debug.Log("Waiting for " + waitBeforeQuittingApp + " seconds before quitting the application...");
            StartCoroutine(WaitAndQuit());
        }

        private IEnumerator WaitAndStartPhase1()
        {
            yield return new WaitForSeconds(waitingPhase1Time);
            PhaseFinished.Invoke("PhaseFinished");
        }

        private IEnumerator WaitAndStartPhase2()
        {
            yield return new WaitForSeconds(waitBetweenPhases);
            InstantiateManager.Instance.StartSpawning();
            yield return null;
        }

        private IEnumerator WaitAndStartPhase3()
        {
            yield return new WaitForSeconds(waitBetweenPhases);
            MoveManager.Instance.StartMovingCubes();
            yield return null;
        }

        private IEnumerator WaitAndQuit()
        {
            yield return new WaitForSeconds(waitBeforeQuittingApp);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }
    }
