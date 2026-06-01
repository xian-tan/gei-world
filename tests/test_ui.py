#!/usr/bin/env python3
"""
测试UI系统的基本功能
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from ui.client_controller import UIClient
from src.models import HexCoord
import pygame


def test_basic_ui_functionality():
    """测试UI系统的基本功能"""
    print("=== UI系统基本功能测试 ===")
    
    try:
        # 创建UI客户端但不运行主循环
        print("1. 初始化UI客户端...")
        pygame.init()
        client = UIClient()
        
        print("✓ UI客户端初始化成功")
        
        # 测试游戏初始化
        print("2. 测试游戏初始化...")
        success = client.start_game(["测试玩家1", "测试玩家2"], 12345)
        
        if success:
            print("✓ 游戏初始化成功")
        else:
            raise AssertionError("游戏初始化失败")
        
        # 测试基本状态获取
        print("3. 测试游戏状态获取...")
        game_state = client._get_game_state()
        
        if game_state and game_state['current_player']:
            print(f"✓ 游戏状态获取成功，当前玩家: {game_state['current_player'].name}")
        else:
            raise AssertionError("游戏状态获取失败")
        
        # 测试六边形坐标转换
        print("4. 测试六边形坐标转换...")
        from ui.hex_renderer import HexRenderer
        
        # 测试坐标转换
        x, y = HexRenderer.hex_to_pixel(0, 0)
        q, r = HexRenderer.pixel_to_hex(x, y)
        
        if q == 0 and r == 0:
            print("✓ 六边形坐标转换正常")
        else:
            print(f"✗ 六边形坐标转换异常: ({q}, {r})")
        
        # 测试渲染系统初始化
        print("5. 测试渲染系统...")
        if client.render_system and client.camera_system:
            print("✓ 渲染系统和摄像机系统初始化成功")
        else:
            raise AssertionError("渲染系统初始化失败")
        
        print("\n=== 所有基本功能测试通过 ===")
        
    except Exception as e:
        print(f"✗ UI测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    


def test_hex_renderer():
    """测试六边形渲染器"""
    print("\n=== 六边形渲染器测试 ===")
    
    from ui.hex_renderer import HexRenderer
    from ui.ui_config import OFFSET_X, OFFSET_Y
    
    # 测试多个坐标转换，必须严格回到同一格，避免点击相邻格
    test_coords = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, -1), (-1, 1), (2, -3), (-4, 5)]
    
    for q, r in test_coords:
        x, y = HexRenderer.hex_to_pixel(q, r)
        back_q, back_r = HexRenderer.pixel_to_hex(x, y)
        assert (back_q, back_r) == (q, r), f"坐标 ({q}, {r}) 转换失败: 得到 ({back_q}, {back_r})"
        
        offset_x, offset_y = HexRenderer.hex_to_pixel(q, r, OFFSET_X, OFFSET_Y)
        offset_back_q, offset_back_r = HexRenderer.pixel_to_hex(offset_x, offset_y, OFFSET_X, OFFSET_Y)
        assert (offset_back_q, offset_back_r) == (q, r), f"带偏移坐标 ({q}, {r}) 转换失败"
        print(f"✓ 坐标 ({q}, {r}) 转换正常")
    
    print("六边形渲染器测试完成")


def test_ui_coordinate_system_consistency():
    """测试渲染中心、摄像机和点击拾取使用同一坐标系。"""
    from ui.hex_renderer import HexRenderer
    from ui.systems.camera_system import CameraSystem
    from ui.systems.render_system import RenderSystem
    from ui.ui_config import OFFSET_X, OFFSET_Y, SCREEN_WIDTH, SCREEN_HEIGHT
    
    camera = CameraSystem(SCREEN_WIDTH, SCREEN_HEIGHT)
    render = RenderSystem()
    scenarios = [
        (0, 0, 1.0),
        (120, -80, 0.75),
        (320, 240, 1.6),
    ]
    world_points = [
        HexRenderer.hex_to_pixel(0, 0, OFFSET_X, OFFSET_Y),
        HexRenderer.hex_to_pixel(1, 0, OFFSET_X, OFFSET_Y),
        HexRenderer.hex_to_pixel(-2, 3, OFFSET_X, OFFSET_Y),
    ]
    
    for camera_x, camera_y, zoom in scenarios:
        camera.set_position(camera_x, camera_y)
        camera.zoom = zoom
        render.camera_x, render.camera_y = camera.get_position()
        render.zoom = camera.get_zoom()
        for world_x, world_y in world_points:
            assert render.world_to_screen(world_x, world_y) == camera.world_to_screen(world_x, world_y)
    
    client = UIClient()
    assert client.start_game(["测试玩家1", "测试玩家2"], 12345)
    sample_coords = list(client.game_engine.map_tiles.keys())[:8]
    for zoom in (1.0, 1.7):
        client.camera_system.zoom = zoom
        for coord in sample_coords:
            world_x, world_y = HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y)
            screen_x, screen_y = client.camera_system.world_to_screen(world_x, world_y)
            assert client._get_tile_at_screen_pos(screen_x, screen_y) == coord


if __name__ == "__main__":
    test_basic_ui_functionality()
    test_hex_renderer()
    print(f"\n🎉 UI系统基本功能正常！")
    print("现在可以运行 'python ui_game.py' 来启动完整的UI游戏")
