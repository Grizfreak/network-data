extends Node

const BUCKET_DURATION := 0.5
const FLUSH_INTERVAL := 1.0

var file: FileAccess

var bucket_time := 0.0
var bucket_frames := 0

var fps_sum := 0.0
var frame_time_sum := 0.0
var process_time_sum := 0.0
var physics_time_sum := 0.0

var draw_calls_sum : float = 0
var objects_sum : float = 0
var primitives_sum : float = 0

var texture_memory_sum : float = 0
var video_memory_sum : float = 0
var static_memory_sum : float = 0

var last_flush := 0.0


func _ready():
	var filename = "";
	var timestamp = Time.get_datetime_string_from_system()
	timestamp = timestamp.replace(":", "-")  # Replace colons with hyphens for filename compatibility
	if OS.get_name() == "Android":
		filename = "/storage/emulated/0/Android/data/com.IMT_Atlantique.godot_benchmark/files/godot_profiler_stats_%s.csv" % timestamp
	else:
		filename = "user://godot_profiler_stats_%s.csv" % timestamp
	file = FileAccess.open(filename, FileAccess.WRITE)
	FileAccess.get_open_error()

	file.store_line(
		"Time,Frame,FPS,FrameTimeMs,ProcessTimeMs,PhysicsTimeMs," +
        "DrawCalls,Objects,Primitives,TextureMemory,VideoMemory,StaticMemory"
	)


func _process(delta):

	bucket_time += delta
	bucket_frames += 1

	fps_sum += Performance.get_monitor(Performance.TIME_FPS)
	frame_time_sum += delta * 1000.0

	process_time_sum += Performance.get_monitor(
		Performance.TIME_PROCESS
	) * 1000.0

	physics_time_sum += Performance.get_monitor(
		Performance.TIME_PHYSICS_PROCESS
	) * 1000.0

	draw_calls_sum += Performance.get_monitor(
		Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME
	)

	objects_sum += Performance.get_monitor(
		Performance.RENDER_TOTAL_OBJECTS_IN_FRAME
	)

	primitives_sum += Performance.get_monitor(
		Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME
	)

	texture_memory_sum += Performance.get_monitor(
		Performance.RENDER_TEXTURE_MEM_USED
	)

	video_memory_sum += Performance.get_monitor(
		Performance.RENDER_VIDEO_MEM_USED
	)

	static_memory_sum += Performance.get_monitor(
		Performance.MEMORY_STATIC
	)

	if bucket_time >= BUCKET_DURATION:
		write_bucket()
		reset_bucket()

	var now = Time.get_ticks_msec() / 1000.0

	if now - last_flush >= FLUSH_INTERVAL:
		last_flush = now
		file.flush()


func write_bucket():

	var n = max(bucket_frames, 1)

	var row = "%0.3f,%d,%0.2f,%0.3f,%0.3f,%0.3f,%d,%d,%d,%d,%d,%d" % [

		Time.get_ticks_msec() / 1000.0,

		Engine.get_process_frames(),

		fps_sum / n,

		frame_time_sum / n,

		process_time_sum / n,

		physics_time_sum / n,

		draw_calls_sum / n,

		objects_sum / n,

		primitives_sum / n,

		texture_memory_sum / n,

		video_memory_sum / n,

		static_memory_sum / n
	]

	file.store_line(row)


func reset_bucket():

	bucket_time = 0.0
	bucket_frames = 0

	fps_sum = 0.0
	frame_time_sum = 0.0
	process_time_sum = 0.0
	physics_time_sum = 0.0

	draw_calls_sum = 0
	objects_sum = 0
	primitives_sum = 0

	texture_memory_sum = 0
	video_memory_sum = 0
	static_memory_sum = 0


func _exit_tree():

	if bucket_frames > 0:
		write_bucket()

	file.flush()
	file.close()
