using Unity.Entities;
using UnityEngine;
public class ECSPhaseManager : PhaseManager
{
        private bool hasInstantiated = false;
        private bool hasMoved = false;
        
        private EntityManager _em;
        private Entity _configEntity;
        private EntityQuery _numberOfStaticInstances;

        private int lastRecordedEntityCount = 0;
        
        protected override void Start()
        {
                base.Start();

                _em = World.DefaultGameObjectInjectionWorld.EntityManager;

                _configEntity =
                        _em.CreateEntityQuery(typeof(BenchmarkConfig))
                                .GetSingletonEntity();
                _numberOfStaticInstances = _em.CreateEntityQuery(typeof(StaticTag));
        }
        protected override void Update()
        {
                base.Update();

                var config =
                        _em.GetComponentData<BenchmarkConfig>(_configEntity);

                // -------------------------
                // PHASE 2 → spawn completed
                // -------------------------
                if (!hasInstantiated)
                {
                        // log every numberPerWave
                        if (config.SpawnedEntities > lastRecordedEntityCount)
                        { 
                                InstantiateManager.Instance.FinishedInstantiation.Invoke("FinishedInstantiation", config.SpawnedEntities);
                                lastRecordedEntityCount = config.SpawnedEntities;
                        }
                        if (config.SpawnedEntities >= config.NumberToSpawn)
                        {
                                hasInstantiated = true;

                                PhaseFinished?.Invoke("PhaseFinished");
                        }
                        return;
                }
                
                if (!hasMoved)
                {
                        bool anyMoving = _numberOfStaticInstances.CalculateEntityCount() > 0;

                        if (!anyMoving)
                        {
                                hasMoved = true;

                                PhaseFinished?.Invoke("PhaseFinished");
                        }
                }
        }

        protected override void StartPhase2()
        {
                Debug.Log("Phase 2 starting...");
                Debug.Log("Phase 2 intends for objects to instantiate via InstantiateManager per wave defined in the manager");
                PhaseStarted.Invoke("PhaseStarted");
                var config =
                        _em.GetComponentData<BenchmarkConfig>(_configEntity);

                config.StartSpawn = true;
                config.StartMove = false;
                config.SpawnedEntities = 0;

                _em.SetComponentData(_configEntity, config);
        }

        protected override void StartPhase3()
        {
                Debug.Log("Phase 3 starting...");
                Debug.Log("Phase 3 intends for objects instantiated to move one by one, everything is defined in MoveManager");
                PhaseStarted.Invoke("PhaseStarted");
                var config =
                        _em.GetComponentData<BenchmarkConfig>(_configEntity);

                config.StartSpawn = false;
                config.StartMove = true;

                _em.SetComponentData(_configEntity, config);
        }
}
