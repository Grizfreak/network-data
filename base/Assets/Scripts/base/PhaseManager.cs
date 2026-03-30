using System;
using System.Collections;
using UnityEngine;

public class PhaseManager : MonoBehaviour
{
    public static PhaseManager instance;
    public bool startPhase1 = false;
    public bool startPhase2 = false;
    public bool startPhase3 = false;
    public bool autoLinkingPhase = true;
    public float waitingPhase1Time = 2f;
    public float waitBetweenPhases = 2f;
    private int _currentPhase = 0;
    public Action<string> PhaseFinished;

    void Awake()
    {
        if (instance == null)
        {
            instance = this;
        }
        else
        {
            Destroy(gameObject);
        }
    }

    void Start()
    {
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
        if (autoLinkingPhase)
        {
            switch (_currentPhase)
            {
                case 1:
                    StartPhase2();
                    break;
                case 2:
                    StartPhase3();
                    break;
                default:
                    Debug.Log("All phases finished");
                    break;
            }
        }
    }

    private void StartPhase1()
    {
        Debug.Log("Phase 1 starting...");
        Debug.Log("Phase 1 intends for players to connect to the server and then start instantiation phase");
        // Depending on the configuration player should connect and phase 1 will start
        //i.e this works here in base but should be changed depending your network implementation
        StartCoroutine(WaitAndStartPhase1());
    }

    private void StartPhase2()
    {
        Debug.Log("Phase 2 starting...");
        Debug.Log("Phase 2 intends for objects to instantiate via InstantiateManager per wave defined in the manager");
        StartCoroutine(WaitAndStartPhase2());
    }

    private void StartPhase3()
    {
        Debug.Log("Phase 3 starting...");
        Debug.Log("Phase 3 intends for objects instantiated to move one by one, everything is defined in MoveManager");
        StartCoroutine(WaitAndStartPhase3());
    }

    private IEnumerator WaitAndStartPhase1()
    {
        yield return new WaitForSeconds(waitingPhase1Time);
        PhaseFinished.Invoke("PhaseFinished");
    }

    private IEnumerator WaitAndStartPhase2()
    {
        yield return new WaitForSeconds(waitBetweenPhases);
        InstantiateManager.instance.StartSpawning();
        yield return null;
    }

    private IEnumerator WaitAndStartPhase3()
    {
        yield return new WaitForSeconds(waitBetweenPhases);
        MoveManager.instance.StartMovingCubes();
        yield return null;
    }
}
