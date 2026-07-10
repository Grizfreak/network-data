extends Node

@export var original_resource: base_resource = preload("res://resources/base.tres")
#@export var original_stats: ProfilerStats

var resource: base_resource
#var resource_stats: ProfilerStats

func _ready():

	resource = original_resource.duplicate(true)
	#resource_stats = original_stats.duplicate(true)
	if OS.get_name() == "Android":
		OS.request_permission("android.permission.READ_EXTERNAL_STORAGE")
		# Create the conf_resources directory if it doesn't exist
		var userDir = "/storage/emulated/0/Android/data/com.example.godot_benchmark/files"
		var confResourcesDir = userDir.path_join("conf_resources")
		
		# Ensure the directory exists using proper Godot API
		var dir = DirAccess.open("user://");
		if not dir.dir_exists("conf_resources"):
			# Directory doesn't exist, create it recursively
			dir.make_dir("conf_resources")
		else:
			# Directory exists, continue
			print("Directory already exists: ", confResourcesDir)
		
		# Load configuration from JSON file using proper path joining
		print("user:// path: ", userDir)
	
		var path = confResourcesDir.path_join("Base.json")
		print("Looking for: ", path)
		print("Exists: ", FileAccess.file_exists(path))
		print(ProjectSettings.get_setting("application/config/name"))
		print(OS.get_user_data_dir())
		if FileAccess.file_exists(path):
			resource.load_from_json(path)
		else:
			print("Using default resource.")
	elif OS.get_name() == "Windows":
		# check for args
		var args = OS.get_cmdline_args()
		if args.size() > 0 and args.find("--conf-file") != -1:
			var index = args.find("--conf-file") + 1
			if index < args.size():
				var path = args[index]
				if FileAccess.file_exists(path):
					resource.load_from_json(path)
				else:
					print("Using default resource.")
		else:
			print("Using default resource.")

	

	#var profiler_path = "user://conf_resources/ProfilerStats.json"

	#if FileAccess.file_exists(profiler_path):
		#resource_stats.load_from_json(profiler_path)
