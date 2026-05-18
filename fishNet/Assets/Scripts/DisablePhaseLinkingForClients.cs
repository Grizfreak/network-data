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
            if (PhaseManager.Instance != null)
            {
                searchForPhaseManager = false;
                PhaseManager.Instance.autoLinkingPhase = false;
            }
        }
    }
}
