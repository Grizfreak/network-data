extends Node


var searching_for_phase_manager : bool
@export var start_auto_phase_1 : bool = true
var phase_manager : Node

func _ready():
	get_tree().scene_changed.connect(on_scene_changed)

func _process(_delta) -> void:
	if searching_for_phase_manager:
		phase_manager = get_node_or_null("/root/Benchmark/Manager/PhaseManager")
		if phase_manager:
			searching_for_phase_manager = false
			if start_auto_phase_1:
				phase_manager.ask_phase1_start.emit()
				start_auto_phase_1 = false

func on_scene_changed():
	if multiplayer.is_server():
		searching_for_phase_manager = true
	else:
		start_auto_phase_1 = false
