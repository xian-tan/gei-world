"""
非交互式测试增强功能
"""
import tempfile

from src.game_engine import GameEngine
from src.models import HexCoord, TerrainType, UnitType
from src.systems.ai_system import AIManager, SimpleAI, AggressiveAI
from src.systems.save_system import GameSaveSystem
from src.utils import get_player_statistics


def test_ai_system():
    """测试AI系统"""
    print("=== 测试AI系统 ===")
    
    # 初始化游戏
    engine = GameEngine()
    success = engine.initialize_game(["AI玩家1", "AI玩家2"], map_seed=123)
    
    if not success:
        print("游戏初始化失败")
        return
    
    # 设置AI
    ai_manager = AIManager()
    player1 = engine.player_system.players[0]
    player2 = engine.player_system.players[1]
    
    ai_manager.add_ai_player(player1, "simple", "easy")
    ai_manager.add_ai_player(player2, "aggressive", "medium")
    
    print(f"✓ AI系统初始化成功")
    print(f"✓ 玩家1: {player1.name} (简单AI)")
    print(f"✓ 玩家2: {player2.name} (激进AI)")
    
    # 模拟几回合AI行动
    for turn in range(3):
        print(f"\n--- 回合 {turn + 1} ---")
        
        for i in range(2):  # 每个玩家一次行动
            current_player = engine.turn_system.get_current_player()
            if not current_player:
                break
            
            print(f"{current_player.name} 行动:")
            
            # 获取AI行动
            action = ai_manager.get_ai_action(current_player.id, engine)
            
            if action:
                success = engine.execute_action(action)
                print(f"  -> {action.action_type.value}: {'成功' if success else '失败'}")
            else:
                print("  -> 无行动")
        
        # 显示状态
        for player in engine.player_system.players:
            stats = get_player_statistics(player)
            print(f"  {stats['name']}: 💰{stats['gold']} 🏙️{stats['cities']} 👥{len(player.units)}")
    
    print("✓ AI系统测试完成")


def test_aggressive_ai_waits_for_enough_force_before_attacking_city():
    """测试激进 AI 兵力不足时不会直接送死攻城"""
    engine = GameEngine()
    assert engine.initialize_game(["AI玩家1", "AI玩家2"], map_seed=123)

    attacker, defender = engine.player_system.players
    for player in [attacker, defender]:
        for unit in list(player.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

    city_center = HexCoord(0, 0)
    stage = HexCoord(1, 0)
    for coord in [city_center, stage]:
        engine.map_tiles[coord].terrain_type = TerrainType.LAND
    city = engine.city_system.create_city(defender, city_center, engine.map_tiles)
    defender.cities.append(city)

    soldier = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, stage)
    engine.map_tiles[stage].units.append(soldier)
    attacker.units.append(soldier)

    ai = AggressiveAI(attacker)
    target = ai._find_move_target(soldier, engine)
    assert target != city_center


def test_aggressive_ai_attacks_city_when_force_is_sufficient():
    """测试激进 AI 兵力足够时会直接攻城"""
    engine = GameEngine()
    assert engine.initialize_game(["AI玩家1", "AI玩家2"], map_seed=123)

    attacker, defender = engine.player_system.players
    for player in [attacker, defender]:
        for unit in list(player.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

    city_center = HexCoord(0, 0)
    stage = HexCoord(1, 0)
    for coord in [city_center, stage]:
        engine.map_tiles[coord].terrain_type = TerrainType.LAND
    city = engine.city_system.create_city(defender, city_center, engine.map_tiles)
    defender.cities.append(city)

    stationed_soldier = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, city_center)
    moving_soldier = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, stage)
    engine.map_tiles[city_center].units.append(stationed_soldier)
    engine.map_tiles[stage].units.append(moving_soldier)
    attacker.units.extend([stationed_soldier, moving_soldier])

    ai = AggressiveAI(attacker)
    target = ai._find_move_target(moving_soldier, engine)
    assert target == city_center


def test_ai_uses_reachable_movement_targets():
    """测试 AI 只选择真实可达移动目标"""
    engine = GameEngine()
    assert engine.initialize_game(["AI玩家1", "AI玩家2"], map_seed=123)

    player = engine.player_system.players[0]
    for unit in list(player.units):
        engine.unit_system.remove_unit(unit, engine.map_tiles)

    start = HexCoord(0, 0)
    blocked = HexCoord(1, 0)
    unreachable = HexCoord(2, 0)
    reachable = HexCoord(0, 1)
    for coord in [start, unreachable, reachable]:
        engine.map_tiles[coord].terrain_type = TerrainType.LAND
    engine.map_tiles[blocked].terrain_type = TerrainType.OCEAN

    soldier = engine.unit_system.create_unit(UnitType.SOLDIER, player, start)
    engine.map_tiles[start].units.append(soldier)
    player.units.append(soldier)

    ai = SimpleAI(player)
    target = ai._find_move_target(soldier, engine)
    assert target != unreachable
    assert target in engine.unit_system.get_reachable_tiles(soldier, engine.map_tiles)


def test_save_system():
    """测试保存系统"""
    print("\n=== 测试保存系统 ===")
    
    # 创建游戏
    engine = GameEngine()
    engine.initialize_game(["测试玩家1", "测试玩家2"], map_seed=456)
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 创建保存系统
        save_system = GameSaveSystem(tmp_dir)
        
        # 测试保存
        save_name = "test_save"
        success = save_system.save_game(engine, save_name)
        assert success, "游戏保存失败"
        print("✓ 游戏保存成功")
        
        # 测试列出保存文件
        saves = save_system.list_saves()
        print(f"✓ 找到 {len(saves)} 个保存文件")
        assert any(save['name'] == save_name for save in saves)
        
        for save in saves:
            if save['name'] == save_name:
                print(f"  - {save['name']}: 回合{save['turn']}")
                break
    
    print("✓ 保存系统测试完成")


def test_map_generators():
    """测试地图生成器"""
    print("\n=== 测试地图生成器 ===")
    
    from src.systems.map_generators import PerlinNoiseMapGenerator, IslandMapGenerator
    from src.models import TerrainType
    
    # 测试柏林噪声生成器
    perlin_gen = PerlinNoiseMapGenerator(radius=8, seed=789)
    perlin_tiles = perlin_gen.generate()
    
    land_count = sum(1 for tile in perlin_tiles.values() 
                    if tile.terrain_type == TerrainType.LAND)
    ocean_count = len(perlin_tiles) - land_count
    
    print(f"✓ 柏林噪声地图: {len(perlin_tiles)}块地形 ({land_count}陆地, {ocean_count}海洋)")
    
    # 测试岛屿生成器
    island_gen = IslandMapGenerator(radius=8, island_count=3, seed=789)
    island_tiles = island_gen.generate()
    
    land_count = sum(1 for tile in island_tiles.values() 
                    if tile.terrain_type == TerrainType.LAND)
    ocean_count = len(island_tiles) - land_count
    
    print(f"✓ 岛屿地图: {len(island_tiles)}块地形 ({land_count}陆地, {ocean_count}海洋)")
    
    print("✓ 地图生成器测试完成")


def test_enhanced_game_engine():
    """测试增强的游戏引擎"""
    print("\n=== 测试增强游戏引擎 ===")
    
    # 测试不同地图类型
    engine = GameEngine()
    
    # 测试岛屿地图
    engine.map_system.generator_type = "island"
    success = engine.initialize_game(["玩家1", "玩家2"], map_seed=111)
    
    if success:
        print("✓ 岛屿地图游戏初始化成功")
        
        # 测试可见状态
        player = engine.player_system.players[0]
        visible_state = engine.get_visible_state(player.id)
        
        if visible_state:
            visible_tiles = len([coord for coord, tile in visible_state.map_tiles.items()
                               if coord in player.vision_tiles])
            print(f"✓ 玩家可见 {visible_tiles} 块地形")
        
    print("✓ 增强游戏引擎测试完成")


def main():
    """运行所有测试"""
    print("开始测试增强功能...\n")
    
    test_ai_system()
    test_save_system()
    test_map_generators()
    test_enhanced_game_engine()
    
    print(f"\n🎉 所有测试完成！")
    print("\n增强功能包括：")
    print("✅ AI玩家系统 (简单AI、激进AI)")
    print("✅ 游戏保存/加载系统")
    print("✅ 多种地图生成器 (柏林噪声、岛屿)")
    print("✅ 改进的游戏引擎")
    print("✅ 实用工具函数")


if __name__ == "__main__":
    main()
