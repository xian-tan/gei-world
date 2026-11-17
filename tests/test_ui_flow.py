"""
主菜单、新游戏设置、热座、快捷操作、多人大厅与 HUD 测试。
"""
from threading import Thread

import pygame

from src.http_multiplayer import create_http_server
from src.models import ActionType, GameAction, HexCoord, UnitType
from tests.helpers import place_unit
from ui.client_controller import UIClient


def _client():
    pygame.init()
    return UIClient()


def _click(client, button):
    client._handle_tile_click(button.rect.center)


def test_main_menu_buttons_open_new_game_form_and_start():
    client = _client()
    client._render()
    labels = [button.text for button in client.ui_system.menu_buttons]
    assert labels[:3] == ["开始新游戏", "多人联机", "读取存档"]
    assert "本机双客户端（调试）" not in labels
    _click(client, client.ui_system.menu_buttons[0])
    assert client.ui_system.active_modal["title"] == "新游戏"

    ui = client.ui_system
    ui.set_modal_input_value("players", 3)
    ui.set_modal_input_value("humans", 1)
    ui.set_modal_input_value("map_size", "small")
    ui.set_modal_input_value("map_type", "pangaea")
    ui.set_modal_input_value("difficulty", "hard")
    ui.set_modal_input_value("seed", "42")
    assert client._start_from_new_game_form()
    engine = client.game_engine
    assert len(engine.player_system.players) == 3
    assert engine.map_system.radius == 8
    assert engine.map_system.generator_type == "pangaea"
    assert sorted(client.ai_manager.ai_players) == ["player_1", "player_2"]
    assert client.ai_manager.ai_players["player_1"].difficulty == "hard"
    assert not client.ui_system.has_active_modal()


def test_choice_inputs_cycle_with_keys_and_clicks():
    client = _client()
    client._show_new_game_modal()
    ui = client.ui_system
    ui.active_input_index = 0
    ui.handle_key_press(pygame.K_RIGHT)
    assert ui.get_modal_input_values()["players"] == 3
    ui.handle_key_press(pygame.K_LEFT)
    ui.handle_key_press(pygame.K_LEFT)
    assert ui.get_modal_input_values()["players"] == 4
    ui.handle_text_input("x")
    assert ui.get_modal_input_values()["players"] == 4
    client._render()
    rect = ui.modal_inputs[3]["rect"]
    before = ui.get_modal_input_values()["turn_mode"]
    ui.handle_click((rect.right - 5, rect.centery))
    assert ui.get_modal_input_values()["turn_mode"] != before


def test_restart_reuses_last_settings():
    client = _client()
    assert client.start_game(["玩家1", "电脑1", "电脑2"], 5, map_size="small", ai_difficulty="easy")
    client.game_engine.game_over = True
    client._handle_key_press(pygame.K_r, True)
    assert len(client.game_engine.player_system.players) == 3
    assert client.game_engine.map_system.radius == 8
    assert not client.game_engine.game_over


def test_simultaneous_hotseat_switches_between_humans():
    client = _client()
    assert client.start_game(["玩家1", "玩家2", "电脑1"], 9, turn_mode="simultaneous", human_count=2)
    p1, p2, _ai = client.game_engine.player_system.players
    assert client._get_controlled_player() == p1
    client._handle_end_turn(force=True)
    assert client._get_controlled_player() == p2
    assert client.game_engine.turn_system.current_turn == 1
    client._handle_end_turn(force=True)
    assert client.game_engine.turn_system.current_turn == 2
    assert client._get_controlled_player() == p1


def test_sequential_hotseat_follows_current_player():
    client = _client()
    assert client.start_game(["玩家1", "玩家2"], 9, turn_mode="sequential", human_count=2)
    p1, p2 = client.game_engine.player_system.players
    client._handle_end_turn(force=True)
    assert client._get_controlled_player() == p2
    assert client.ui_system.banner and "玩家2" in client.ui_system.banner[0]


def test_next_unit_hotkey_and_enter_end_turn():
    client = _client()
    assert client.start_game(["玩家1", "电脑1"], 9)
    player = client._get_controlled_player()
    client._handle_key_press(pygame.K_n, True)
    assert client.input_system.get_selected_unit_id() == player.units[0].id
    turn = client.game_engine.turn_system.current_turn
    client._handle_key_press(pygame.K_RETURN, True)
    assert client.ui_system.has_active_modal()
    client._handle_end_turn(force=True)
    assert client.game_engine.turn_system.current_turn == turn + 1


def test_combat_spawns_floating_text_when_visible():
    client = _client()
    assert client.start_game(["玩家1", "电脑1"], 9)
    engine = client.game_engine
    me, enemy = engine.player_system.players
    base = me.units[0].position
    target = next(n for n in base.neighbors() if n in engine.map_tiles)
    for coord in (base, target):
        engine.map_tiles[coord].terrain_type = engine.map_tiles[base].terrain_type
    soldier = place_unit(engine, me, UnitType.SOLDIER, base, quantity=3)
    place_unit(engine, enemy, UnitType.SOLDIER, target, quantity=1)
    engine._update_all_visions()
    client._execute_action_and_notify(GameAction(me.id, ActionType.MOVE_UNIT, {
        "unit_id": soldier.id, "target": [target.q, target.r], "move_quantity": 3}))
    assert any(item["text"] == "战斗！" for item in client.render_system.floating_texts)


def test_hud_renders_and_blocks_clicks_on_panels_and_resizes():
    client = _client()
    assert client.start_game(["玩家1", "电脑1"], 9)
    client._render()
    top_bar = client.ui_system.top_bar_rect()
    assert client.ui_system.is_over_ui(top_bar.center)
    labels = [button.text for button in client.ui_system.buttons]
    assert "结束回合" in labels and "菜单" in labels
    client._handle_resize(1400, 900)
    client._render()
    assert client.ui_system.side_panel_rect().right == 1400 - 10
    for index in range(30):
        client._notify(f"很长的消息 {index} " + "测试" * 40)
    client.ui_system.scroll_log(5)
    client._render()
    assert client.ui_system.log_scroll == 5


def test_help_overlay_toggles_with_f1():
    client = _client()
    assert client.start_game(["玩家1", "电脑1"], 9)
    client._handle_key_press(pygame.K_F1, True)
    assert client.ui_system.show_help
    client._render()
    client._handle_key_press(pygame.K_ESCAPE, True)
    assert not client.ui_system.show_help


def _http_server():
    server = create_http_server("127.0.0.1", 0)
    Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def test_host_lobby_auto_enters_when_guest_joins_and_reconnect_uses_identity():
    http_server, base_url = _http_server()
    try:
        host = _client()
        created = host._create_http_room(base_url=base_url, turn_mode="sequential", host_name="房主")
        room_id = created["room"]["room_id"]
        assert not host._poll_pending_host_room(force=True)

        guest = _client()
        assert guest._join_http_multiplayer_room(base_url=base_url, room_id=room_id.lower(), player_name="挑战者")
        assert guest.game_engine.turn_system.mode == "sequential"

        assert host._poll_pending_host_room(force=True)
        assert host.game_started
        assert host._get_controlled_player().id == "player_0"

        assert guest._leave_multiplayer_room()
        assert guest._connect_http_multiplayer_existing(base_url=base_url, room_id=room_id, player_name="挑战者")
        assert guest._get_controlled_player().id == "player_1"
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_password_protected_room():
    http_server, base_url = _http_server()
    try:
        host = _client()
        created = host._create_http_room(base_url=base_url, host_name="房主", password="secret")
        room_id = created["room"]["room_id"]
        guest = _client()
        assert not guest._join_http_multiplayer_room(base_url=base_url, room_id=room_id, player_name="甲")
        assert any("密码" in message for message in guest.ui_system.messages)
        assert guest._join_http_multiplayer_room(base_url=base_url, room_id=room_id, player_name="甲",
                                                 password="secret")
    finally:
        http_server.shutdown()
        http_server.server_close()


def test_dev_mode_shows_debug_entries(monkeypatch):
    monkeypatch.setenv("GEI_WORLD_DEV", "1")
    client = _client()
    client._render()
    assert "本机双客户端（调试）" in [button.text for button in client.ui_system.menu_buttons]
    client._show_http_multiplayer_modal()
    assert any(action["text"] == "调试双席位房" for action in client.ui_system.active_modal["actions"])


def test_minimap_click_moves_camera():
    client = _client()
    assert client.start_game(["玩家1", "电脑1"], 9)
    client._render()
    rect = client.render_system.minimap_rect
    before = client.camera_system.get_position()
    client._handle_tile_click((rect.left + 15, rect.top + 15))
    assert client.camera_system.get_position() != before
    assert HexCoord(0, 0) in client.game_engine.map_tiles
