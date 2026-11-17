"""
多人产品化：令牌私有、迷雾安全的房间事件、心跳超时、离线自动跳过、房主强制跳过、房间清理、快照恢复。
"""
import tempfile
from threading import Thread

import pygame
import pytest

from src.http_multiplayer import HTTPMultiplayerClient, create_http_server
from src.models import ActionType, GameAction
from src.multiplayer_server import MultiplayerServer
from src.network_protocol import serialize_action


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _room(turn_mode="simultaneous", **kwargs):
    clock = FakeClock()
    server = MultiplayerServer(clock=clock, heartbeat_timeout=60, closed_room_ttl=100, idle_room_ttl=300, **kwargs)
    created = server.create_room("房主", turn_mode=turn_mode, map_seed=7)
    room_id = created["room"]["room_id"]
    guest = server.join_room(room_id, "挑战者")["client_id"]
    assert server.start_room(room_id)["success"]
    return server, clock, room_id, created["client_id"], guest


def _end(server, room_id, client_id, player_id):
    return server.submit_action(room_id, client_id, serialize_action(GameAction(player_id, ActionType.END_TURN, {})))


def test_room_codes_are_short_and_tokens_never_public():
    server, _clock, room_id, host, guest = _room()
    assert len(room_id) == 6 and room_id.isalnum() and room_id.isupper()
    assert len(host) >= 16 and host != guest
    state = server.get_room_state(room_id.lower())
    assert all("client_id" not in seat for seat in state["seats"])
    assert [seat["is_you"] for seat in server.get_room_state(room_id, guest)["seats"]] == [False, True]
    with pytest.raises(KeyError):
        server.get_player_view(room_id, "client_1")


def test_public_room_events_do_not_leak_unit_positions():
    server, _clock, room_id, host, _guest = _room()
    engine = server.get_room_engine(room_id)
    settler = engine.player_system.players[0].units[0]
    server.submit_action(room_id, host, serialize_action(GameAction("player_0", ActionType.BUILD_CITY, {"unit_id": settler.id})))
    events = server.get_room_state(room_id)["recent_events"]
    assert all(event["event_type"] not in {"city_built", "unit_moved"} for event in events)
    assert all("data" not in event for event in events)


def test_heartbeat_timeout_marks_offline_and_auto_skips_simultaneous_turn():
    server, clock, room_id, host, guest = _room()
    assert _end(server, room_id, host, "player_0")["success"]
    clock.advance(30)
    server.get_player_view(room_id, host)
    clock.advance(40)
    state = server.get_room_state(room_id)
    assert not state["seats"][1]["connected"]
    assert state["turn"] == 2
    types = [event["event_type"] for event in state["recent_events"]]
    assert "player_timeout" in types and "turn_skipped" in types

    view = server.get_player_view(room_id, guest)
    assert view["success"]
    assert server.get_room_state(room_id)["seats"][1]["connected"]


def test_sequential_offline_player_is_skipped_so_game_continues():
    server, _clock, room_id, host, guest = _room(turn_mode="sequential")
    server.leave_room(room_id, guest)
    assert _end(server, room_id, host, "player_0")["success"]
    engine = server.get_room_engine(room_id)
    assert engine.turn_system.get_current_player().id == "player_0"
    assert engine.turn_system.current_turn == 2


def test_force_skip_requires_host_and_offline_player():
    server, _clock, room_id, host, guest = _room()
    server.get_room_engine(room_id)
    for room in server.rooms.values():
        room.auto_skip_offline = False
    assert not server.force_skip(room_id, guest)["success"]
    assert not server.force_skip(room_id, host)["success"]
    server.leave_room(room_id, guest)
    result = server.force_skip(room_id, host)
    assert result["success"] and result["skipped"] == ["挑战者"]


def test_closed_and_idle_rooms_are_cleaned_up():
    server, clock, room_id, host, _guest = _room()
    server.leave_room(room_id, host)
    clock.advance(150)
    with pytest.raises(KeyError):
        server.get_room_state(room_id)

    waiting = server.create_room("独自", map_seed=1)["room"]["room_id"]
    clock.advance(400)
    state = server.get_room_state(waiting)
    assert state["closed"] and "已关闭" in state["close_reason"]
    clock.advance(150)
    with pytest.raises(KeyError):
        server.get_room_state(waiting)


def test_room_snapshot_save_and_restore_with_seat_claiming():
    with tempfile.TemporaryDirectory() as tmp_dir:
        server, _clock, room_id, host, guest = _room(save_directory=tmp_dir)
        assert not server.save_room(room_id, guest)["success"]
        saved = server.save_room(room_id, host)
        assert saved["success"] and saved["save_code"] == room_id

        restored = server.restore_room(room_id, "房主", password="pw")
        assert restored["success"]
        new_room = restored["room"]["room_id"]
        assert new_room != room_id and restored["room"]["started"]
        assert server.get_player_view(new_room, restored["client_id"])["view"]["player_id"] == "player_0"

        assert not server.join_room(new_room, "挑战者")["success"]
        assert not server.join_room(new_room, "路人", password="pw")["success"]
        claimed = server.join_room(new_room, "挑战者", password="pw")
        assert claimed["success"]
        assert server.get_player_view(new_room, claimed["client_id"])["view"]["player_id"] == "player_1"
        assert not server.restore_room(room_id, "陌生人")["success"]


def test_http_save_restore_and_heartbeat_endpoints():
    with tempfile.TemporaryDirectory() as tmp_dir:
        http_server = create_http_server("127.0.0.1", 0, MultiplayerServer(save_directory=tmp_dir))
        Thread(target=http_server.serve_forever, daemon=True).start()
        host, port = http_server.server_address
        client = HTTPMultiplayerClient(f"http://{host}:{port}")
        try:
            assert client._request("GET", "/health")["success"]
            created = client.create_room("房主", map_seed=3)
            room_id, host_id = created["room"]["room_id"], created["client_id"]
            guest_id = client.join_room(room_id, "挑战者")["client_id"]
            assert client.start_room(room_id)["success"]
            assert client.heartbeat(room_id, guest_id)["room"]["seats"][1]["is_you"]
            save_code = client.save_room(room_id, host_id)["save_code"]
            restored = client.restore_room(save_code, "房主")
            assert restored["success"] and restored["room"]["started"]
        finally:
            http_server.shutdown()
            http_server.server_close()


def test_ui_host_can_save_room_and_force_skip():
    from ui.client_controller import UIClient
    pygame.init()
    client = UIClient()
    assert client._start_local_multiplayer("simultaneous", map_seed=5)
    with tempfile.TemporaryDirectory() as tmp_dir:
        client.multiplayer_server.save_directory = tmp_dir
        client._handle_save_game()
        assert any("恢复码" in message for message in client.ui_system.messages)
    client._handle_load_game()
    assert any("不能读取本地存档" in message for message in client.ui_system.messages)
    room = next(iter(client.multiplayer_server.rooms.values()))
    room.auto_skip_offline = False
    room.seats[1].connected = False
    room.seats[1].left_explicitly = True
    client._handle_key_press(pygame.K_f, True)
    assert any("已跳过离线玩家" in message for message in client.ui_system.messages)
