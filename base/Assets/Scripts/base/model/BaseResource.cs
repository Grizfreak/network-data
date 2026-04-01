using UnityEngine;

[CreateAssetMenu(fileName = "BaseResource", menuName = "Scriptable Objects/BaseResource")]
public class BaseResource : ScriptableObject
{
    [Header("Instantiation Management")]
    public GameObject m_Prefab;
    public int m_Amount;
    public bool m_SpawnOnce;
    public float m_TimeBeforeEachSpawn;
    public int m_NumberPerWave;
    [Header("Movement Management")]
    public float m_PercentageMovingCubesPerWave;
    public float m_TimeBeforeMovingCubes;

    [Header("Phase Management")] 
    public float m_WaitingPhase1Time;
    public float m_WaitBetweenPhases;
    public float m_WaitBeforeQuittingApp;

    public void ParseConfiguration(string fileContent)
    {
        // JsonUtility.FromJsonOverwrite takes the JSON string and 
        // injects the values directly into this ScriptableObject instance.
        JsonUtility.FromJsonOverwrite(fileContent, this);
    }

}
