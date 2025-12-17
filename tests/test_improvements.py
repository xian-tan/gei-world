"""
测试新功能
"""
import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.systems.map_generators import PerlinNoiseMapGenerator, IslandMapGenerator
from src.models import TerrainType
from src.utils import get_player_statistics, calculate_map_bounds
from src.game_engine import GameEngine


class TestMapGenerators(unittest.TestCase):
    """测试地图生成器"""
    
    def test_perlin_generator(self):
        """测试柏林噪声生成器"""
        generator = PerlinNoiseMapGenerator(radius=5, seed=123)
        tiles = generator.generate()
        
        self.assertGreater(len(tiles), 0)
        
        # 检查地形类型
        terrain_types = set(tile.terrain_type for tile in tiles.values())
        self.assertIn(TerrainType.LAND, terrain_types)
        self.assertIn(TerrainType.OCEAN, terrain_types)
    
    def test_island_generator(self):
        """测试岛屿生成器"""
        generator = IslandMapGenerator(radius=5, island_count=2, seed=123)
        tiles = generator.generate()
        
        self.assertGreater(len(tiles), 0)
        
        # 应该有陆地
        land_tiles = [tile for tile in tiles.values() 
                     if tile.terrain_type == TerrainType.LAND]
        self.assertGreater(len(land_tiles), 0)


class TestUtils(unittest.TestCase):
    """测试工具函数"""
    
    def test_player_statistics(self):
        """测试玩家统计"""
        # 创建游戏并获取玩家统计
        engine = GameEngine()
        engine.initialize_game(["测试玩家1", "测试玩家2"], map_seed=123)
        
        player = engine.player_system.players[0]
        stats = get_player_statistics(player)
        
        self.assertIn('name', stats)
        self.assertIn('gold', stats)
        self.assertIn('cities', stats)
        self.assertIn('territory', stats)
        self.assertIn('units', stats)
        self.assertEqual(stats['name'], "测试玩家1")
    
    def test_map_bounds(self):
        """测试地图边界计算"""
        engine = GameEngine()
        engine.initialize_game(["测试玩家1", "测试玩家2"], map_seed=123)
        
        bounds = calculate_map_bounds(engine.map_tiles)
        
        self.assertIn('min_q', bounds)
        self.assertIn('max_q', bounds)
        self.assertIn('min_r', bounds)
        self.assertIn('max_r', bounds)


class TestImprovedGameEngine(unittest.TestCase):
    """测试改进的游戏引擎"""
    
    def test_different_map_types(self):
        """测试不同地图类型"""
        engine = GameEngine()
        
        # 测试岛屿地图
        engine.map_system.generator_type = "island"
        success = engine.initialize_game(["玩家1", "玩家2"], map_seed=123)
        self.assertTrue(success)
        
        # 应该有地图
        self.assertGreater(len(engine.map_tiles), 0)
    
    def test_visible_state(self):
        """测试可见状态"""
        engine = GameEngine()
        engine.initialize_game(["玩家1", "玩家2"], map_seed=123)
        
        player = engine.player_system.players[0]
        visible_state = engine.get_visible_state(player.id)
        
        self.assertIsNotNone(visible_state)
        self.assertEqual(visible_state.current_player_id, player.id)


if __name__ == '__main__':
    unittest.main()
