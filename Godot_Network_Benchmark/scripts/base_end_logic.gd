extends Node

@onready var phase_manager = $"../PhaseManager"

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	phase_manager.finishing_experimentation.connect(_on_finishing_experimentation)

func _on_finishing_experimentation() -> void:
	phase_manager.finish_test()
