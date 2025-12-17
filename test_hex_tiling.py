#!/usr/bin/env python3
"""
测试六边形紧密拼接
"""
import sys
import os
import math

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_hex_tiling():
    """测试六边形紧密拼接"""
    print("=== 六边形紧密拼接测试 ===")
    
    try:
        from ui.hex_renderer import HexRenderer
        from ui.ui_config import HEX_RADIUS
        
        print(f"六边形半径: {HEX_RADIUS}")
        
        # 测试中心六边形和其6个邻居的位置
        center_coord = (0, 0)
        neighbors = [
            (1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)  # 六个相邻坐标
        ]
        
        center_px, center_py = HexRenderer.hex_to_pixel(*center_coord)
        print(f"\n中心六边形 {center_coord}: 像素位置 ({center_px}, {center_py})")
        
        print("\n相邻六边形位置:")
        expected_distance = HEX_RADIUS * math.sqrt(3)  # 平顶式六边形中心距离
        
        for i, neighbor in enumerate(neighbors):
            nx, ny = HexRenderer.hex_to_pixel(*neighbor)
            distance = math.sqrt((nx - center_px)**2 + (ny - center_py)**2)
            
            print(f"  邻居{i+1} {neighbor}: ({nx}, {ny}), 距离中心: {distance:.1f}")
            
            # 检查距离是否接近期望值
            if abs(distance - expected_distance) < 2:
                print(f"    ✓ 距离正确 (期望: {expected_distance:.1f})")
            else:
                print(f"    ✗ 距离错误 (期望: {expected_distance:.1f})")
        
        # 测试3x3网格的排列
        print(f"\n3x3网格测试:")
        print("检查行偏移是否正确...")
        
        for r in range(-1, 2):
            y_positions = []
            for q in range(-1, 2):
                px, py = HexRenderer.hex_to_pixel(q, r)
                y_positions.append(py)
            
            # 检查同一行的Y坐标是否相同
            if len(set(y_positions)) == 1:
                print(f"  r={r}: Y={y_positions[0]} ✓ (同行Y坐标一致)")
            else:
                print(f"  r={r}: Y坐标不一致 {y_positions} ✗")
        
        # 检查行间距
        row_0_y = HexRenderer.hex_to_pixel(0, 0)[1]
        row_1_y = HexRenderer.hex_to_pixel(0, 1)[1]
        row_spacing = abs(row_1_y - row_0_y)
        expected_row_spacing = HEX_RADIUS * 1.5  # 平顶式六边形行间距
        
        print(f"\n行间距测试:")
        print(f"  实际行间距: {row_spacing}")
        print(f"  期望行间距: {expected_row_spacing}")
        
        if abs(row_spacing - expected_row_spacing) < 1:
            print("  ✓ 行间距正确")
        else:
            print("  ✗ 行间距错误")
        
        return True
        
    except Exception as e:
        print(f"✗ 拼接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def visualize_hex_grid():
    """可视化六边形网格布局"""
    print("\n=== 六边形网格可视化 ===")
    
    try:
        from ui.hex_renderer import HexRenderer
        
        print("5x3网格的中心坐标 (q, r) -> (x, y):")
        
        for r in range(-1, 2):
            line = f"r={r:2d}: "
            for q in range(-2, 3):
                px, py = HexRenderer.hex_to_pixel(q, r)
                line += f"({px:4d},{py:3d}) "
            print(line)
        
        print("\n如果是正确的平顶式拼接:")
        print("- 同一行(相同r)的y坐标应该相同")
        print("- 相邻行的y坐标差应该是 HEX_RADIUS * 1.5")
        print("- 奇偶行在x方向应该有偏移")
        
        return True
    except Exception as e:
        print(f"可视化失败: {e}")
        return False

if __name__ == "__main__":
    success1 = test_hex_tiling()
    success2 = visualize_hex_grid()
    
    if success1 and success2:
        print(f"\n🎉 六边形拼接测试完成")
        print("运行UI游戏查看实际效果: python ui_demo.py")
    else:
        print(f"\n❌ 拼接测试中发现问题")
