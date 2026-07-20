extends Node

var address = "127.0.0.1"
var port = 9999

func _ready() -> void:
    if OS.get_name() == "Android":
        # take from the base loader
        if BaseLoader.resource.multiplayer_mode == "server":
            host()
        elif BaseLoader.resource.multiplayer_mode == "client":
            var address_port = BaseLoader.resource.server_address.split(":")
            print(BaseLoader.resource)
            if address_port.size() == 2:
                address = address_port[0]
                port = int(address_port[1])
            join()
    else:
        # check if args contains host or client
        if OS.get_cmdline_args().has("server"):
            host()
        elif OS.get_cmdline_args().has("client"):
            # check for next arg to get the address and port
            var args = OS.get_cmdline_args()
            for i in range(args.size()):
                if args[i] == "client" and i + 1 < args.size():
                    var address_port = args[i + 1].split(":")
                    if address_port.size() == 2:
                        address = address_port[0]
                        port = int(address_port[1])
                    else:
                        print("Invalid address:port format. Using default values.")
            join()
        else:
            host()


func host():
    var peer = ENetMultiplayerPeer.new()
    peer.create_server(port, 32)

    multiplayer.multiplayer_peer = peer

    multiplayer.peer_connected.connect(player_connected)
    multiplayer.peer_disconnected.connect(player_disconnected)

    print("Server started on port %d" % port)

func player_connected(id):
    print("Player connected:", id)
    if multiplayer.is_server():
        print("Server is running, starting to log network events.")
        WiresharkManager.start_tracking("udp port %s or tcp port %s" % [port, port], "godot_server_capture");
    await get_tree().process_frame
    load_game.rpc()


func player_disconnected(id):
    print("Player disconnected with ID: %d" % id)


func join():
    var peer = ENetMultiplayerPeer.new()
    peer.create_client(address, port)

    multiplayer.multiplayer_peer = peer

    multiplayer.connected_to_server.connect(connected_to_server)
    multiplayer.connection_failed.connect(connection_failed)

func connected_to_server():
    print("Connected to server at %s:%d" % [address, port])
    if OS.get_name() == "Windows":
        print("Client is running, running logic on client")
        WiresharkManager.start_tracking("udp port %s or tcp port %s" % [port, port], "godot_client_capture");

func connection_failed():
    print("Failed to connect to server at %s:%d" % [address, port])

@rpc("authority", "call_local", "reliable")
func load_game():
    get_tree().change_scene_to_file("res://scenes/benchmark.tscn")