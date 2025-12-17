"""
地图系统 - 负责地图生成和地块管理
"""
import random
import math
from typing import Dict, Set, List, Optional
from ..models import HexCoord, Tile, TerrainType
from ..config import MAP_CONFIG
from .map_generators import PerlinNoiseMapGenerator, IslandMapGenerator


class MapSystem:
    """地图系统"""
    
    def __init__(self, generator_type: str = "perlin"):
        self.tiles: Dict[HexCoord, Tile] = {}
        self.radius = MAP_CONFIG["radius"]
        self.ocean_ratio = MAP_CONFIG["ocean_ratio"]
        self.generator_type = generator_type
    def generate_map(self, seed: int = None, generator_type: Optional[str] = None) -> Dict[HexCoord, Tile]:
        """生成地图"""
        if seed is not None:
            random.seed(seed)
        elif MAP_CONFIG["seed"] is not None:
            random.seed(MAP_CONFIG["seed"])
        
        # 选择地图生成器
        gen_type = generator_type or self.generator_type
        
        if gen_type == "island":
            generator = IslandMapGenerator(self.radius, seed=seed)
        elif gen_type == "perlin":
            generator = PerlinNoiseMapGenerator(self.radius, self.ocean_ratio, seed=seed)
        else:
            # 默认简单生成器
            generator = None
        
        if generator:
            self.tiles = generator.generate()
        else:
            # 回退到原始简单生成
            coords = self._generate_hex_coords()
            self.tiles = {}
            for coord in coords:
                terrain = TerrainType.OCEAN if random.random() < self.ocean_ratio else TerrainType.LAND
                self.tiles[coord] = Tile(coord=coord, terrain_type=terrain)
            self._ensure_connected_landmasses()
        
        return self.tiles
    
    def _generate_hex_coords(self) -> Set[HexCoord]:
        """生成六边形地图的所有坐标"""
        coords = set()
        for q in range(-self.radius, self.radius + 1):
            r_min = max(-self.radius, -q - self.radius)
            r_max = min(self.radius, -q + self.radius)
            for r in range(r_min, r_max + 1):
                coords.add(HexCoord(q, r))
        return coords
    
    def _ensure_connected_landmasses(self):
        """确保有连通的陆地块（简单实现）"""
        # 找到所有陆地块
        land_tiles = [coord for coord, tile in self.tiles.items() 
                     if tile.terrain_type == TerrainType.LAND]
        
        if len(land_tiles) < 10:  # 如果陆地太少，强制生成一些
            ocean_tiles = [coord for coord, tile in self.tiles.items() 
                          if tile.terrain_type == TerrainType.OCEAN]
            # 随机选择一些海洋块变为陆地
            for _ in range(min(20, len(ocean_tiles))):
                if ocean_tiles:
                    coord = random.choice(ocean_tiles)
                    self.tiles[coord].terrain_type = TerrainType.LAND
                    ocean_tiles.remove(coord)
    
    def get_tile(self, coord: HexCoord) -> Tile:
        """获取指定坐标的地块"""
        return self.tiles.get(coord)
    
    def get_neighbors(self, coord: HexCoord) -> List[Tile]:
        """获取相邻地块"""
        neighbors = []
        for neighbor_coord in coord.neighbors():
            tile = self.get_tile(neighbor_coord)
            if tile:
                neighbors.append(tile)
        return neighbors
    
    def get_tiles_in_radius(self, center: HexCoord, radius: int) -> List[Tile]:
        """获取指定半径内的所有地块"""
        tiles = []
        for coord, tile in self.tiles.items():
            if center.distance_to(coord) <= radius:
                tiles.append(tile)
        return tiles
    
    def get_random_land_tile(self) -> Tile:
        """获取随机陆地地块"""
        land_tiles = [tile for tile in self.tiles.values() 
                     if tile.terrain_type == TerrainType.LAND]
        return random.choice(land_tiles) if land_tiles else None
