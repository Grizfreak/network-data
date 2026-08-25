extends NetworkBenchmarkProvider
class_name ENetBenchmarkProvider

const PING_INTERVAL := 1.0

var _rtt := 0.0

var _bytes_sent := 0
var _bytes_received := 0

var _timer := 0.0

func _process(delta):
    if multiplayer.multiplayer_peer == null:
        return

    if multiplayer.multiplayer_peer.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
        return
    if multiplayer.is_server():
        return

    _timer += delta

    if _timer >= PING_INTERVAL:
        _timer = 0.0
        rpc_id(1, "_ping", Time.get_ticks_usec())


@rpc("any_peer", "reliable")
func _ping(timestamp):

    # Here you could also increase bytes sent

    rpc_id(
        multiplayer.get_remote_sender_id(),
        "_pong",
        timestamp
    )


@rpc("authority", "reliable")
func _pong(timestamp):

    _rtt = (Time.get_ticks_usec() - timestamp) / 1000.0

    # Here you could count received bytes


func get_rtt_ms():
    return _rtt


func get_bytes_sent():
    return _bytes_sent


func get_bytes_received():
    return _bytes_received