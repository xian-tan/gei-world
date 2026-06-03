#!/usr/bin/env python3
"""
测试UI修复功能
"""
import sys
import os
import tempfile
import pygame

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

def test_ui_fixes():
    """测试UI修复"""
    print("=== UI修复测试 ===")
    
    try:
        pygame.init()
        # 测试导入
        from ui.client_controller import UIClient
        from ui.font_manager import get_font_manager
        from ui.systems.input_system import InputMode
        from ui.systems.ui_system import UISystem
        from src.models import HexCoord, UnitType, Player, ActionEvent, ActionResult, Tile, TerrainType, Unit, City
        from src.systems.save_system import GameSaveSystem
        from src.config import ECONOMY_CONFIG
        
        print("✓ 所有模块导入成功")
        
        # 测试字体管理器
        font_manager = get_font_manager()
        assert font_manager.chinese_font_path and os.path.exists(font_manager.chinese_font_path)
        chinese_metrics = font_manager.get_font('medium').metrics("测试中文")
        assert all(metric is not None for metric in chinese_metrics)
        test_text = font_manager.render_text("测试中文", 'medium', (255, 255, 255))
        assert test_text.get_width() > 0 and test_text.get_height() > 0
        print("✓ 中文字体渲染成功")
        
        # 测试六边形坐标
        coord1 = HexCoord(0, 0)
        coord2 = HexCoord(1, 0)
        distance = coord1.distance_to(coord2)
        print(f"✓ 六边形距离计算: {distance}")
        
        # 测试游戏结束面板和移动范围高亮渲染
        ui_system = UISystem(800, 600)
        surface = pygame.Surface((800, 600))
        winner = Player(id="player_1", name="测试玩家", gold=100)
        selected_coord = HexCoord(0, 0)
        selected_tile = Tile(coord=selected_coord, terrain_type=TerrainType.LAND, owner=winner)
        selected_unit = Unit(
            id="unit_1",
            owner=winner,
            position=selected_coord,
            unit_type=UnitType.SOLDIER,
            movement_points=1,
            max_movement_points=2,
            vision_range=2
        )
        selected_city = City(
            id="city_1",
            owner=winner,
            center_tile=selected_coord,
            territory_tiles={selected_coord}
        )
        ui_system.render(surface, {
            'current_player': winner,
            'turn_number': 1,
            'game_over': True,
            'winner': winner,
            'selected_coord': selected_coord,
            'selected_tile': selected_tile,
            'selected_unit': selected_unit,
            'selected_city': selected_city
        })
        print("✓ 游戏结束面板和选择详情渲染成功")
        
        # 测试可达地块高亮状态
        from ui.systems.render_system import RenderSystem
        render_system = RenderSystem()
        reachable = {HexCoord(1, 0), HexCoord(0, 1)}
        render_system.set_reachable_tiles(reachable)
        assert render_system.reachable_tiles == reachable
        render_system.clear_reachable_tiles()
        assert not render_system.reachable_tiles
        print("✓ 可达地块高亮状态正常")
        
        # 测试战斗详情消息格式化
        client = UIClient()
        client._notify_action_result(ActionResult(
            success=True,
            message="单位移动成功",
            events=[
                ActionEvent("unit_moved", "单位移动成功", {"from_terrain": "land", "to_terrain": "ocean"}),
                ActionEvent("combat_resolved", data={"destroyed_unit_ids": ["u1", "u2"]}),
                ActionEvent("unit_destroyed", "单位被消灭", {"unit_id": "u1"})
            ]
        ))
        assert "战斗结束：消灭 2 个单位" in client.ui_system.messages
        assert "单位移动成功" not in client.ui_system.messages[-2:]
        print("✓ 战斗详情消息格式化成功")
        
        client.ui_system.messages.clear()
        client._notify_action_result(ActionResult(
            success=True,
            message="单位移动成功",
            events=[ActionEvent("unit_moved", "单位移动成功", {"from_terrain": "land", "to_terrain": "ocean"})]
        ))
        assert "单位下海，移动力已耗尽" in client.ui_system.messages
        print("✓ 海陆移动消息格式化成功")
        
        client.ui_system.messages.clear()
        client._notify_action_result(ActionResult(False, "生产失败：金币不足，需要 1，当前 0"))
        assert "金币不足" in client.ui_system.messages[-1]
        print("✓ 失败原因消息展示成功")
        
        client.ui_system.messages.clear()
        assert client.start_game(["玩家1", "AI玩家"], 123)
        assert any("新手提示" in message for message in client.ui_system.messages)
        player = client.game_engine.get_current_player()
        settler = player.units[0]
        settler_tile = client.game_engine.map_tiles[settler.position]
        client.ui_system.messages.clear()
        client._handle_normal_click(settler_tile, player)
        assert any("建城" in message and "右键移动" in message for message in client.ui_system.messages)
        
        client.game_engine.unit_system.remove_unit(settler, client.game_engine.map_tiles)
        city = client.game_engine.city_system.create_city(player, settler.position, client.game_engine.map_tiles)
        player.cities.append(city)
        assert client._get_game_state()['current_income'] == len(city.territory_tiles) * ECONOMY_CONFIG["territory_income"]
        client.ui_system.messages.clear()
        client._handle_normal_click(client.game_engine.map_tiles[city.center_tile], player)
        assert any("生产" in message and "金币" in message for message in client.ui_system.messages)
        print("✓ 新手提示和选择建议成功")
        
        selected_city.owner.gold = 0
        ui_system.show_city_panel_for(selected_city)
        ui_system.render(surface, {
            'current_player': winner,
            'turn_number': 1,
            'game_over': False,
            'winner': None,
            'selected_coord': selected_coord,
            'selected_tile': selected_tile,
            'selected_unit': selected_unit,
            'selected_city': selected_city
        })
        disabled_button = ui_system._temp_city_buttons[0]
        assert not disabled_button.enabled
        assert ui_system.handle_click(disabled_button.rect.center)
        assert any("金币不足" in message for message in ui_system.messages)
        print("✓ 禁用生产按钮反馈成功")
        
        # 测试 UI 默认存档加载流程
        assert client.start_game(["玩家1", "AI玩家"], 123)
        with tempfile.TemporaryDirectory() as tmp_dir:
            client.save_system = GameSaveSystem(tmp_dir)
            assert client.save_system.save_game(client.game_engine, "ui_save")
            client.render_system.selected_tile = HexCoord(0, 0)
            client.render_system.set_selected_unit("stale_unit")
            client.render_system.set_reachable_tiles({HexCoord(1, 0)})
            client.ui_system.show_city_panel_for(selected_city)
            client.input_system.set_mode(InputMode.UNIT_SELECTED, "stale_unit")
            client.game_engine = client.game_engine.__class__()
            client.game_started = False
            client._handle_load_game("ui_save")
            assert client.game_started
            assert client.game_engine.player_system.players
            assert client.ai_manager.is_ai_player("player_1")
            assert client.input_system.mode == InputMode.NORMAL
            assert client.render_system.selected_tile is None
            assert client.render_system.selected_unit_id is None
            assert not client.render_system.reachable_tiles
            assert not client.ui_system.show_city_panel
            assert client.ui_system.selected_city is None
        print("✓ UI 默认存档加载成功")
        
        print("\n=== 所有测试通过 ===")
        print("可以运行 'python scripts/ui_game.py' 启动UI游戏")
        print("\n游戏控制:")
        print("- 按 SPACE 开始游戏")
        print("- 左键点击选择单位或城市")
        print("- B 或建城按钮: 选中移民后建城")
        print("- 左键空地取消选择")
        print("- 选中单位后右键点击黄色范围移动")
        print("- WASD 或方向键移动地图")
        print("- 滚轮缩放")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_path_preview_state_and_hover_path():
    """测试路径预览状态和悬停路径生成。"""
    from ui.client_controller import UIClient
    from src.models import HexCoord, UnitType, TerrainType
    from ui.hex_renderer import HexRenderer
    from ui.ui_config import OFFSET_X, OFFSET_Y
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "AI玩家"], 123)
    player = client.game_engine.get_current_player()
    for unit in list(player.units):
        client.game_engine.unit_system.remove_unit(unit, client.game_engine.map_tiles)
    start = HexCoord(0, 0)
    middle = HexCoord(1, 0)
    target = HexCoord(2, 0)
    for coord in [start, middle, target]:
        client.game_engine.map_tiles[coord].terrain_type = TerrainType.LAND
    soldier = client.game_engine.unit_system.create_unit(UnitType.SOLDIER, player, start)
    client.game_engine.map_tiles[start].units.append(soldier)
    player.units.append(soldier)
    client._center_camera_on_map()
    client._select_unit(soldier)
    assert not client.move_mode_active
    assert client.render_system.reachable_tiles
    
    path = [start, middle, target]
    client.render_system.set_path_preview(path)
    assert client.render_system.path_preview == path
    client.render_system.clear_path_preview()
    assert not client.render_system.path_preview
    
    world_x, world_y = HexRenderer.hex_to_pixel(target.q, target.r, OFFSET_X, OFFSET_Y)
    client.input_system.mouse_pos = client.camera_system.world_to_screen(world_x, world_y)
    visible_tiles = client.game_engine.vision_system.get_visible_tiles(player.id)
    visible_tiles.update(path)
    client._update_hover_path_preview(visible_tiles)
    assert client.render_system.path_preview == path
    surface = pygame.Surface((800, 600))
    client.render_system.render_map(surface, client.game_engine.map_tiles, visible_tiles, player.explored_tiles, player)



def test_selection_cycle_build_city_and_minimap():
    """测试同格循环选择、B 建城、右键取消、小地图和移动力耗尽取消。"""
    from ui.client_controller import UIClient
    from ui.systems.input_system import InputMode
    from src.models import HexCoord, UnitType, TerrainType
    from src.config import CITY_CONFIG
    from ui.hex_renderer import HexRenderer
    from ui.ui_config import OFFSET_X, OFFSET_Y
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "AI玩家"], 123)
    player = client.game_engine.get_current_player()
    settler = player.units[0]
    tile = client.game_engine.map_tiles[settler.position]
    soldier = client.game_engine.unit_system.create_unit(UnitType.SOLDIER, player, tile.coord)
    client.game_engine.unit_system.units.append(soldier) if soldier not in client.game_engine.unit_system.units else None
    player.units.append(soldier)
    tile.units.append(soldier)
    city = client.game_engine.city_system.create_city(player, tile.coord, client.game_engine.map_tiles)
    player.cities.append(city)
    
    client._handle_normal_click(tile, player)
    assert client.input_system.get_selected_unit_id() == settler.id
    client._handle_unit_selected_click(tile, player)
    assert client.input_system.get_selected_unit_id() == soldier.id
    client._handle_unit_selected_click(tile, player)
    assert client.input_system.mode == InputMode.CITY_SELECTED
    assert client.ui_system.selected_city == city
    assert client.render_system.selected_tile == city.center_tile
    assert client.render_system.selected_city_economic_tiles
    assert all(
        city.center_tile.distance_to(coord) <= CITY_CONFIG["economic_radius"]
        for coord in client.render_system.selected_city_economic_tiles
    )
    
    empty_tile = next(
        candidate for candidate in client.game_engine.map_tiles.values()
        if not candidate.units and not candidate.city
    )
    client._handle_city_selected_click(empty_tile, player)
    assert client.input_system.mode == InputMode.NORMAL
    assert client.render_system.selected_unit_id is None
    assert not client.render_system.reachable_tiles
    assert not client.render_system.selected_city_economic_tiles
    
    for unit in list(player.units):
        client.game_engine.unit_system.remove_unit(unit, client.game_engine.map_tiles)
    player.cities.clear()
    client.game_engine.city_system.cities.clear()
    tile.city = None
    fresh_settler = client.game_engine.unit_system.create_unit(UnitType.SETTLER, player, tile.coord)
    player.units.append(fresh_settler)
    tile.units.append(fresh_settler)
    client._select_unit(fresh_settler)
    client._handle_key_press(pygame.K_b, True)
    assert len(player.cities) == 1
    assert client.input_system.mode == InputMode.NORMAL
    
    moving_unit = client.game_engine.unit_system.create_unit(UnitType.SETTLER, player, tile.coord)
    player.units.append(moving_unit)
    tile.units.append(moving_unit)
    target = next(coord for coord in tile.coord.neighbors() if coord in client.game_engine.map_tiles)
    client.game_engine.map_tiles[target].terrain_type = TerrainType.OCEAN
    client._select_unit(moving_unit)
    client._handle_unit_selected_click(client.game_engine.map_tiles[target], player)
    assert moving_unit.position == tile.coord
    client._select_unit(moving_unit)
    world_x, world_y = HexRenderer.hex_to_pixel(target.q, target.r, OFFSET_X, OFFSET_Y)
    client._handle_tile_right_click(client.camera_system.world_to_screen(world_x, world_y))
    assert moving_unit.movement_points == 0
    assert client.input_system.mode == InputMode.NORMAL
    
    surface = pygame.Surface((800, 600))
    client.render_system.render_minimap(surface, client.game_engine.map_tiles, player.vision_tiles, player.explored_tiles)
    assert client.render_system.minimap_rect is not None
    assert client.render_system.is_minimap_pos(client.render_system.minimap_rect.center)



def test_batch_soldier_production_and_movement():
    """测试士兵批量生产和批量移动。"""
    from ui.client_controller import UIClient
    from src.models import UnitType, TerrainType
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "AI玩家"], 123)
    player = client.game_engine.get_current_player()
    settler = player.units[0]
    city = client.game_engine.city_system.create_city(player, settler.position, client.game_engine.map_tiles)
    player.cities.append(city)
    client.game_engine.unit_system.remove_unit(settler, client.game_engine.map_tiles)
    player.gold = 5
    
    client._handle_build_unit(city.id, UnitType.SOLDIER, quantity=3)
    soldiers = [unit for unit in player.units if unit.unit_type == UnitType.SOLDIER]
    assert len(soldiers) == 1
    assert soldiers[0].quantity == 3
    assert player.gold == 2
    assert any("生产士兵 3 名" in message for message in client.ui_system.messages)
    
    city_tile = client.game_engine.map_tiles[city.center_tile]
    target = next(coord for coord in city.center_tile.neighbors() if coord in client.game_engine.map_tiles)
    client.game_engine.map_tiles[target].terrain_type = TerrainType.LAND
    client._select_unit(soldiers[0])
    client._handle_key_press(pygame.K_m, True)
    assert client.ui_system.move_soldier_quantity == 3
    client._handle_key_press(pygame.K_9, True)
    assert client.ui_system.move_soldier_quantity == 3
    client._handle_key_press(pygame.K_2, True)
    assert client.ui_system.move_soldier_quantity == 2
    assert any("移动士兵数量已设为 2/3" in message for message in client.ui_system.messages)
    client._handle_unit_selected_click(client.game_engine.map_tiles[target], player)
    assert all(unit.position == city.center_tile for unit in soldiers)
    client._select_unit(soldiers[0])
    client._handle_unit_move_click(client.game_engine.map_tiles[target], player)
    soldier_stacks = [unit for unit in player.units if unit.unit_type == UnitType.SOLDIER]
    moved = [unit for unit in soldier_stacks if unit.position == target]
    stayed = [unit for unit in soldier_stacks if unit.position == city.center_tile]
    assert sum(unit.quantity for unit in moved) == 2
    assert sum(unit.quantity for unit in stayed) == 1
    assert any("已移动 2 名士兵" in message for message in client.ui_system.messages)
    
    surface = pygame.Surface((800, 600))
    client.ui_system.show_city_panel_for(city)
    client.ui_system.render(surface, {
        'current_player': player,
        'turn_number': 1,
        'game_over': False,
        'winner': None,
        'selected_coord': city.center_tile,
        'selected_tile': city_tile,
        'selected_unit': None,
        'selected_city': city
    })
    city_sliders = [slider for slider in client.ui_system.sliders if slider.label == "city_soldier_quantity"]
    assert city_sliders
    city_slider = city_sliders[0]
    assert client.ui_system.handle_mouse_down(city_slider.rect.midleft)
    assert client.ui_system.active_slider == city_slider
    client.ui_system.handle_mouse_drag(city_slider.rect.midright)
    client.ui_system.handle_mouse_up(city_slider.rect.midright)
    assert client.ui_system.active_slider is None
    assert client.ui_system.city_soldier_quantity == city_slider.max_value



def test_split_soldier_stack_keeps_moved_stack_selected_and_saved():
    """测试分兵后继续移动的是分出去的士兵栈，并保存人数。"""
    import json
    from ui.client_controller import UIClient
    from src.models import HexCoord, UnitType, TerrainType
    from src.systems.save_system import GameSaveSystem
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "AI玩家"], 123)
    player = client.game_engine.get_current_player()
    for unit in list(player.units):
        client.game_engine.unit_system.remove_unit(unit, client.game_engine.map_tiles)
    start = HexCoord(0, 0)
    first_target = HexCoord(1, 0)
    second_target = HexCoord(2, 0)
    for coord in [start, first_target, second_target]:
        client.game_engine.map_tiles[coord].terrain_type = TerrainType.LAND
        client.game_engine.map_tiles[coord].owner = None
    soldier_stack = client.game_engine.unit_system.create_unit(UnitType.SOLDIER, player, start, quantity=30)
    client.game_engine.map_tiles[start].units.append(soldier_stack)
    player.units.append(soldier_stack)
    
    client._select_unit(soldier_stack)
    client.ui_system.move_soldier_quantity = 25
    client._handle_unit_move_click(client.game_engine.map_tiles[first_target], player)
    selected_after_first_move = client._find_unit_by_id(client.input_system.get_selected_unit_id())
    assert selected_after_first_move is not None
    assert selected_after_first_move.position == first_target
    assert selected_after_first_move.quantity == 25
    
    client.ui_system.move_soldier_quantity = 21
    client._handle_unit_move_click(client.game_engine.map_tiles[second_target], player)
    soldier_stacks = [unit for unit in player.units if unit.unit_type == UnitType.SOLDIER]
    assert sum(unit.quantity for unit in soldier_stacks if unit.position == start) == 5
    assert sum(unit.quantity for unit in soldier_stacks if unit.position == first_target) == 4
    assert sum(unit.quantity for unit in soldier_stacks if unit.position == second_target) == 21
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        client.save_system = GameSaveSystem(tmp_dir)
        assert client.save_system.save_game(client.game_engine, "stacked")
        with open(os.path.join(tmp_dir, "stacked.json"), "r", encoding="utf-8") as save_file:
            save_data = json.load(save_file)
        saved_quantities = [unit_data.get("quantity") for player_data in save_data["game_data"]["players"] for unit_data in player_data["units"]]
        assert 21 in saved_quantities
        loaded = client.save_system.load_game("stacked")
        loaded_player = loaded.player_system.players[0]
        assert sum(unit.quantity for unit in loaded_player.units if unit.unit_type == UnitType.SOLDIER) == 30



def test_ai_turn_auto_returns_to_human_view():
    """测试 AI 行动很多时仍会自动结束 AI 回合并回到玩家视野。"""
    from ui.client_controller import UIClient
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "AI玩家"], 123)
    human_player, ai_player = client.game_engine.player_system.players
    ai_player.gold = 100
    client._handle_end_turn()
    assert client.ui_system.has_active_modal()
    assert client.render_system.attention_tiles
    client._handle_end_turn(force=True)
    assert client.game_engine.get_current_player() == human_player
    assert not client.ai_manager.is_ai_player(client.game_engine.get_current_player().id)



def test_simultaneous_mode_ui_uses_local_player_view():
    """测试同时回合模式下 UI 使用本地玩家而不是首个可行动玩家。"""
    from ui.client_controller import UIClient
    from ui.systems.input_system import InputMode
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "玩家2"], 123, turn_mode="simultaneous")
    player1, player2 = client.game_engine.player_system.players
    assert client.local_player_id == player1.id
    assert client._get_controlled_player() == player1
    
    client.local_player_id = player2.id
    assert client._get_controlled_player() == player2
    player2_tile = client.game_engine.map_tiles[player2.units[0].position]
    client._handle_normal_click(player2_tile, client._get_controlled_player())
    assert client.input_system.mode == InputMode.UNIT_SELECTED
    assert client.input_system.get_selected_unit_id() == player2.units[0].id
    
    client.ai_manager.clear()
    client._handle_end_turn(force=True)
    assert player2.id in client.game_engine.turn_system.ended_player_ids
    assert not client._can_controlled_player_act()
    assert client._get_game_state()['turn_mode'] == "simultaneous"
    assert not client._get_game_state()['can_act']


def test_simultaneous_single_player_ai_advances_after_human_end():
    """测试单人同时回合中玩家结束后 AI 会自动完成本轮并推进整轮。"""
    from ui.client_controller import UIClient
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "AI玩家"], 123, turn_mode="simultaneous")
    human_player, ai_player = client.game_engine.player_system.players
    assert client.game_engine.turn_system.current_turn == 1
    client._handle_end_turn(force=True)
    assert client.game_engine.turn_system.current_turn == 2
    assert client.game_engine.turn_system.ended_player_ids == set()
    assert client._get_controlled_player() == human_player
    assert client._can_controlled_player_act()
    assert ai_player.cities or not ai_player.units


def test_local_multiplayer_ui_starts_and_switches_clients():
    """测试进程内多人 UI 原型可启动并切换两个客户端视角。"""
    from ui.client_controller import UIClient
    
    pygame.init()
    client = UIClient()
    client._handle_key_press(pygame.K_m, True)
    assert client.ui_system.has_active_modal()
    assert client._start_local_multiplayer("simultaneous", map_seed=123)
    assert client.game_started
    assert client.multiplayer_server is not None
    assert len(client.multiplayer_sessions) == 2
    assert client.game_engine.turn_system.mode == "simultaneous"
    host_player = client._get_controlled_player()
    assert host_player.id == "player_0"
    client._handle_end_turn(force=True)
    assert not client._can_controlled_player_act()
    assert client._switch_multiplayer_client()
    guest_player = client._get_controlled_player()
    assert guest_player.id == "player_1"
    assert client._can_controlled_player_act()
    client._handle_end_turn(force=True)
    assert client.game_engine.turn_system.current_turn == 2
    assert client.game_engine.turn_system.ended_player_ids == set()


def test_local_multiplayer_ui_supports_sequential_switching():
    """测试本机多人轮流回合中可切换到下一位客户端继续操作。"""
    from ui.client_controller import UIClient
    
    pygame.init()
    client = UIClient()
    assert client._start_local_multiplayer("sequential", map_seed=123)
    host_player = client._get_controlled_player()
    assert host_player.id == "player_0"
    client._handle_end_turn(force=True)
    assert not client._can_controlled_player_act()
    assert client._switch_multiplayer_client()
    assert client._get_controlled_player().id == "player_1"
    assert client._can_controlled_player_act()


def test_multi_save_slots_and_player_colors():
    """测试 UI 多存档槽位和稳定的非亮黄色玩家颜色。"""
    from ui.client_controller import UIClient
    from ui.systems.render_system import RenderSystem
    from ui.ui_config import COLORS
    from src.models import Player
    from src.systems.save_system import GameSaveSystem
    
    pygame.init()
    client = UIClient()
    assert client.start_game(["玩家1", "AI玩家"], 123)
    with tempfile.TemporaryDirectory() as tmp_dir:
        client.save_system = GameSaveSystem(tmp_dir)
        client._handle_save_game()
        assert client.ui_system.has_active_modal()
        client._handle_save_game("slot_1")
        client._handle_save_game("slot_2")
        saves = client.save_system.list_saves()
        assert {save['name'] for save in saves} >= {"slot_1", "slot_2"}
        client._handle_load_game()
        assert client.ui_system.has_active_modal()
        client._handle_load_game("slot_2")
        assert client.game_started
    
    render = RenderSystem()
    colors = [render._get_player_color(Player(id=f"player_{index}", name=str(index), gold=0)) for index in range(4)]
    assert len(set(colors)) == 4
    assert COLORS['PLAYER_3'] != (255, 255, 100)
    assert all(color != COLORS['YELLOW'] for color in colors)
    assert render._get_player_color(Player(id="player_2", name="A", gold=0)) == COLORS['PLAYER_3']



def test_unit_markers_and_minimap_rendering():
    """测试移民/士兵同格错开渲染和小地图紧密绘制入口。"""
    from ui.systems.render_system import RenderSystem
    from src.models import Player, Unit, UnitType, HexCoord, Tile, TerrainType
    
    pygame.init()
    render = RenderSystem()
    surface = pygame.Surface((800, 600))
    player = Player(id="player_0", name="玩家", gold=0)
    coord = HexCoord(0, 0)
    settler = Unit("settler", player, coord, UnitType.SETTLER, 1, 1, 1)
    soldier = Unit("soldier", player, coord, UnitType.SOLDIER, 2, 2, 2, quantity=8)
    tile = Tile(coord, TerrainType.LAND, owner=player, units=[settler, soldier])
    render.render_map(surface, {coord: tile}, {coord}, {coord}, player)
    assert surface.get_bounding_rect().width > 0
    render.render_minimap(surface, {coord: tile}, {coord}, {coord})
    assert render.minimap_rect is not None



def test_input_system_slider_drag_captures_mouse():
    """测试拖动滑块时不会触发摄像机拖拽或地图点击。"""
    from ui.systems.input_system import InputSystem
    
    class Event:
        def __init__(self, pos, button=1):
            self.pos = pos
            self.button = button
    
    input_system = InputSystem()
    calls = {"down": 0, "drag": 0, "up": 0, "camera": 0, "tile": 0}
    input_system.on_mouse_down = lambda pos: calls.__setitem__("down", calls["down"] + 1) or True
    input_system.on_mouse_drag = lambda pos: calls.__setitem__("drag", calls["drag"] + 1) or True
    input_system.on_mouse_up = lambda pos: calls.__setitem__("up", calls["up"] + 1) or True
    input_system.on_camera_move = lambda dx, dy: calls.__setitem__("camera", calls["camera"] + 1)
    input_system.on_tile_clicked = lambda pos: calls.__setitem__("tile", calls["tile"] + 1)
    
    input_system._handle_mouse_down(Event((10, 10)))
    input_system._handle_mouse_motion(Event((40, 10)))
    input_system._handle_mouse_up(Event((80, 10)))
    
    assert calls["down"] == 1
    assert calls["drag"] == 1
    assert calls["up"] == 1
    assert calls["camera"] == 0
    assert calls["tile"] == 0



def test_start_menu_and_game_over_keys():
    """测试开始菜单和游戏结束快捷键流程。"""
    from ui.client_controller import UIClient
    from ui.systems.input_system import InputMode
    from src.models import HexCoord
    from src.systems.save_system import GameSaveSystem
    
    pygame.init()
    
    menu_client = UIClient()
    menu_client._handle_key_press(pygame.K_SPACE, True)
    assert menu_client.game_started
    assert menu_client.game_engine.player_system.players
    assert menu_client.game_engine.turn_system.mode == "sequential"
    
    simultaneous_menu_client = UIClient()
    simultaneous_menu_client._handle_key_press(pygame.K_t, True)
    assert simultaneous_menu_client.game_started
    assert simultaneous_menu_client.game_engine.turn_system.mode == "simultaneous"
    
    exit_client = UIClient()
    exit_client.game_started = False
    exit_client.running = True
    exit_client._handle_key_press(pygame.K_ESCAPE, True)
    assert exit_client.running
    assert exit_client.ui_system.has_active_modal()
    exit_client._confirm_exit_game()
    assert not exit_client.running
    
    load_client = UIClient()
    assert load_client.start_game(["玩家1", "AI玩家"], 123)
    with tempfile.TemporaryDirectory() as tmp_dir:
        load_client.save_system = GameSaveSystem(tmp_dir)
        assert load_client.save_system.save_game(load_client.game_engine, "ui_save")
        load_client.game_engine = load_client.game_engine.__class__()
        load_client.game_started = False
        load_client._handle_key_press(pygame.K_l, True)
        assert load_client.ui_system.has_active_modal()
        load_client._handle_load_game("ui_save")
        assert load_client.game_started
        assert load_client.game_engine.player_system.players
    
    restart_client = UIClient()
    assert restart_client.start_game(["玩家1", "AI玩家"], 123)
    old_engine = restart_client.game_engine
    restart_client.game_engine.game_over = True
    restart_client.game_engine.winner = restart_client.game_engine.player_system.players[0]
    restart_client.render_system.selected_tile = HexCoord(0, 0)
    restart_client.render_system.set_selected_unit("stale_unit")
    restart_client.render_system.set_reachable_tiles({HexCoord(1, 0)})
    restart_client.input_system.set_mode(InputMode.UNIT_SELECTED, "stale_unit")
    restart_client._handle_key_press(pygame.K_r, True)
    assert restart_client.game_started
    assert restart_client.game_engine is not old_engine
    assert not restart_client.game_engine.game_over
    assert restart_client.input_system.mode == InputMode.NORMAL
    assert restart_client.render_system.selected_tile is None
    assert restart_client.render_system.selected_unit_id is None
    assert not restart_client.render_system.reachable_tiles
    assert not restart_client.ui_system.show_city_panel
    
    restart_client.game_engine.game_over = True
    restart_client.running = True
    restart_client.input_system.set_mode(InputMode.UNIT_SELECTED, "stale_unit")
    restart_client._handle_key_press(pygame.K_ESCAPE, True)
    assert restart_client.running
    assert restart_client.ui_system.has_active_modal()
    restart_client._confirm_exit_game()
    assert not restart_client.running


if __name__ == "__main__":
    test_ui_fixes()
    test_path_preview_state_and_hover_path()
    test_selection_cycle_build_city_and_minimap()
    test_batch_soldier_production_and_movement()
    test_ai_turn_auto_returns_to_human_view()
    test_multi_save_slots_and_player_colors()
    test_unit_markers_and_minimap_rendering()
    test_input_system_slider_drag_captures_mouse()
    test_start_menu_and_game_over_keys()
