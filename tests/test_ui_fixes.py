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
        from ui.systems.ui_system import UISystem
        from src.models import HexCoord, UnitType, Player
        from src.systems.save_system import GameSaveSystem
        
        print("✓ 所有模块导入成功")
        
        # 测试字体管理器
        font_manager = get_font_manager()
        test_text = font_manager.render_text("测试中文", 'medium', (255, 255, 255))
        print("✓ 中文字体渲染成功")
        
        # 测试六边形坐标
        coord1 = HexCoord(0, 0)
        coord2 = HexCoord(1, 0)
        distance = coord1.distance_to(coord2)
        print(f"✓ 六边形距离计算: {distance}")
        
        # 测试游戏结束面板渲染
        ui_system = UISystem(800, 600)
        surface = pygame.Surface((800, 600))
        winner = Player(id="player_1", name="测试玩家", gold=100)
        ui_system.render(surface, {
            'current_player': winner,
            'turn_number': 1,
            'game_over': True,
            'winner': winner
        })
        print("✓ 游戏结束面板渲染成功")
        
        # 测试 UI 默认存档加载流程
        client = UIClient()
        assert client.start_game(["玩家1", "AI玩家"], 123)
        with tempfile.TemporaryDirectory() as tmp_dir:
            client.save_system = GameSaveSystem(tmp_dir)
            assert client.save_system.save_game(client.game_engine, "ui_save")
            client.game_engine = client.game_engine.__class__()
            client.game_started = False
            client._handle_load_game()
            assert client.game_started
            assert client.game_engine.player_system.players
            assert client.ai_manager.is_ai_player("player_1")
        print("✓ UI 默认存档加载成功")
        
        print("\n=== 所有测试通过 ===")
        print("可以运行 'python ui_game.py' 启动UI游戏")
        print("\n游戏控制:")
        print("- 按 SPACE 开始游戏")
        print("- 左键点击选择单位或城市")
        print("- 右键点击选中移民的位置建城")
        print("- 选中单位后左键点击其他地块移动")
        print("- WASD 或方向键移动地图")
        print("- 滚轮缩放")
        print("- ESC 取消选择或退出")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_ui_fixes()
