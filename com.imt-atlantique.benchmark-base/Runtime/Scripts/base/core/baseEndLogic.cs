using UnityEngine;

// NOTE: file name is lowercase ("baseEndLogic.cs") while the class below is "BaseEndLogic"; not renamed here since the file may be referenced by Unity meta/GUID and a rename is risky without further verification.
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
