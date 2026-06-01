#!/usr/bin/env python3
"""
UI游戏演示 - 展示完整的pygame UI功能
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from ui.client_controller import UIClient


def main():
    """主演示函数"""
    print("🎮 六边形策略游戏 - UI版本演示")
    print("=" * 50)
    
    print("\n📋 功能特性:")
    print("✓ 中文字体支持 (宋体/微软雅黑)")
    print("✓ 六边形地图渲染")
    print("✓ 单位选择与高亮显示")
    print("✓ 移民建城功能")
    print("✓ 城市生产界面")
    print("✓ 战争迷雾系统")
    print("✓ 摄像机平移缩放")
    print("✓ 回合制游戏流程")
    
    print("\n🎯 操作指南:")
    print("1. 游戏启动后按 SPACE 开始")
    print("2. 左键点击选择单位或城市")
    print("3. 选中移民后右键点击建城")
    print("4. 选中单位后左键点击移动")
    print("5. WASD/方向键移动地图")
    print("6. 鼠标滚轮缩放地图")
    print("7. ESC键取消选择/退出")
    
    print("\n🎲 游戏目标:")
    print("- 使用移民建立城市")
    print("- 在城市中生产单位")
    print("- 探索和占领更多领土")
    print("- 与AI玩家竞争")
    
    input("\n按回车键启动UI游戏...")
    
    try:
        # 创建并运行UI客户端
        print("🚀 启动游戏引擎...")
        client = UIClient()
        
        print("✅ 游戏界面已准备就绪！")
        print("\n提示: 关闭游戏窗口或按ESC退出")
        
        # 运行游戏主循环
        client.run()
        
    except KeyboardInterrupt:
        print("\n⏸️  游戏被用户中断")
    except Exception as e:
        print(f"\n❌ 游戏运行错误: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
    finally:
        print("🎮 游戏结束，感谢游玩！")


if __name__ == "__main__":
    main()
