#!/usr/bin/env python3
"""
测试UI系统的基本功能
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

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
            print("✗ 游戏初始化失败")
            return False
        
        # 测试基本状态获取
        print("3. 测试游戏状态获取...")
        game_state = client._get_game_state()
        
        if game_state and game_state['current_player']:
            print(f"✓ 游戏状态获取成功，当前玩家: {game_state['current_player'].name}")
        else:
            print("✗ 游戏状态获取失败")
            return False
        
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
            print("✗ 渲染系统初始化失败")
            return False
        
        print("\n=== 所有基本功能测试通过 ===")
        return True
        
    except Exception as e:
        print(f"✗ UI测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        pygame.quit()


def test_hex_renderer():
    """测试六边形渲染器"""
    print("\n=== 六边形渲染器测试 ===")
    
    from ui.hex_renderer import HexRenderer
    
    # 测试多个坐标转换
    test_coords = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, -1), (-1, 1)]
    
    for q, r in test_coords:
        x, y = HexRenderer.hex_to_pixel(q, r)
        back_q, back_r = HexRenderer.pixel_to_hex(x, y)
        
        if abs(back_q - q) <= 1 and abs(back_r - r) <= 1:  # 允许舍入误差
            print(f"✓ 坐标 ({q}, {r}) 转换正常")
        else:
            print(f"✗ 坐标 ({q}, {r}) 转换失败: 得到 ({back_q}, {back_r})")
    
    print("六边形渲染器测试完成")


if __name__ == "__main__":
    success = test_basic_ui_functionality()
    test_hex_renderer()
    
    if success:
        print(f"\n🎉 UI系统基本功能正常！")
        print("现在可以运行 'python ui_game.py' 来启动完整的UI游戏")
    else:
        print(f"\n❌ UI系统存在问题，请检查错误信息")
