extends Node

# Signals for phase management
signal phase_started(name: String)
signal phase_finished(name: String)
signal ask_phase1_start
signal finishing_experimentation

# Configuration properties
@export var auto_linking_phase := true
@export var waiting_phase1_time := 2.0
@export var wait_between_phases := 2.0
@export var wait_before_quitting_app := 5.0
@export var move_and_spawn := false

# State variables
var start_phase_1 := false
var start_phase_2 := false
var start_phase_3 := false
var current_phase := 0

func _ready():
	# Set up autoload pattern - this script should be added as PhaseManager in Project Settings
	if name != "PhaseManager":
		queue_free()
	
	# Load configuration from BaseLoader if available
	if BaseLoader:
		waiting_phase1_time = BaseLoader.resource.waiting_phase1_time
		wait_between_phases = BaseLoader.resource.wait_between_phases
		wait_before_quitting_app = BaseLoader.resource.wait_before_quitting_app
		move_and_spawn = BaseLoader.resource.move_and_spawn

	if !multiplayer.is_server():
		print("This is not the server, phase management will be handled by the server.")
		auto_linking_phase = false
	
	# Connect signals
	ask_phase1_start.connect(start_phase1)
	phase_finished.connect(on_phase_finished)

func _process(_delta: float):
	if start_phase_1:
		start_phase_1 = false
		start_phase1()
	
	if start_phase_2:
		start_phase_2 = false
		start_phase2()
	
	if start_phase_3:
		start_phase_3 = false
		start_phase3()

func on_phase_finished(_phase_name: String):
	current_phase += 1
	if not auto_linking_phase:
		return
	
	match current_phase:
		1:
			start_phase2()
		2:
			if not move_and_spawn:
				start_phase3()
			else:
				finishing_experimentation.emit()
		3:
			finishing_experimentation.emit()
		_:
			print("All phases finished")

func start_phase1():
	print("Phase 1 starting...")
	print("Phase 1 intends for players to connect to the server and then start instantiation phase")
	# Depending on the configuration player should connect and phase 1 will start
	# i.e. this works here in base but should be changed depending on your network implementation
	phase_started.emit("PhaseStarted")
	await get_tree().create_timer(waiting_phase1_time).timeout
	phase_finished.emit("PhaseFinished")

func start_phase2():
	print("Phase 2 starting...")
	print("Phase 2 intends for objects to instantiate via InstantiateManager per wave defined in the manager")
	phase_started.emit("PhaseStarted")
	await get_tree().create_timer(wait_between_phases).timeout
	var instantiate_manager = get_node_or_null("/root/Benchmark/Manager/InstantiateManager")
	if instantiate_manager and instantiate_manager.has_method("start_spawning"):
		instantiate_manager.call("start_spawning")

func start_phase3():
	print("Phase 3 starting...")
	print("Phase 3 intends for objects instantiated to move one by one, everything is defined in MoveManager")
	phase_started.emit("PhaseStarted")
	await get_tree().create_timer(wait_between_phases).timeout
	var move_manager = get_node_or_null("/root/Benchmark/Manager/MoveManager")
	if move_manager and move_manager.has_method("start_moving"):
		move_manager.call("start_moving")

func finish_test(terminate: bool = true):
	print("Phase 3 finished")
	if terminate:
		print("Waiting for " + str(wait_before_quitting_app) + " seconds before quitting the application...")
		await get_tree().create_timer(wait_before_quitting_app).timeout
		# Quit the application
		get_tree().quit()
