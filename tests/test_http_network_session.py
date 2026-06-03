"""
HTTPNetworkSession 测试。
"""
from threading import Thread

from src.game_session import HTTPNetworkSession
from src.http_multiplayer import HTTPMultiplayerClient, create_http_server
from src.models import ActionType, GameAction
from src.systems.turn_system import TurnSystem


def _start_http_sessions():
    http_server = create_http_server("127.0.0.1", 0)
    thread = Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    host, port = http_server.server_address
    client = HTTPMultiplayerClient(f"http://{host}:{port}")
    created = client.create_room("玩家1", turn_mode=TurnSystem.MODE_SIMULTANEOUS, map_seed=123)
    room_id = created["room"]["room_id"]
    host_client_id = created["client_id"]
    guest_client_id = client.join_room(room_id, "玩家2")["client_id"]
    host_session = HTTPNetworkSession(client, room_id, host_client_id)
    guest_session = HTTPNetworkSession(client, room_id, guest_client_id)
    assert host_session.start_game(turn_mode=TurnSystem.MODE_SIMULTANEOUS)
    return http_server, host_session, guest_session


def test_http_network_session_polls_view_and_turn_status():
    http_server, host_session, guest_session = _start_http_sessions()
    try:
        host_player = host_session.get_controlled_player()
        guest_player = guest_session.get_controlled_player()
        assert host_player.id == "player_0"
        assert guest_player.id == "player_1"
        assert host_session.get_turn_status()["mode"] == "simultaneous"
        assert host_session.can_player_act(host_player.id)
        assert guest_session.can_player_act(guest_player.id)
        assert host_session.get_visible_tiles(host_player.id)
        assert host_session.get_explored_tiles(host_player.id)
        mirror = host_session.engine
        assert mirror.game_started
        assert mirror.map_tiles
        assert mirror.player_system.get_player_by_id(host_player.id)
        assert mirror.turn_system.mode == "simultaneous"
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_http_network_session_leave_and_reconnect():
    http_server, host_session, guest_session = _start_http_sessions()
    try:
        left = host_session.leave_room()
        assert left["success"]
        assert not left["room"]["seats"][0]["connected"]
        reconnected = host_session.reconnect_room()
        assert reconnected["success"]
        assert reconnected["room"]["seats"][0]["connected"]
        assert host_session.get_player_view()["success"]
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_http_network_session_submits_actions_and_updates_cache():
    http_server, host_session, guest_session = _start_http_sessions()
    try:
        host_player = host_session.get_controlled_player()
        guest_player = guest_session.get_controlled_player()

        spoofed = host_session.submit_action(GameAction(
            player_id=guest_player.id,
            action_type=ActionType.END_TURN,
            params={}
        ))
        assert not spoofed.success
        assert spoofed.message == "无权操作该玩家"

        host_result = host_session.submit_action(GameAction(
            player_id=host_player.id,
            action_type=ActionType.END_TURN,
            params={}
        ))
        assert host_result.success
        assert not host_session.can_player_act(host_player.id)

        guest_result = guest_session.submit_action(GameAction(
            player_id=guest_player.id,
            action_type=ActionType.END_TURN,
            params={}
        ))
        assert guest_result.success
        assert guest_session.get_player_view()["view"]["turn"] == 2
    finally:
        http_server.shutdown()
        http_server.server_close()
