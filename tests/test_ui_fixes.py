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
        client._notify_action_result(ActionResult(False, "生产失败：金币不足，需要 30，当前 0"))
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
        assert any("建城" in message and "右键" not in message for message in client.ui_system.messages)
        
        client.game_engine.unit_system.remove_unit(settler, client.game_engine.map_tiles)
        city = client.game_engine.city_system.create_city(player, settler.position, client.game_engine.map_tiles)
        player.cities.append(city)
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
            client._handle_load_game()
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
        print("- 右键取消选择")
        print("- 选中单位后左键点击其他地块移动")
        print("- WASD 或方向键移动地图")
        print("- 滚轮缩放")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_selection_cycle_build_city_and_minimap():
    """测试同格循环选择、B 建城、右键取消、小地图和移动力耗尽取消。"""
    from ui.client_controller import UIClient
    from ui.systems.input_system import InputMode
    from src.models import HexCoord, UnitType, TerrainType
    
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
    
    client._handle_tile_right_click((0, 0))
    assert client.input_system.mode == InputMode.NORMAL
    assert client.render_system.selected_unit_id is None
    assert not client.render_system.reachable_tiles
    
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
    assert moving_unit.movement_points == 0
    assert client.input_system.mode == InputMode.NORMAL
    
    surface = pygame.Surface((800, 600))
    client.render_system.render_minimap(surface, client.game_engine.map_tiles, player.vision_tiles, player.explored_tiles)
    assert client.render_system.minimap_rect is not None
    assert client.render_system.is_minimap_pos(client.render_system.minimap_rect.center)



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
    
    exit_client = UIClient()
    exit_client.game_started = False
    exit_client.running = True
    exit_client._handle_key_press(pygame.K_ESCAPE, True)
    assert not exit_client.running
    
    load_client = UIClient()
    assert load_client.start_game(["玩家1", "AI玩家"], 123)
    with tempfile.TemporaryDirectory() as tmp_dir:
        load_client.save_system = GameSaveSystem(tmp_dir)
        assert load_client.save_system.save_game(load_client.game_engine, "ui_save")
        load_client.game_engine = load_client.game_engine.__class__()
        load_client.game_started = False
        load_client._handle_key_press(pygame.K_l, True)
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
    assert not restart_client.running


if __name__ == "__main__":
    test_ui_fixes()
    test_selection_cycle_build_city_and_minimap()
    test_start_menu_and_game_over_keys()
