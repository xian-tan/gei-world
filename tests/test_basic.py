"""
基础测试文件
"""
import unittest
from src.models import HexCoord, TerrainType, UnitType
from src.systems.map_system import MapSystem
from src.game_engine import GameEngine


class TestHexCoord(unittest.TestCase):
    """测试六边形坐标"""
    
    def test_distance(self):
        """测试距离计算"""
        coord1 = HexCoord(0, 0)
        coord2 = HexCoord(1, 0)
        self.assertEqual(coord1.distance_to(coord2), 1)
        
        coord3 = HexCoord(2, -1)
        self.assertEqual(coord1.distance_to(coord3), 2)
    
    def test_neighbors(self):
        """测试邻居坐标"""
        coord = HexCoord(0, 0)
        neighbors = coord.neighbors()
        self.assertEqual(len(neighbors), 6)


class TestMapSystem(unittest.TestCase):
    """测试地图系统"""
    
    def test_map_generation(self):
        """测试地图生成"""
        map_system = MapSystem()
        tiles = map_system.generate_map(seed=123)
        
        # 检查是否生成了地块
        self.assertGreater(len(tiles), 0)
        
        # 检查是否有陆地和海洋
        terrain_types = set(tile.terrain_type for tile in tiles.values())
        self.assertIn(TerrainType.LAND, terrain_types)
        self.assertIn(TerrainType.OCEAN, terrain_types)


class TestGameEngine(unittest.TestCase):
    """测试游戏引擎"""
    
    def test_game_initialization(self):
        """测试游戏初始化"""
        engine = GameEngine()
        success = engine.initialize_game(["玩家1", "玩家2"], map_seed=123)
        
        self.assertTrue(success)
        self.assertTrue(engine.game_started)
        self.assertFalse(engine.game_over)
        
        # 检查玩家是否创建
        self.assertEqual(len(engine.player_system.players), 2)
        
        # 检查每个玩家是否有初始移民
        for player in engine.player_system.players:
            self.assertEqual(len(player.units), 1)
            self.assertEqual(player.units[0].unit_type, UnitType.SETTLER)
    
    def test_initial_spawn_tiles_are_unique_and_spaced(self):
        """测试初始出生点不重叠且有基本间距"""
        engine = GameEngine()
        success = engine.initialize_game(["玩家1", "玩家2", "玩家3", "玩家4"], map_seed=123)
        self.assertTrue(success)
        
        spawn_positions = [player.units[0].position for player in engine.player_system.players]
        self.assertEqual(len(spawn_positions), len(set(spawn_positions)))
        
        for index, coord in enumerate(spawn_positions):
            for other in spawn_positions[index + 1:]:
                self.assertGreaterEqual(coord.distance_to(other), 2)
    
    def test_initial_spawn_tiles_are_reachable_by_land_or_sea(self):
        """测试初始出生点允许经海路互相可达"""
        engine = GameEngine()
        success = engine.initialize_game(["玩家1", "玩家2", "玩家3", "玩家4"], map_seed=123)
        self.assertTrue(success)
        
        spawn_positions = [player.units[0].position for player in engine.player_system.players]
        for index, coord in enumerate(spawn_positions):
            for other in spawn_positions[index + 1:]:
                self.assertTrue(engine.map_system.are_coords_reachable(coord, other, allow_ocean=True))


if __name__ == '__main__':
    unittest.main()
