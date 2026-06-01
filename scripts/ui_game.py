#!/usr/bin/env python3
"""
UI游戏启动器 - 使用pygame的可视化界面
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from ui.client_controller import UIClient


def main():
    """主函数"""
    print("=== 六边形策略游戏 UI版 ===")
    print("控制说明:")
    print("- 鼠标左键: 选择地块/单位/城市")
    print("- 鼠标右键: 取消选择")
    print("- B/建城按钮: 选中移民后建城")
    print("- 鼠标拖拽: 移动地图")
    print("- 滚轮: 缩放地图")
    print("- WASD/方向键: 移动地图")
    print("- 开始界面: SPACE 新游戏 / L 加载 / ESC 退出")
    print("- 游戏结束: R 重新开始 / ESC 退出")
    print("- ESC: 游戏中取消选择或退出")
    print()
    
    try:
        # 创建UI客户端
        client = UIClient()
        
        # 运行游戏
        client.run()
        
    except KeyboardInterrupt:
        print("\n游戏被用户中断")
    except Exception as e:
        print(f"游戏运行时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("游戏结束")


if __name__ == "__main__":
    main()
