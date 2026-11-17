"""
地图系统 - 负责地图生成、出生点选择和地块查询
"""
import random
from typing import Dict, List, Optional

from ..config import MAP_CONFIG
from ..models import HexCoord, Tile, TerrainType
from .map_generators import DEFAULT_MAP_TYPE, MAP_TYPES, MapGenerator, land_components

MAP_SIZES = {"small": 8, "medium": 10, "large": 14}
SPAWN_MIN_COMPONENT = 20
SPAWN_MIN_BUILDABLE = 10


class MapSystem:
    """地图系统"""

    def __init__(self, generator_type: str = None, radius: int = None):
        self.tiles: Dict[HexCoord, Tile] = {}
        self.radius = radius or MAP_CONFIG["radius"]
        self.ocean_ratio = MAP_CONFIG["ocean_ratio"]
        self.generator_type = generator_type or MAP_CONFIG["map_type"]

    def configure(self, map_type: Optional[str] = None, map_size: Optional[str] = None):
        """设置地图类型与尺寸（small / medium / large）。"""
        if map_type:
            if map_type not in MAP_TYPES:
                raise ValueError(f"未知地图类型: {map_type}")
            self.generator_type = map_type
        if map_size:
            if map_size not in MAP_SIZES:
                raise ValueError(f"未知地图尺寸: {map_size}")
            self.radius = MAP_SIZES[map_size]

    def generate_map(self, seed: int = None, generator_type: Optional[str] = None) -> Dict[HexCoord, Tile]:
        """生成地图；使用独立随机源，不影响全局 random 状态。"""
        if seed is None:
            seed = MAP_CONFIG["seed"]
        if seed is None:
            seed = random.SystemRandom().randrange(1 << 30)
        map_type = generator_type or self.generator_type
        if map_type not in MAP_TYPES:
            map_type = DEFAULT_MAP_TYPE
        self.generator_type = map_type
        generator = MapGenerator(self.radius, map_type, seed=seed, ocean_ratio=self.ocean_ratio)
        self.tiles = generator.generate()
        return self.tiles

    def buildable_area(self, coord: HexCoord, radius: int = 2) -> int:
        """坐标周围可用陆地数量，用于评估出生点和建城点。"""
        return sum(
            1 for neighbor in coord.within(radius)
            if neighbor in self.tiles and self.tiles[neighbor].terrain_type == TerrainType.LAND
        )

    def select_spawn_tiles(self, count: int, rng: random.Random) -> List[Tile]:
        """选择公平且分散的出生点：大陆块足够大、周边可建城面积足够、彼此距离尽量远。"""
        component_size = {}
        for component in land_components(self.tiles):
            for coord in component:
                component_size[coord] = len(component)
        land = sorted(
            (coord for coord, tile in self.tiles.items()
             if tile.terrain_type == TerrainType.LAND and not tile.units and not tile.city),
            key=lambda coord: (coord.q, coord.r)
        )
        candidates = [
            coord for coord in land
            if component_size.get(coord, 0) >= SPAWN_MIN_COMPONENT
            and self.buildable_area(coord) >= SPAWN_MIN_BUILDABLE
        ]
        if len(candidates) < count:
            candidates = land
        if len(candidates) < count:
            return []

        # 多次随机起点贪心，选出"间距足够 + 最差出生点也不差 + 彼此差距小"的出生点组合
        region = {coord: self.buildable_area(coord, 3) for coord in candidates}
        desired_spacing = max(4, int(self.radius * (1.2 if count == 2 else 0.8)))
        best_set, best_quality = None, None
        for _ in range(40):
            selected = [rng.choice(candidates)]
            while len(selected) < count:
                def score(coord):
                    spacing = min(coord.distance_to(other) for other in selected)
                    return min(spacing, desired_spacing) * 4 + region[coord] * 0.5 + rng.random()
                remaining = [coord for coord in candidates if coord not in selected]
                selected.append(max(remaining, key=score))
            areas = [region[coord] for coord in selected]
            spacing = min(a.distance_to(b) for i, a in enumerate(selected) for b in selected[i + 1:])
            quality = min(spacing, desired_spacing) * 3 + min(areas) - (max(areas) - min(areas))
            if best_quality is None or quality > best_quality:
                best_set, best_quality = selected, quality
        rng.shuffle(best_set)
        return [self.tiles[coord] for coord in best_set]

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
