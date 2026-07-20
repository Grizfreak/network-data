extends Node


var EVENTS_FILE_NAME := "godot_events_"

var events_file: FileAccess
var events_file_path: String

@onready var PhaseManager = get_node("../PhaseManager")
@onready var InstantiateManager = get_node("../InstantiateManager")
@onready var MoveManager = get_node("../MoveManager")



func _ready() -> void:
    # Connexion des signaux
    InstantiateManager.starting_instantiation.connect(_on_log_event)
    InstantiateManager.finished_instantiation.connect(_on_log_event_with_value)

    PhaseManager.phase_started.connect(_on_log_event)
    PhaseManager.phase_finished.connect(_on_log_event)

    MoveManager.start_moving_entities.connect(_on_log_event)
    MoveManager.end_moving_entities.connect(_on_log_event)

    _create_log_file()


func _create_log_file() -> void:
    var datetime := Time.get_datetime_dict_from_system()

    var filename := "%s%04d%02d%02d_%02d%02d%02d.csv" % [
        EVENTS_FILE_NAME,
        datetime.year,
        datetime.month,
        datetime.day,
        datetime.hour,
        datetime.minute,
        datetime.second
    ]

    if OS.get_name() == "Android":
        events_file_path = "/storage/emulated/0/Android/data/com.IMT_Atlantique.godot_network_benchmark/files/%s" % filename
    else:
        events_file_path = "user://%s" % filename

    events_file = FileAccess.open(events_file_path, FileAccess.WRITE)
    
    if events_file == null:
        push_error("Impossible de créer le fichier : %s" % events_file_path)
        return

    events_file.store_line("Frame,Time,Event,Value")


func _on_log_event(event_name: String) -> void:
    write_event(Engine.get_process_frames(), event_name)


func _on_log_event_with_value(event_name: String, value: int) -> void:
    write_event(Engine.get_process_frames(), event_name, value)


func write_event(frame: int, event_name: String, value: int = -1) -> void:
    if events_file == null:
        push_warning("Le fichier de log n'est pas ouvert.")
        return

    var timestamp := Time.get_ticks_msec() / 1000.0

    events_file.store_line("%d,%.3f,%s,%d" % [
        frame,
        timestamp,
        event_name,
        value
    ])

    # Facultatif : garantit l'écriture immédiate
    events_file.flush()

    print("Event logged : ", event_name)


func _exit_tree() -> void:
    if events_file:
        events_file.flush()
        events_file.close()
