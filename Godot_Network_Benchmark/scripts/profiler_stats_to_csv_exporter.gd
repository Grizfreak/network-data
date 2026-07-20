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

@export var network_provider : NetworkBenchmarkProvider
var bucket_rtt_sum := 0.0
var bucket_rtt_samples := 0

var bucket_bytes_sent_delta := 0
var bucket_bytes_received_delta := 0

var last_bytes_sent := 0
var last_bytes_received := 0

var network_baseline_initialized := false

var filename = "";


func _ready():
	var timestamp = Time.get_datetime_string_from_system()
	timestamp = timestamp.replace(":", "-")  # Replace colons with hyphens for filename compatibility
	if OS.get_name() == "Android":
		filename = "/storage/emulated/0/Android/data/com.IMT_Atlantique.godot_network_benchmark/files/%s_godot_profiler_stats_%s.csv" % [filename, timestamp]
	else:
		filename = "user://%s_godot_profiler_stats_%s.csv" % [filename, timestamp]
	file = FileAccess.open(filename, FileAccess.WRITE)
	FileAccess.get_open_error()

	file.store_line(
		"Time,Frame,FPS,FrameTimeMs,ProcessTimeMs,PhysicsTimeMs," +
		"DrawCalls,Objects,Primitives,TextureMemory,VideoMemory,StaticMemory," +
		"RTTms,UploadBytesPerSec,DownloadBytesPerSec"
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

	if network_provider:

		bucket_rtt_sum += network_provider.get_rtt_ms()
		bucket_rtt_samples += 1

		var current_sent = network_provider.get_bytes_sent()
		var current_received = network_provider.get_bytes_received()

		if !network_baseline_initialized:

			last_bytes_sent = current_sent
			last_bytes_received = current_received

			network_baseline_initialized = true

		else:

			bucket_bytes_sent_delta += current_sent - last_bytes_sent
			bucket_bytes_received_delta += current_received - last_bytes_received

			last_bytes_sent = current_sent
			last_bytes_received = current_received

	if bucket_time >= BUCKET_DURATION:
		write_bucket()
		reset_bucket()

	var now = Time.get_ticks_msec() / 1000.0

	if now - last_flush >= FLUSH_INTERVAL:
		last_flush = now
		file.flush()


func write_bucket():

	var avg_rtt := 0.0

	if bucket_rtt_samples > 0:
		avg_rtt = bucket_rtt_sum / bucket_rtt_samples

	var upload_rate := 0.0
	var download_rate := 0.0

	if bucket_time > 0.0:

		upload_rate = bucket_bytes_sent_delta / bucket_time
		download_rate = bucket_bytes_received_delta / bucket_time

	var n = max(bucket_frames, 1)

	var row = "%0.3f,%d,%0.2f,%0.3f,%0.3f,%0.3f,%d,%d,%d,%d,%d,%d,%0.2f,%0.0f,%0.0f" % [

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

		static_memory_sum / n,

		avg_rtt,

		upload_rate,

		download_rate
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

	bucket_rtt_sum = 0.0
	bucket_rtt_samples = 0

	bucket_bytes_sent_delta = 0
	bucket_bytes_received_delta = 0


func _exit_tree():

	if bucket_frames > 0:
		write_bucket()

	file.flush()
	file.close()
