"""
本机多人服务端权威原型测试。
"""

from src.game_session import NetworkGameSession
from src.models import ActionType, GameAction
from src.multiplayer_server import MultiplayerServer
from src.network_protocol import serialize_action


def _started_two_player_room():
    server = MultiplayerServer()
    created = server.create_room("玩家1", max_players=2, map_seed=123)
    room_id = created["room"]["room_id"]
    client1 = created["client_id"]
    joined = server.join_room(room_id, "玩家2")
    client2 = joined["client_id"]
    started = server.start_room(room_id)
    assert started["success"]
    return server, room_id, client1, client2


def test_multiplayer_server_starts_authoritative_room_and_views():
    server, room_id, client1, client2 = _started_two_player_room()
    room_state = server.get_room_state(room_id)
    engine = server.get_room_engine(room_id)

    assert room_state["started"]
    assert room_state["turn_mode"] == "simultaneous"
    assert engine is not None
    assert [seat["player_id"] for seat in room_state["seats"]] == ["player_0", "player_1"]

    view1 = server.get_player_view(room_id, client1)
    view2 = server.get_player_view(room_id, client2)
    assert view1["success"]
    assert view2["success"]
    assert view1["view"]["player_id"] == "player_0"
    assert view2["view"]["player_id"] == "player_1"
    assert view1["view"]["turn_status"]["mode"] == "simultaneous"


def test_multiplayer_server_rejects_spoofed_player_action():
    server, room_id, client1, client2 = _started_two_player_room()
    engine = server.get_room_engine(room_id)
    player2 = engine.player_system.players[1]

    response = server.submit_action(room_id, client1, serialize_action(GameAction(
        player_id=player2.id,
        action_type=ActionType.END_TURN,
        params={}
    )))

    assert not response["success"]
    assert response["result"]["message"] == "无权操作该玩家"
    assert player2.id not in engine.turn_system.ended_player_ids


def test_multiplayer_server_simultaneous_turn_flow():
    server, room_id, client1, client2 = _started_two_player_room()
    engine = server.get_room_engine(room_id)
    player1, player2 = engine.player_system.players

    first = server.submit_action(room_id, client1, serialize_action(GameAction(
        player_id=player1.id,
        action_type=ActionType.END_TURN,
        params={}
    )))
    assert first["success"]
    assert player1.id in engine.turn_system.ended_player_ids
    assert engine.turn_system.current_turn == 1
    assert first["room"]["recent_events"]
    assert first["room"]["recent_events"][-1]["event_type"] == "turn_ended"

    second = server.submit_action(room_id, client2, serialize_action(GameAction(
        player_id=player2.id,
        action_type=ActionType.END_TURN,
        params={}
    )))
    assert second["success"]
    assert engine.turn_system.current_turn == 2
    assert engine.turn_system.ended_player_ids == set()
    assert any(event["event_type"] == "turn_advanced" for event in second["result"]["events"])


def test_multiplayer_server_leave_and_reconnect_room():
    server, room_id, client1, client2 = _started_two_player_room()

    left = server.leave_room(room_id, client2)
    assert left["success"]
    assert not left["room"]["seats"][1]["connected"]
    assert left["room"]["recent_events"][-1]["event_type"] == "player_left"

    offline_action = server.submit_action(room_id, client2, serialize_action(GameAction(
        player_id="player_1",
        action_type=ActionType.END_TURN,
        params={}
    )))
    assert not offline_action["success"]
    assert "离线" in offline_action["result"]["message"]

    reconnected = server.reconnect_room(room_id, client2)
    assert reconnected["success"]
    assert reconnected["room"]["seats"][1]["connected"]
    assert reconnected["room"]["recent_events"][-1]["event_type"] == "player_reconnected"


def test_multiplayer_server_host_leave_closes_room():
    server, room_id, client1, client2 = _started_two_player_room()

    left = server.leave_room(room_id, client1)
    assert left["success"]
    assert left["room"]["closed"]
    assert left["room"]["close_reason"] == "房主已退出，房间关闭"
    assert all(not seat["connected"] for seat in left["room"]["seats"])
    assert left["room"]["recent_events"][-1]["event_type"] == "room_closed"

    action = server.submit_action(room_id, client2, serialize_action(GameAction(
        player_id="player_1",
        action_type=ActionType.END_TURN,
        params={}
    )))
    assert not action["success"]
    assert "房间关闭" in action["result"]["message"]

    reconnected = server.reconnect_room(room_id, client2)
    assert not reconnected["success"]
    assert reconnected["room"]["closed"]


def test_network_game_session_uses_server_authority():
    server = MultiplayerServer()
    created = server.create_room("玩家1", max_players=2, map_seed=123)
    room_id = created["room"]["room_id"]
    host_client = created["client_id"]
    guest_client = server.join_room(room_id, "玩家2")["client_id"]

    host_session = NetworkGameSession(server, room_id, host_client)
    guest_session = NetworkGameSession(server, room_id, guest_client)
    assert host_session.start_game(turn_mode="simultaneous")

    host_player = host_session.get_controlled_player()
    guest_player = guest_session.get_controlled_player()
    assert host_player.id == "player_0"
    assert guest_player.id == "player_1"
    assert host_session.can_player_act(host_player.id)
    assert guest_session.can_player_act(guest_player.id)

    result = guest_session.submit_action(GameAction(
        player_id=guest_player.id,
        action_type=ActionType.END_TURN,
        params={}
    ))
    assert result.success
    assert not guest_session.can_player_act(guest_player.id)
    assert host_session.get_player_view()["view"]["turn_status"]["mode"] == "simultaneous"
