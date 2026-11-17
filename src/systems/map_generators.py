"""
地图生成器：分形值噪声 + 径向衰减 + 后处理。

地图类型：
- continents：2~3 块主要大陆
- pangaea：一整块超大陆
- islands：多个中小岛屿
"""
import math
import random
from typing import Dict, List, Set

from ..models import HexCoord, Tile, TerrainType

MAP_TYPES = {
    # base_scale: 噪声基础波长（相对地图半径）；falloff: 边缘压海强度；ocean_ratio: 目标海洋比例
    # continent_seeds: 大陆核心数量范围；seed_weight: 核心隆起权重；noise_weight: 噪声权重
    "continents": {"base_scale": 0.3, "falloff": 1.0, "ocean_ratio": 0.52,
                   "continent_seeds": (2, 3), "seed_sigma": 0.45, "seed_weight": 1.5, "noise_weight": 0.6,
                   "channel_width": 2.0, "channel_weight": 3.0},
    "pangaea": {"base_scale": 0.7, "falloff": 3.0, "ocean_ratio": 0.45},
    "islands": {"base_scale": 0.2, "falloff": 0.5, "ocean_ratio": 0.62},
}
DEFAULT_MAP_TYPE = "continents"
MIN_ISLAND_SIZE = 3
MAX_LAKE_SIZE = 2


def hex_coords(radius: int) -> List[HexCoord]:
    """生成六边形地图全部坐标（按 q, r 排序，保证确定性）。"""
    return HexCoord(0, 0).within(radius)


def land_components(tiles: Dict[HexCoord, Tile], terrain: TerrainType = TerrainType.LAND) -> List[Set[HexCoord]]:
    """返回指定地形的连通块列表（按大小降序）。"""
    remaining = {coord for coord, tile in tiles.items() if tile.terrain_type == terrain}
    components = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            current = stack.pop()
            for neighbor in current.neighbors():
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    components.sort(key=len, reverse=True)
    return components


class FractalNoise:
    """基于整数哈希的 2D 分形值噪声，结果只取决于种子。"""

    def __init__(self, rng: random.Random, octaves: int = 4, persistence: float = 0.5):
        self.salts = [rng.randrange(1, 1 << 30) for _ in range(octaves)]
        self.persistence = persistence

    @staticmethod
    def _lattice(ix: int, iy: int, salt: int) -> float:
        h = (ix * 374761393 + iy * 668265263 + salt * 2246822519) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF

    @staticmethod
    def _smooth(t: float) -> float:
        return t * t * (3 - 2 * t)

    def _value(self, x: float, y: float, salt: int) -> float:
        ix, iy = math.floor(x), math.floor(y)
        fx, fy = self._smooth(x - ix), self._smooth(y - iy)
        v00 = self._lattice(ix, iy, salt)
        v10 = self._lattice(ix + 1, iy, salt)
        v01 = self._lattice(ix, iy + 1, salt)
        v11 = self._lattice(ix + 1, iy + 1, salt)
        top = v00 + (v10 - v00) * fx
        bottom = v01 + (v11 - v01) * fx
        return top + (bottom - top) * fy

    def sample(self, x: float, y: float) -> float:
        total, amplitude, frequency, norm = 0.0, 1.0, 1.0, 0.0
        for salt in self.salts:
            total += amplitude * self._value(x * frequency, y * frequency, salt)
            norm += amplitude
            amplitude *= self.persistence
            frequency *= 2.0
        return total / norm


class MapGenerator:
    """按地图类型生成地形。"""

    def __init__(self, radius: int, map_type: str = DEFAULT_MAP_TYPE, seed: int = None,
                 ocean_ratio: float = None):
        if map_type not in MAP_TYPES:
            raise ValueError(f"未知地图类型: {map_type}")
        self.radius = radius
        self.map_type = map_type
        self.params = MAP_TYPES[map_type]
        self.ocean_ratio = self.params["ocean_ratio"] if ocean_ratio is None else ocean_ratio
        self.rng = random.Random(seed)

    def generate(self) -> Dict[HexCoord, Tile]:
        coords = hex_coords(self.radius)
        noise = FractalNoise(self.rng)
        offset_x, offset_y = self.rng.uniform(0, 1000), self.rng.uniform(0, 1000)
        wavelength = max(1.0, self.radius * self.params["base_scale"])

        raw = {}
        for coord in coords:
            x = coord.q + coord.r / 2
            y = coord.r * math.sqrt(3) / 2
            raw[coord] = noise.sample(x / wavelength + offset_x, y / wavelength + offset_y)
        mean = sum(raw.values()) / len(raw)
        std = math.sqrt(sum((value - mean) ** 2 for value in raw.values()) / len(raw)) or 1.0

        seeds = self._continent_seeds(coords)
        sigma = max(1.0, self.radius * self.params.get("seed_sigma", 0.3))
        noise_weight = self.params.get("noise_weight", 1.0)
        seed_weight = self.params.get("seed_weight", 0.0)

        channel_width = self.params.get("channel_width", 0.0)
        channel_weight = self.params.get("channel_weight", 0.0)

        elevation = {}
        for coord in coords:
            edge = HexCoord(0, 0).distance_to(coord) / max(1, self.radius)
            value = noise_weight * (raw[coord] - mean) / std - self.params["falloff"] * edge * edge
            if seeds:
                distances = sorted(coord.distance_to(c) for c in seeds)
                value += seed_weight * math.exp(-(distances[0] / sigma) ** 2)
                if len(distances) > 1 and channel_width > 0:
                    gap = distances[1] - distances[0]
                    value -= channel_weight * max(0.0, 1.0 - gap / channel_width)
            elevation[coord] = value

        land_target = round(len(coords) * (1 - self.ocean_ratio))
        ranked = sorted(coords, key=lambda coord: (-elevation[coord], coord.q, coord.r))
        land = set(ranked[:land_target])
        tiles = {
            coord: Tile(coord=coord, terrain_type=TerrainType.LAND if coord in land else TerrainType.OCEAN)
            for coord in coords
        }
        self._remove_small_islands(tiles)
        self._fill_small_lakes(tiles)
        return tiles

    def _continent_seeds(self, coords: List[HexCoord]) -> List[HexCoord]:
        """为大陆模式挑选彼此远离的大陆核心。"""
        seed_range = self.params.get("continent_seeds")
        if not seed_range:
            return []
        count = self.rng.randint(*seed_range)
        inner = [coord for coord in coords if HexCoord(0, 0).distance_to(coord) <= self.radius * 0.6]
        seeds = [self.rng.choice(inner)]
        while len(seeds) < count:
            candidates = self.rng.sample(inner, min(30, len(inner)))
            seeds.append(max(candidates, key=lambda c: min(c.distance_to(s) for s in seeds)))
        return seeds

    def _remove_small_islands(self, tiles: Dict[HexCoord, Tile]):
        for component in land_components(tiles):
            if len(component) < MIN_ISLAND_SIZE:
                for coord in component:
                    tiles[coord].terrain_type = TerrainType.OCEAN

    def _fill_small_lakes(self, tiles: Dict[HexCoord, Tile]):
        for component in land_components(tiles, TerrainType.OCEAN):
            touches_edge = any(HexCoord(0, 0).distance_to(coord) == self.radius for coord in component)
            if not touches_edge and len(component) <= MAX_LAKE_SIZE:
                for coord in component:
                    tiles[coord].terrain_type = TerrainType.LAND
