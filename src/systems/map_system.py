"""
地图系统 - 负责地图生成和地块管理
"""
import random
from typing import Dict, Optional
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
        """生成地图；使用独立随机源，不影响全局 random 状态。"""
        if seed is None:
            seed = MAP_CONFIG["seed"]
        if seed is None:
            seed = random.SystemRandom().randrange(1 << 30)
        gen_type = generator_type or self.generator_type
        if gen_type == "island":
            generator = IslandMapGenerator(self.radius, seed=seed)
        else:
            generator = PerlinNoiseMapGenerator(self.radius, self.ocean_ratio, seed=seed)
        self.tiles = generator.generate()
        return self.tiles

    def are_coords_reachable(self, start: HexCoord, target: HexCoord,
                             allow_ocean: bool = True) -> bool:
        """检查两个坐标是否在当前地图中可达。"""
        if start not in self.tiles or target not in self.tiles:
            return False
        if start == target:
            return True
        visited = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for neighbor in current.neighbors():
                if neighbor in visited:
                    continue
                tile = self.tiles.get(neighbor)
                if not tile:
                    continue
                if not allow_ocean and tile.terrain_type != TerrainType.LAND:
                    continue
                if neighbor == target:
                    return True
                visited.add(neighbor)
                frontier.append(neighbor)
        return False
