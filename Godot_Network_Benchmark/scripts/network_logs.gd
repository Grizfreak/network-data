extends Node

@onready var InstantiateManager = $"../InstantiateManager"
@onready var PhaseManager = $"../PhaseManager"
@onready var MoveManager = $"../MoveManager"
@onready var LogsManager = $"../LogsManager"
@onready var Profiler = $"../ProfilerStatsToCSVExporter"
		

func _ready() -> void:
	if multiplayer.is_server():
		print("Server is running, starting to log network events.")
		Profiler.filename = "server"
		LogsManager.EVENTS_FILE_NAME = "server_godot_events_"
		# Connect signals for logging
		InstantiateManager.starting_instantiation.connect(started_instantiation)
		InstantiateManager.finished_instantiation.connect(finished_instantiation)

		PhaseManager.phase_started.connect(phase_started)
		PhaseManager.phase_finished.connect(phase_finished)
		MoveManager.start_moving_entities.connect(start_moving_entities)
		MoveManager.end_moving_entities.connect(end_moving_entities)
	else:
		Profiler.filename = "client"
		LogsManager.EVENTS_FILE_NAME = "client_godot_events_"
		print("Client is running, logging network events will be handled by the server.")

func started_instantiation(event_name: String) -> void:
	started_instantiation_rpc.rpc(event_name)

@rpc("authority") 
func started_instantiation_rpc(event_name: String) -> void:
	LogsManager._on_log_event(event_name)

func finished_instantiation(event_name: String, value: int) -> void:
	finished_instantiation_rpc.rpc(event_name, value)

@rpc("authority") 
func finished_instantiation_rpc(event_name: String, value: int) -> void:
	LogsManager._on_log_event_with_value(event_name, value)

func phase_started(event_name: String) -> void:
	phase_started_rpc.rpc(event_name)

@rpc("authority") 
func phase_started_rpc(event_name: String) -> void:
	LogsManager._on_log_event(event_name)

func phase_finished(event_name: String) -> void:
	phase_finished_rpc.rpc(event_name)

@rpc("authority")
func phase_finished_rpc(event_name: String) -> void:
	LogsManager._on_log_event(event_name)

func start_moving_entities(event_name: String) -> void:
	start_moving_entities_rpc.rpc(event_name)

@rpc("authority") 
func start_moving_entities_rpc(event_name: String) -> void:
	LogsManager._on_log_event(event_name)

func end_moving_entities(event_name: String) -> void:
	end_moving_entities_rpc.rpc(event_name)
	
@rpc("authority") 
func end_moving_entities_rpc(event_name: String) -> void:
	LogsManager._on_log_event(event_name)
