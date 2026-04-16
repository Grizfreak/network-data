using UnityEngine;

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
