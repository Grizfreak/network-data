extends Node

@export var android_subsystem: Node
@export var windows_subsystem: Node

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	print(OS.get_name())
	if OS.get_name() == "Android":
		android_subsystem.visible = true
		windows_subsystem.queue_free()
		android_subsystem.get_node("XRCamera3D").current = true
	elif OS.get_name() == "Windows":
		android_subsystem.queue_free()
		windows_subsystem.visible = true
		windows_subsystem.current = true
