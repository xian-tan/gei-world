"""
HTTP + 轮询多人传输层测试。
"""
from threading import Thread

from src.http_multiplayer import HTTPMultiplayerClient, create_http_server
from src.models import ActionType, GameAction
from src.systems.turn_system import TurnSystem


def _start_test_http_server():
    http_server = create_http_server("127.0.0.1", 0)
    thread = Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    host, port = http_server.server_address
    return http_server, HTTPMultiplayerClient(f"http://{host}:{port}")


def test_http_multiplayer_room_lifecycle_and_views():
    http_server, client = _start_test_http_server()
    try:
        created = client.create_room("玩家1", turn_mode=TurnSystem.MODE_SIMULTANEOUS, map_seed=123)
        assert created["success"]
        room_id = created["room"]["room_id"]
        host_client_id = created["client_id"]

        joined = client.join_room(room_id, "玩家2")
        assert joined["success"]
        guest_client_id = joined["client_id"]

        state = client.get_room_state(room_id)
        assert state["success"]
        assert len(state["room"]["seats"]) == 2

        started = client.start_room(room_id, turn_mode=TurnSystem.MODE_SIMULTANEOUS)
        assert started["success"]
        assert started["room"]["started"]
        assert started["room"]["seats"][0]["player_id"] == "player_0"
        assert started["room"]["seats"][1]["player_id"] == "player_1"

        host_view = client.get_player_view(room_id, host_client_id)
        guest_view = client.get_player_view(room_id, guest_client_id)
        assert host_view["success"]
        assert guest_view["success"]
        assert host_view["view"]["player_id"] == "player_0"
        assert guest_view["view"]["player_id"] == "player_1"
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_http_multiplayer_action_authority_and_turn_advance():
    http_server, client = _start_test_http_server()
    try:
        created = client.create_room("玩家1", turn_mode=TurnSystem.MODE_SIMULTANEOUS, map_seed=123)
        room_id = created["room"]["room_id"]
        host_client_id = created["client_id"]
        guest_client_id = client.join_room(room_id, "玩家2")["client_id"]
        client.start_room(room_id, turn_mode=TurnSystem.MODE_SIMULTANEOUS)

        spoofed = client.submit_action(room_id, host_client_id, GameAction(
            player_id="player_1",
            action_type=ActionType.END_TURN,
            params={}
        ))
        assert not spoofed["success"]
        assert spoofed["result"]["message"] == "无权操作该玩家"

        first = client.submit_action(room_id, host_client_id, GameAction(
            player_id="player_0",
            action_type=ActionType.END_TURN,
            params={}
        ))
        assert first["success"]
        assert first["room"]["seats"][0]["ended_turn"]

        second = client.submit_action(room_id, guest_client_id, GameAction(
            player_id="player_1",
            action_type=ActionType.END_TURN,
            params={}
        ))
        assert second["success"]
        assert second["view"]["turn"] == 2
        assert any(event["event_type"] == "turn_advanced" for event in second["result"]["events"])
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_http_multiplayer_returns_errors_as_json():
    http_server, client = _start_test_http_server()
    try:
        missing = client.get_room_state("missing")
        assert not missing["success"]
        assert "房间不存在" in missing["message"]
    finally:
        http_server.shutdown()
        http_server.server_close()
