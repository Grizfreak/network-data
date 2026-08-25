extends Node
var capture_file_path: String = ""

var is_quest := false
var quest_ip := ""

func _ready():
    _parse_command_line()


func _parse_command_line():
    var args = OS.get_cmdline_args()

    for i in args.size():
        if args[i] == "--quest":
            is_quest = true
            print("Running for Quest benchmark tracking.")

        if args[i] == "--quest-ip" and i + 1 < args.size():
            quest_ip = args[i + 1]
            print("Quest IP:", quest_ip)


func start_tracking(filter: String, filename: String):
    var timestamp := Time.get_datetime_string_from_system()
    timestamp = timestamp.replace(":", "").replace("-", "").replace("T", "_")

    var script_path: String
    if OS.has_feature("editor"):
        script_path = ProjectSettings.globalize_path("res://capture_wireshark.ps1")
    else:
        script_path = OS.get_executable_path().get_base_dir().path_join("capture_wireshark.ps1")
    
    if is_quest:
        capture_file_path = "%s/%s_quest_capture_%s.pcap" % [
            OS.get_user_data_dir(),
            filename,
            timestamp
        ]
        
        var output := []
        

        OS.execute(
            "powershell",
            [
                "-ExecutionPolicy", "Bypass",
                "-File", script_path,
                "start",
                "-OutputFile", capture_file_path,
                "-Filter", "host %s and udp" % quest_ip,
                "-Interface", "Wi-Fi 3"
            ],
            output
        )

        print(output)

        print("Started tshark for Quest.")

    else:
        capture_file_path = "%s/%s_%s.pcap" % [
            OS.get_user_data_dir(),
            filename,
            timestamp
        ]

        var output := []

        # debug print
        print("-ExecutionPolicy Bypass -File %s start -OutputFile %s -Filter %s -Interface Wi-Fi" % [
            script_path,
            capture_file_path,
            filter
        ])

        OS.execute(
            "powershell",
            [
                "-ExecutionPolicy", "Bypass",
                "-File", script_path,
                "start",
                "-OutputFile", capture_file_path,
                "-Filter", filter,
                "-Interface", "Wi-Fi"
            ],
            output
        )

        print(output)

        print("Started tshark with filter:", filter)


func stop_tracking():
    var output := []

    var script_path: String
    if OS.has_feature("editor"):
        script_path = ProjectSettings.globalize_path("res://capture_wireshark.ps1")
    else:
        script_path = OS.get_executable_path().get_base_dir().path_join("capture_wireshark.ps1")

    OS.execute(
        "powershell",
        [
            "-ExecutionPolicy", "Bypass",
            "-File", script_path,
            "stop"
        ],
        output
    )
    print(output)

func _exit_tree():
    stop_tracking()