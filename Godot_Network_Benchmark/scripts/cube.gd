extends Node3D

@export var speed: float = 5.0

var velocity: float = 0.0
var is_moving: bool = false

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _physics_process(delta: float) -> void:
	if is_moving:
		move(delta)
		jump(delta)
		rotate_place(delta)


func move(delta: float) -> void:
	global_position += -global_transform.basis.z * speed * delta
	
func jump(delta: float) -> void:
	var pos = global_position
	
	if pos.y <= 0.0:
		velocity = 5.0
		
	velocity -= 1.0 * delta
	pos.y += velocity * delta
	
	if pos.y <= 0.0:
		pos.y = 0.0
		
	global_position = pos
	
func rotate_place(delta: float) -> void:
	rotate_y(deg_to_rad(90.0 * delta))
