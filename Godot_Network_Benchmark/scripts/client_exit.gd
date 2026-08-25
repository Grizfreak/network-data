extends Node

@onready var PhaseManager = get_node("../PhaseManager")
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	if !multiplayer.is_server():
		multiplayer.server_disconnected.connect(_on_server_disconnected)


func _on_server_disconnected():
	print("Disconnected from server. Exiting the game.")
	PhaseManager.finish_test()

