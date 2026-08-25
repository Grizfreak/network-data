extends Node

signal start_moving_entities(message: String)
signal end_moving_entities(message: String)

var static_cubes: Array[Node3D] = []
var moving_cubes: Array[Node3D] = []

var percentage_of_moving_cubes: float
var time_before_moving_cubes: float

var start_moving := false
var stop_moving := false

@onready var phase_manager = $"../PhaseManager"
@onready var instantiate_manager = $"../InstantiateManager"


func _ready() -> void:
	percentage_of_moving_cubes = BaseLoader.resource.percentage_moving_cubes_per_wave
	time_before_moving_cubes = BaseLoader.resource.time_before_moving_cubes

	instantiate_manager.instance_created.connect(_on_instance_created)


func _process(_delta: float) -> void:
	if start_moving:
		start_moving = false
		start_moving_cubes()

	if stop_moving:
		stop_moving = false
		stop_moving_cubes()


func _on_instance_created(cube: Node3D) -> void:
	static_cubes.append(cube)


func start_moving_cubes() -> void:
	_move_cubes()


func stop_moving_cubes() -> void:
	for cube in moving_cubes:
		cube.is_moving = false


func _move_cubes() -> void:
	var total := static_cubes.size() + moving_cubes.size()
	var number_to_move :int = max(1, int(total * percentage_of_moving_cubes / 100.0))

	while !static_cubes.is_empty():
		await get_tree().create_timer(time_before_moving_cubes).timeout

		start_moving_entities.emit("StartedMovingLocally")

		for _i in range(number_to_move):
			if static_cubes.is_empty():
				break

			var index := randi_range(0, static_cubes.size() - 1)
			var cube := static_cubes[index]

			static_cubes.remove_at(index)
			moving_cubes.append(cube)

			cube.is_moving = true

		end_moving_entities.emit("EndedMovingLocally")

	phase_manager.phase_finished.emit("PhaseFinished")
