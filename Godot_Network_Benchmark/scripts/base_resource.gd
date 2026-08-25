extends Resource
class_name base_resource

@export var prefab: PackedScene

@export var amount := 0
@export var spawn_once := false

@export var time_before_each_spawn := 0.0
@export var number_per_wave := 0

@export var percentage_moving_cubes_per_wave := 0.0
@export var time_before_moving_cubes := 0.0

@export var waiting_phase1_time := 0.0
@export var wait_between_phases := 0.0
@export var wait_before_quitting_app := 0.0

@export var move_and_spawn := false

@export var multiplayer_mode:= "client"

@export var server_address := ""

func load_from_json(path: String) -> void:
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        push_error("Cannot open %s" % path)
        return

    var json := JSON.new()
    var err := json.parse(file.get_as_text())

    if err != OK:
        push_error("JSON parse error")
        return

    var data: Dictionary = json.data

    amount = int(data.get("mAmount", amount))
    spawn_once = bool(data.get("mSpawnOnce", spawn_once))
    time_before_each_spawn = float(data.get("mTimeBeforeEachSpawn", time_before_each_spawn))
    number_per_wave = int(data.get("mNumberPerWave", number_per_wave))
    percentage_moving_cubes_per_wave = float(
        data.get("mPercentageMovingCubesPerWave", percentage_moving_cubes_per_wave)
    )
    time_before_moving_cubes = float(
        data.get("mTimeBeforeMovingCubes", time_before_moving_cubes)
    )

    waiting_phase1_time = float(
        data.get("mWaitingPhase1Time", waiting_phase1_time)
    )

    wait_between_phases = float(
        data.get("mWaitBetweenPhases", wait_between_phases)
    )

    wait_before_quitting_app = float(
        data.get("mWaitBeforeQuittingApp", wait_before_quitting_app)
    )

    move_and_spawn = bool(data.get("moveAndSpawn", move_and_spawn))

    multiplayer_mode = data.get("multiplayerMode", multiplayer_mode)
    server_address = data.get("mServerAddress", server_address)