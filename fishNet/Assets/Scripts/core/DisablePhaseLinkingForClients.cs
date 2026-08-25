using UnityEngine;

public class DisablePhaseLinkingForClients : MonoBehaviour
{

    private bool searchForPhaseManager = false;

    public void setSearch(bool value)
    {
        searchForPhaseManager = value;
    }

    // Update is called once per frame
    void Update()
    {
        if (searchForPhaseManager)
        {
            Debug.Log("Trying to disable auto linking phase for clients");
            if (PhaseManager.Instance != null)
            {
                searchForPhaseManager = false;
                PhaseManager.Instance.autoLinkingPhase = false;
                Debug.Log("Auto linking phase disabled for clients");
            }
        }
    }
}
