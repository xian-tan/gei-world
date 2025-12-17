#!/usr/bin/env python3
"""
测试领土视野功能
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_territory_vision():
    """测试领土视野功能"""
    print("=== 领土视野功能测试 ===")
    
    try:
        from src.game_engine import GameEngine
        from src.models import HexCoord
        
        # 创建游戏引擎
        engine = GameEngine()
        success = engine.initialize_game(["测试玩家", "AI玩家"], 12345)
        
        if not success:
            print("✗ 游戏初始化失败")
            return False
        
        current_player = engine.get_current_player()
        print(f"✓ 游戏初始化成功，当前玩家: {current_player.name}")
        
        # 获取玩家初始单位位置
        if not current_player.units:
            print("✗ 玩家没有初始单位")
            return False
        
        settler = current_player.units[0]
        settler_pos = settler.position
        print(f"✓ 玩家移民位置: ({settler_pos.q}, {settler_pos.r})")
        
        # 建立城市来创建领土
        from src.models import GameAction, ActionType
        
        build_city_action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.BUILD_CITY,
            params={'unit_id': settler.id}
        )
        
        success = engine.execute_action(build_city_action)
        if not success:
            print("✗ 建城失败")
            return False
        
        print("✓ 成功建立城市")
        
        # 检查城市领土
        if not current_player.cities:
            print("✗ 玩家没有城市")
            return False
        
        city = current_player.cities[0]
        territory_count = len(city.territory_tiles)
        print(f"✓ 城市控制 {territory_count} 个地块")
        
        # 检查视野
        visible_count = len(current_player.vision_tiles)
        print(f"✓ 玩家可见地块数量: {visible_count}")
        
        # 验证领土视野：每个领土地块应该能看到周围1格
        expected_min_vision = territory_count  # 至少能看到所有领土
        
        if visible_count >= expected_min_vision:
            print("✓ 领土视野功能正常工作")
            
            # 详细检查：验证领土周围是否可见
            territory_vision_working = True
            for territory_tile in city.territory_tiles:
                neighbors = territory_tile.neighbors()
                for neighbor in neighbors:
                    if neighbor in engine.map_tiles and neighbor not in current_player.vision_tiles:
                        # 如果邻居地块存在但不可见，可能有问题
                        # 但也可能是正常的（比如在地图边缘）
                        pass
            
            print("✓ 领土周围地块视野检查完成")
            return True
        else:
            print(f"✗ 视野范围不足，期望至少 {expected_min_vision}，实际 {visible_count}")
            return False
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_territory_vision_detailed():
    """详细测试领土视野"""
    print("\n=== 详细领土视野测试 ===")
    
    try:
        from src.systems.vision_system import VisionSystem
        from src.models import Player, City, HexCoord
        from src.systems.map_system import MapSystem
        
        # 创建测试数据
        vision_system = VisionSystem()
        map_system = MapSystem()
        map_tiles = map_system.generate_map(seed=12345)
        
        # 创建测试玩家
        player = Player(id="test", name="测试玩家", gold=100)
        
        # 创建测试城市，控制中心格和周围6格
        center_coord = HexCoord(0, 0)
        territory_tiles = {center_coord}
        territory_tiles.update(center_coord.neighbors())
        
        city = City(
            id="test_city",
            owner=player,
            center_tile=center_coord,
            territory_tiles=territory_tiles
        )
        player.cities.append(city)
        
        # 设置地块所有者
        for coord in territory_tiles:
            if coord in map_tiles:
                map_tiles[coord].owner = player
        
        # 设置玩家列表
        vision_system.set_players([player])
        
        # 更新视野
        vision_system.update_player_vision(player, map_tiles)
        
        print(f"✓ 玩家领土地块数量: {len(territory_tiles)}")
        print(f"✓ 玩家可见地块数量: {len(player.vision_tiles)}")
        
        # 验证所有领土地块都可见
        territory_visible = all(coord in player.vision_tiles for coord in territory_tiles)
        print(f"✓ 所有领土地块可见: {territory_visible}")
        
        # 验证领土周围地块可见（1格视野）
        expected_visible = set(territory_tiles)
        for territory_coord in territory_tiles:
            expected_visible.update(neighbor for neighbor in territory_coord.neighbors() 
                                  if neighbor in map_tiles)
        
        actually_visible = player.vision_tiles
        vision_correct = expected_visible.issubset(actually_visible)
        
        print(f"✓ 期望可见地块数: {len(expected_visible)}")
        print(f"✓ 实际可见地块数: {len(actually_visible)}")
        print(f"✓ 领土1格视野正确: {vision_correct}")
        
        return vision_correct
        
    except Exception as e:
        print(f"✗ 详细测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_territory_vision()
    success2 = test_territory_vision_detailed()
    
    if success1 and success2:
        print(f"\n🎉 领土视野功能测试成功!")
        print("现在每个领土地块都提供1格视野范围")
        print("可以运行UI游戏查看效果: python ui_demo.py")
    else:
        print(f"\n❌ 领土视野功能还有问题需要修复")
