"""
HTTP 房间流程 UI 测试。
"""
from threading import Thread

import pygame

from src.game_session import HTTPNetworkSession
from src.http_multiplayer import create_http_server
from ui.client_controller import UIClient


def _start_http_server():
    http_server = create_http_server("127.0.0.1", 0)
    thread = Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    host, port = http_server.server_address
    return http_server, f"http://{host}:{port}"


def test_http_modal_form_inputs_drive_room_flow():
    http_server, base_url = _start_http_server()
    try:
        pygame.init()
        client = UIClient()
        client._show_http_multiplayer_modal()
        assert client.ui_system.has_active_modal()
        assert client.ui_system.set_modal_input_value("base_url", base_url)
        assert client.ui_system.set_modal_input_value("turn_mode", "simultaneous")
        created = client._create_http_room(
            base_url=client._get_http_form_values()["base_url"],
            turn_mode=client._get_http_form_values()["turn_mode"],
            host_name="玩家1"
        )
        assert created["success"]
        assert created["room"]["room_id"]
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_http_ui_create_join_and_reconnect_existing_room():
    http_server, base_url = _start_http_server()
    try:
        pygame.init()
        host_client = UIClient()
        created = host_client._create_http_room(base_url=base_url, turn_mode="simultaneous", map_seed=123)
        assert created["success"]
        room_id = created["room"]["room_id"]
        host_client_id = created["client_id"]
        assert not host_client.game_started

        guest_client = UIClient()
        assert guest_client._join_http_multiplayer_room(
            base_url=base_url,
            room_id=room_id,
            player_name="玩家2",
            turn_mode="simultaneous"
        )
        assert guest_client.game_started
        assert isinstance(guest_client.session, HTTPNetworkSession)
        assert guest_client._get_controlled_player().id == "player_1"

        assert host_client._connect_http_multiplayer_existing(
            base_url=base_url,
            room_id=room_id,
            client_id=host_client_id
        )
        assert host_client.game_started
        assert isinstance(host_client.session, HTTPNetworkSession)
        assert host_client._get_controlled_player().id == "player_0"
        assert host_client._get_game_state()["multiplayer_status"]["room_id"] == room_id
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_http_ui_join_requires_room_id():
    pygame.init()
    client = UIClient()
    assert not client._join_http_multiplayer_room(base_url="http://127.0.0.1:9", room_id=None)
    assert any("缺少房间号" in message for message in client.ui_system.messages)


def test_http_ui_connect_requires_room_and_client_id():
    pygame.init()
    client = UIClient()
    assert not client._connect_http_multiplayer_existing(base_url="http://127.0.0.1:9")
    assert any("缺少房间号或客户端ID" in message for message in client.ui_system.messages)


def test_http_ui_reports_room_closed_after_host_leaves():
    http_server, base_url = _start_http_server()
    try:
        pygame.init()
        host_client = UIClient()
        created = host_client._create_http_room(base_url=base_url, turn_mode="simultaneous", map_seed=123)
        room_id = created["room"]["room_id"]
        host_client_id = created["client_id"]

        guest_client = UIClient()
        assert guest_client._join_http_multiplayer_room(
            base_url=base_url,
            room_id=room_id,
            player_name="玩家2",
            turn_mode="simultaneous"
        )
        assert host_client._connect_http_multiplayer_existing(
            base_url=base_url,
            room_id=room_id,
            client_id=host_client_id
        )

        host_client.session.leave_room()
        state = guest_client._get_game_state()
        assert state["multiplayer_status"]["closed"]
        assert not state["can_act"]
        assert any("房主已退出，房间关闭" in message for message in guest_client.ui_system.messages)
    finally:
        http_server.shutdown()
        http_server.server_close()
