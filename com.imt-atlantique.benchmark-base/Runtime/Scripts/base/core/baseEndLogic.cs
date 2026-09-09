using UnityEngine;

/// <summary>Calls PhaseManager.FinishTest when the benchmark reports it is finishing.</summary>
public class BaseEndLogic : MonoBehaviour
{
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    private void Start()
    {
        PhaseManager.Instance.FinishingExperimentation += () =>
        {
            PhaseManager.Instance.FinishTest();
        };
    }
}
