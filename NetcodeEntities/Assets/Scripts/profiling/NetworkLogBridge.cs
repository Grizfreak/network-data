using Unity.Collections;
using Unity.Entities;
using Unity.NetCode;
using UnityEngine;

public class NetworkLogsBridge : MonoBehaviour
{
    private EntityManager _entityManager;

    private void Start()
    {
        var serverWorld = GetServerWorld();

        if (serverWorld == null)
        {
            Debug.Log("No server world found.");
            return;
        }

        _entityManager = serverWorld.EntityManager;

        InstantiateManager.Instance.StartingInstantiation += OnStartingInstantiation;
        InstantiateManager.Instance.FinishedInstantiation += OnFinishedInstantiation;

        PhaseManager.Instance.PhaseStarted += OnPhaseStarted;
        PhaseManager.Instance.PhaseFinished += OnPhaseFinished;
        PhaseManager.Instance.FinishingExperimentation += OnFinishingExperimentation;

        MoveManager.Instance.StartMovingEntities += OnStartMovingEntities;
        MoveManager.Instance.EndMovingEntities += OnEndMovingEntities;
    }

    private void OnDestroy()
    {
        if (InstantiateManager.Instance != null)
        {
            InstantiateManager.Instance.StartingInstantiation -= OnStartingInstantiation;
            InstantiateManager.Instance.FinishedInstantiation -= OnFinishedInstantiation;
        }

        if (PhaseManager.Instance != null)
        {
            PhaseManager.Instance.PhaseStarted -= OnPhaseStarted;
            PhaseManager.Instance.PhaseFinished -= OnPhaseFinished;
            PhaseManager.Instance.FinishingExperimentation -= OnFinishingExperimentation;
        }

        if (MoveManager.Instance != null)
        {
            MoveManager.Instance.StartMovingEntities -= OnStartMovingEntities;
            MoveManager.Instance.EndMovingEntities -= OnEndMovingEntities;
        }
    }

    private void OnStartingInstantiation(string msg)
    {
        SendLogEvent(LogEventType.StartingInstantiation, msg);
    }

    private void OnFinishedInstantiation(string msg, int value)
    {
        SendLogEvent(LogEventType.FinishedInstantiation, msg, value);
    }

    private void OnPhaseStarted(string msg)
    {
        SendLogEvent(LogEventType.PhaseStarted, msg);
    }

    private void OnPhaseFinished(string msg)
    {
        SendLogEvent(LogEventType.PhaseFinished, msg);
    }

    private void OnStartMovingEntities(string msg)
    {
        SendLogEvent(LogEventType.StartMovingEntities, msg);
    }

    private void OnEndMovingEntities(string msg)
    {
        SendLogEvent(LogEventType.EndMovingEntities, msg);
    }

    private void OnFinishingExperimentation()
    {
        SendLogEvent(LogEventType.EndExperiment);
    }

    private void SendLogEvent(
        LogEventType type,
        string message = "",
        int value = 0)
    {
        Entity rpc = _entityManager.CreateEntity();

        _entityManager.AddComponentData(rpc,
            new LogEventRpc
            {
                Type = type,
                Message = message,
                Value = value
            });

        _entityManager.AddComponentData(
            rpc,
            new SendRpcCommandRequest());
    }

    private static World GetServerWorld()
    {
        foreach (var world in World.All)
        {
            if (world.IsServer())
                return world;
        }

        return null;
    }
}