extends Node

func _ready() -> void:
    call_deferred("_load_benchmark")

func _load_benchmark() -> void:
    get_tree().change_scene_to_file("res://scenes/benchmark.tscn")