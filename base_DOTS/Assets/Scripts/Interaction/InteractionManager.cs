using TMPro;
using Unity.Collections;
using Unity.Entities;
using UnityEngine;
using UnityEngine.UI;

public class InteractionManager : MonoBehaviour
{
    [Header("UI Elements")]
    [SerializeField] private Button spawnButton;
    [SerializeField] private Button despawnButton;
    [SerializeField] private TMP_InputField spawnCountInput;
    [SerializeField] private TMP_Text FPS_Text;

    private EntityManager entityManager;
    private EntityQuery interactionQuery;
    private EntityQuery instanceQuery;
    private Entity interactionEntity;
    private bool initialized;

    [Header("Value System")]
    [SerializeField] private GameObject panel;
    [SerializeField] private TMP_Text IdText;
    [SerializeField] private TMP_Text RandomIntText;
    [SerializeField] private TMP_Text RandomFloatText;

    private void Start()
    {
        if (spawnCountInput != null)
        {
            spawnCountInput.onValueChanged.AddListener(OnInstanceValueChanged);
        }

        TryInitializeEcsReferences();
        SyncUiFromConfig();
    }

    private void OnDestroy()
    {
        if (spawnCountInput != null)
        {
            spawnCountInput.onValueChanged.RemoveListener(OnInstanceValueChanged);
        }
    }

    private void Update()
    {
        if (FPS_Text != null)
        {
            FPS_Text.text = $"FPS: {Mathf.RoundToInt(1f / Mathf.Max(Time.deltaTime, 0.0001f))}";
        }

        if (!TryInitializeEcsReferences())
            return;

        SyncButtonStates();
        SyncValueDisplay();
    }

    public void SpawnInstances()
    {
        if (!TryInitializeEcsReferences())
            return;

        var config = entityManager.GetComponentData<InteractionSpawnConfig>(interactionEntity);
        if (config.SpawnRequested || config.DespawnRequested)
        {
            SyncButtonStates();
            return;
        }

        config.NumberToSpawn = ReadSpawnCountFromUi(config.NumberToSpawn);
        config.SpawnRequested = true;
        config.DespawnRequested = false;
        entityManager.SetComponentData(interactionEntity, config);

        SyncButtonStates();
    }

    public void DeleteAllCubes()
    {
        if (!TryInitializeEcsReferences())
            return;

        var config = entityManager.GetComponentData<InteractionSpawnConfig>(interactionEntity);
        config.SpawnRequested = false;
        config.DespawnRequested = true;
        entityManager.SetComponentData(interactionEntity, config);

        SyncButtonStates();
    }

    public void OnInstanceValueChanged(string input)
    {
        if (!TryInitializeEcsReferences())
            return;

        if (!int.TryParse(input, out int newValue))
            return;

        newValue = Mathf.Max(0, newValue);

        var config = entityManager.GetComponentData<InteractionSpawnConfig>(interactionEntity);
        config.NumberToSpawn = newValue;
        entityManager.SetComponentData(interactionEntity, config);
    }

    private bool TryInitializeEcsReferences()
    {
        if (initialized)
            return true;

        World world = World.DefaultGameObjectInjectionWorld;
        if (world == null || !world.IsCreated)
            return false;

        entityManager = world.EntityManager;
        interactionQuery = entityManager.CreateEntityQuery(ComponentType.ReadWrite<InteractionSpawnConfig>());
        instanceQuery = entityManager.CreateEntityQuery(ComponentType.ReadOnly<InteractionSpawnedTag>());

        if (!interactionQuery.HasSingleton<InteractionSpawnConfig>())
            return false;

        interactionEntity = interactionQuery.GetSingletonEntity();
        initialized = true;
        return true;
    }

    private void SyncUiFromConfig()
    {
        if (!TryInitializeEcsReferences())
            return;

        var config = entityManager.GetComponentData<InteractionSpawnConfig>(interactionEntity);
        if (spawnCountInput != null)
        {
            spawnCountInput.SetTextWithoutNotify(config.NumberToSpawn.ToString());
        }

        SyncButtonStates();
    }

    private void SyncButtonStates()
    {
        if (!initialized)
            return;

        var config = entityManager.GetComponentData<InteractionSpawnConfig>(interactionEntity);

        if (spawnButton != null)
        {
            spawnButton.interactable = !config.SpawnRequested && !config.DespawnRequested;
        }

        if (despawnButton != null)
        {
            int instanceCount = instanceQuery.CalculateEntityCount();
            despawnButton.interactable = instanceCount > 0;
        }
    }

    private int ReadSpawnCountFromUi(int fallbackValue)
    {
        if (spawnCountInput == null)
            return fallbackValue;

        return int.TryParse(spawnCountInput.text, out int value) ? Mathf.Max(0, value) : fallbackValue;
    }

    private void SyncValueDisplay()
    {
        if (panel != null)
        {
            panel.SetActive(false);
        }

        if (InteractionValuesApi.TryGetHoveredValues(out InteractionEntityValues values))
        {
            if (panel != null)
            {
                panel.SetActive(true);
            }

            if (IdText != null)
            {
                IdText.text = $"ID: {values.Id}";
            }

            if (RandomIntText != null)
            {
                RandomIntText.text = $"Int: {values.RandomInt}";
            }

            if (RandomFloatText != null)
            {
                RandomFloatText.text = $"Float: {values.RandomFloat:F2}";
            }
        }
    }
}
