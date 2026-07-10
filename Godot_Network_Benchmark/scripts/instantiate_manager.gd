extends Node

signal starting_instantiation(message: String)
signal finished_instantiation(message: String, amount: int)
signal instance_created(instance: Node3D)

@export var object_to_spawn: PackedScene
@export var number_to_spawn: int = 10
@export var spawn_instantly: bool = true
@export var time_before_spawn: float = 1.0
@export var number_per_wave: int = 5

## A Node3D with a MeshInstance3D child (or any node that defines the spawn area)
@export var spawn_zone: MeshInstance3D

@onready var phase_manager = $"../PhaseManager"

var spawned_instances: int = 0

func _ready() -> void:
	if BaseLoader == null:
		return

	object_to_spawn = BaseLoader.resource.prefab
	number_to_spawn = BaseLoader.resource.amount
	spawn_instantly = BaseLoader.resource.spawn_once
	time_before_spawn = BaseLoader.resource.time_before_each_spawn
	number_per_wave = BaseLoader.resource.number_per_wave

func start_spawning() -> void:
	if spawn_instantly:
		spawn_objects()
	else:
		spawn_objects_by_group()

func random_spawn_position() -> Vector3:
	var aabb := spawn_zone.get_aabb()

	# Point aléatoire dans l'espace local du mesh
	var local_pos := Vector3(
		randf_range(aabb.position.x, aabb.position.x + aabb.size.x),
		0.0,
		randf_range(aabb.position.z, aabb.position.z + aabb.size.z)
	)

	# Conversion en coordonnées monde
	return spawn_zone.to_global(local_pos)

func spawn_objects() -> void:
	await get_tree().create_timer(time_before_spawn).timeout

	starting_instantiation.emit("StartedInstantiation")

	for i in number_to_spawn:
		var obj = object_to_spawn.instantiate()
		obj.global_position = random_spawn_position()

		add_child(obj)

		if phase_manager.move_and_spawn:
			obj.is_moving = true

		instance_created.emit(obj)

	finished_instantiation.emit("FinishedInstantiation", number_to_spawn)
	phase_manager.phase_finished.emit("PhaseFinished")

func spawn_objects_by_group() -> void:
	while spawned_instances < number_to_spawn:

		await get_tree().create_timer(time_before_spawn).timeout

		starting_instantiation.emit("StartedInstantiation")

		for i in number_per_wave:
			if spawned_instances >= number_to_spawn:
				break

			var obj = object_to_spawn.instantiate()
			add_child(obj)
			obj.global_position = random_spawn_position()

			if phase_manager.move_and_spawn:
				obj.is_moving = true

			instance_created.emit(obj)

			spawned_instances += 1

		finished_instantiation.emit("FinishedInstantiation", spawned_instances)

	phase_manager.phase_finished.emit("PhaseFinished")
