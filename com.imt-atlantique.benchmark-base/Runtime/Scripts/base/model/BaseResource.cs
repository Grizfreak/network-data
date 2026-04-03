using UnityEngine;
using UnityEngine.Serialization;

    [CreateAssetMenu(fileName = "BaseResource", menuName = "Scriptable Objects/BaseResource")]
    public class BaseResource : ScriptableObject
    {
        [FormerlySerializedAs("MPrefab")] [FormerlySerializedAs("m_Prefab")] [Header("Instantiation Management")]
        public GameObject mPrefab;

        [FormerlySerializedAs("m_Amount")] public int mAmount;
        [FormerlySerializedAs("m_SpawnOnce")] public bool mSpawnOnce;

        [FormerlySerializedAs("m_TimeBeforeEachSpawn")]
        public float mTimeBeforeEachSpawn;

        [FormerlySerializedAs("m_NumberPerWave")]
        public int mNumberPerWave;

        [FormerlySerializedAs("m_PercentageMovingCubesPerWave")] [Header("Movement Management")]
        public float mPercentageMovingCubesPerWave;

        [FormerlySerializedAs("m_TimeBeforeMovingCubes")]
        public float mTimeBeforeMovingCubes;

        [FormerlySerializedAs("m_WaitingPhase1Time")] [Header("Phase Management")]
        public float mWaitingPhase1Time;

        [FormerlySerializedAs("m_WaitBetweenPhases")]
        public float mWaitBetweenPhases;

        [FormerlySerializedAs("m_WaitBeforeQuittingApp")]
        public float mWaitBeforeQuittingApp;

        public void ParseConfiguration(string fileContent)
        {
            // JsonUtility.FromJsonOverwrite takes the JSON string and 
            // injects the values directly into this ScriptableObject instance.
            JsonUtility.FromJsonOverwrite(fileContent, this);
        }

    }
