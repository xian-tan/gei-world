"""
改进的地图生成器
"""
import random
import math
from typing import Dict, Set, List
from ..models import HexCoord, Tile, TerrainType
from ..config import MAP_CONFIG


class PerlinNoiseMapGenerator:
    """使用简化柏林噪声的地图生成器"""
    
    def __init__(self, radius: int, ocean_ratio: float = 0.7, seed: int = None):
        self.radius = radius
        self.ocean_ratio = ocean_ratio
        if seed is not None:
            random.seed(seed)
    
    def generate(self) -> Dict[HexCoord, Tile]:
        """生成地图"""
        tiles = {}
        
        # 生成所有坐标
        coords = self._generate_hex_coords()
        
        # 使用简化的噪声生成地形
        for coord in coords:
            # 距离中心越远，越容易是海洋
            distance_from_center = math.sqrt(coord.q * coord.q + coord.r * coord.r)
            normalized_distance = distance_from_center / self.radius
            
            # 添加随机噪声
            noise = random.random() * 0.5
            
            # 计算海洋概率
            ocean_probability = self.ocean_ratio + normalized_distance * 0.3 + noise * 0.2
            
            terrain = TerrainType.OCEAN if random.random() < ocean_probability else TerrainType.LAND
            tiles[coord] = Tile(coord=coord, terrain_type=terrain)
        
        # 确保有足够的连通陆地
        self._ensure_playable_landmasses(tiles)
        
        return tiles
    
    def _generate_hex_coords(self) -> Set[HexCoord]:
        """生成六边形坐标"""
        coords = set()
        for q in range(-self.radius, self.radius + 1):
            r_min = max(-self.radius, -q - self.radius)
            r_max = min(self.radius, -q + self.radius)
            for r in range(r_min, r_max + 1):
                coords.add(HexCoord(q, r))
        return coords
    
    def _ensure_playable_landmasses(self, tiles: Dict[HexCoord, Tile]):
        """确保有可游玩的陆地块"""
        # 找到最大的陆地连通区域
        land_coords = {coord for coord, tile in tiles.items() 
                      if tile.terrain_type == TerrainType.LAND}
        
        if len(land_coords) < 20:  # 如果陆地太少
            # 在中心区域强制生成一些陆地
            center_coords = [coord for coord in tiles.keys() 
                           if abs(coord.q) <= 3 and abs(coord.r) <= 3]
            
            for coord in center_coords[:15]:  # 至少15块中心陆地
                if tiles[coord].terrain_type == TerrainType.OCEAN:
                    tiles[coord].terrain_type = TerrainType.LAND


class IslandMapGenerator:
    """岛屿地图生成器"""
    
    def __init__(self, radius: int, island_count: int = 3, seed: int = None):
        self.radius = radius
        self.island_count = island_count
        if seed is not None:
            random.seed(seed)
    
    def generate(self) -> Dict[HexCoord, Tile]:
        """生成岛屿地图"""
        tiles = {}
        
        # 生成所有坐标，默认为海洋
        coords = self._generate_hex_coords()
        for coord in coords:
            tiles[coord] = Tile(coord=coord, terrain_type=TerrainType.OCEAN)
        
        # 生成多个岛屿
        island_centers = self._generate_island_centers(coords)
        
        for center in island_centers:
            self._generate_island(tiles, center)
        
        return tiles
    
    def _generate_hex_coords(self) -> Set[HexCoord]:
        """生成六边形坐标"""
        coords = set()
        for q in range(-self.radius, self.radius + 1):
            r_min = max(-self.radius, -q - self.radius)
            r_max = min(self.radius, -q + self.radius)
            for r in range(r_min, r_max + 1):
                coords.add(HexCoord(q, r))
        return coords
    
    def _generate_island_centers(self, coords: Set[HexCoord]) -> List[HexCoord]:
        """生成岛屿中心点"""
        centers = []
        available_coords = list(coords)
        
        for _ in range(self.island_count):
            if available_coords:
                center = random.choice(available_coords)
                centers.append(center)
                
                # 移除周围区域的坐标，避免岛屿太近
                available_coords = [
                    coord for coord in available_coords 
                    if center.distance_to(coord) > 4
                ]
        
        return centers
    
    def _generate_island(self, tiles: Dict[HexCoord, Tile], center: HexCoord):
        """生成单个岛屿"""
        island_size = random.randint(3, 7)
        
        # 从中心开始扩展
        for coord, tile in tiles.items():
            distance = center.distance_to(coord)
            
            # 根据距离和随机性决定是否为陆地
            if distance == 0:
                tile.terrain_type = TerrainType.LAND
            elif distance <= island_size:
                land_probability = max(0, 1.0 - (distance / island_size) + random.random() * 0.3)
                if random.random() < land_probability:
                    tile.terrain_type = TerrainType.LAND
