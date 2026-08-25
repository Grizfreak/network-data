# Protocole expérimental — résumé

Résumé Markdown, pour une lecture rapide, du protocole formel. La version
qui fait foi reste le LaTeX/PDF :
[FR](protocole_experimental.pdf) · [EN](protocol_eng.pdf) (sources
[`.tex`](protocole_experimental.tex) à côté). En cas de divergence entre ce
résumé et le PDF, le PDF a priorité — ce fichier n'est volontairement pas
signé/versionné comme un document de méthodologie officiel.

## Objectif de l'étude

Comparer plusieurs méthodes d'affichage d'un volume important d'objets dans
Unity, en particulier l'impact des mécanismes réseau sur les performances de
rendu, de calcul et de synchronisation.

## Déroulement (3 phases)

Un protocole unique est appliqué à toutes les solutions évaluées pour
garantir la reproductibilité — voir
[ADR 0003](../architecture/decisions/0003-phase-based-workload-shape.md)
pour la justification de cette structure en phases et
[reference.md#benchmark-flow](../reference.md#benchmark-flow) pour
l'implémentation.

1. **Préparation** — initialisation de l'environnement et des conditions de
   lancement.
2. **Instanciation** — entités instanciées progressivement par vagues
   successives, mêmes paramètres pour tous les scénarios.
3. **Mouvement** — les entités instanciées sont progressivement mises en
   mouvement jusqu'à 100 % de la population simulée.

> **Note du protocole original :** dans la version actuelle de
> l'expérimentation, les phases 2 et 3 sont fusionnées en un seul scénario
> (*Spawn + Move*) — la distinction phase 2 / phase 3 n'est conservée dans
> le protocole que pour rester compatible avec des expérimentations
> antérieures. Correspond au champ `moveAndSpawn` de
> [`BaseResource`](../reference.md#configuration) (utilisé par exemple par
> le sample `AcceleratedBase.json`).

## Périmètre de l'analyse réseau

L'étude ne porte **pas** sur le nombre maximal de clients connectés
simultanément (des travaux antérieurs suggèrent une évolution prévisible
avec ce paramètre). L'analyse se concentre sur, pour un client unique :

- capacité d'affichage des données ;
- charge côté serveur ;
- charge côté client ;
- coûts de synchronisation réseau.

## Paramètres expérimentaux

| Paramètre | Valeur |
|---|---|
| Nombre total d'entités | 20 000 |
| Taille d'une vague d'instanciation | 400 |
| Délai entre deux vagues | 10 s |
| Entités mises en mouvement par palier | 10 % |
| Délai avant activation du mouvement | 5 s |
| Durée de préparation initiale | 10 s |
| Temps d'attente entre phases | 10 s |
| Temps avant fermeture automatique | 10 s |
| Mode d'exécution | Spawn + Move |

Ces valeurs correspondent aux champs `mAmount`, `mNumberPerWave`,
`mTimeBeforeEachSpawn`, `mPercentageMovingCubesPerWave`,
`mTimeBeforeMovingCubes`, `mWaitingPhase1Time`, `mWaitBetweenPhases`,
`mWaitBeforeQuittingApp` — voir
[reference.md#configuration](../reference.md#configuration) pour le détail
de chaque champ, et [`Resources/AcceleratedBase.json`](../../Resources/AcceleratedBase.json)
pour l'échantillon "Spawn + Move" qu'elles décrivent.

### Définition d'une entité

Cube Unity standard (12 triangles), texture de base, pas d'éclairage
dynamique. Dans les versions réseau, chaque entité possède un
`NetworkObject` et un composant de synchronisation de position spécifique à
l'implémentation testée. Déplacement à vitesse constante (5 m/s sur chaque
axe) avec rotation uniforme simultanée.

## Groupes d'étude

- **Configuration locale** — aucune couche réseau visible ; évalue les
  limites intrinsèques du moteur de rendu (voir les variantes `base*` et
  `Godot_Benchmark` dans
  [architecture/README.md](../architecture/README.md#benchmark-client-variants)).
- **Configuration réseau** — comportement serveur/client dans une
  architecture client-serveur réelle (`ngo`, `fishNet`, `photonFusion`,
  `NetcodeEntities`, `Godot_Network_Benchmark`).

## Mesures collectées

Voir [data-dictionary.md](../data-dictionary.md) pour la colonne CSV brute
et l'unité exactes derrière chaque mesure ci-dessous.

- **Performances de rendu** — FPS, temps CPU/image (ms), temps GPU/image (ms).
- **Mémoire** — mémoire utilisée (MB).
- **Performances réseau** — RTT, RTT calculé via RPC.
- **Charge réseau** — débit montant/descendant, volume total envoyé/reçu,
  nombre de paquets envoyés/reçus.
- **Analyse du trafic** (capture réseau indépendante) — paquets/s, volume de
  données échangé, volumes cumulés, évolution de la charge dans le temps.

## Méthode d'analyse

Les indicateurs sont étudiés en fonction du nombre d'entités présentes dans
la scène, pour identifier : limites serveur/client, impact de la couche
réseau, goulets d'étranglement, tendances de consommation de ressources,
limites matérielles par plateforme. C'est l'approche que
[Pipeline B (`load_analysis.py`)](../data-analysis/ccl/README.md#pipeline-b--load-based-analysis-load_analysispy)
implémente statistiquement — voir aussi
[ADR 0004](../architecture/decisions/0004-dual-analysis-pipelines.md).

## Clients évalués

1. PC.
2. Casque autonome Meta Quest 3.

Résultats analysés séparément par plateforme.

## Configuration matérielle

### Serveur (FishNet, Netcode for GameObjects)

Dell Precision 7550, headless.

| Composant | Caractéristiques |
|---|---|
| Système | Windows 11 Enterprise 64 bits |
| CPU | Intel Core i7-10850H |
| RAM | 32 Go |
| GPU | NVIDIA Quadro RTX 3000 |
| API | DirectX 12 |
| Résolution | 1920 × 1080 |

### Client PC

| Composant | Caractéristiques |
|---|---|
| Système | Windows 11 Enterprise 64 bits |
| CPU | Intel Core Ultra 9 285K |
| RAM | 128 Go |
| GPU | NVIDIA RTX 5000 Ada Generation |
| API | DirectX 12 |
| Résolution | 2560 × 1440 |

### Client réalité virtuelle

Meta Quest 3.

## Infrastructure et configuration réseau

- **FishNet / Netcode for GameObjects** : serveur et clients sur un réseau
  local, routeur Netgear R6020 — conditions réseau stables et contrôlées.
- **Photon** : communications via l'infrastructure cloud du fournisseur
  (Internet) — les latences mesurées **ne sont donc pas directement
  comparables** à celles des architectures locales.
