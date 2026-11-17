"""
地图生成与出生点质量测试。
"""
import random

import pytest

from src.game_engine import GameEngine
from src.models import HexCoord, TerrainType
from src.systems.map_generators import MAP_TYPES, MapGenerator, land_components
from src.systems.map_system import MAP_SIZES, SPAWN_MIN_BUILDABLE, SPAWN_MIN_COMPONENT, MapSystem

SEEDS = range(100)


@pytest.mark.parametrize("map_type", sorted(MAP_TYPES))
def test_no_tiny_islands_and_land_ratio_matches_target(map_type):
    for seed in SEEDS:
        tiles = MapGenerator(10, map_type, seed=seed).generate()
        components = land_components(tiles)
        assert all(len(component) >= 3 for component in components), (map_type, seed)
        land_ratio = sum(map(len, components)) / len(tiles)
        assert abs(land_ratio - (1 - MAP_TYPES[map_type]["ocean_ratio"])) < 0.08, (map_type, seed, land_ratio)


def test_pangaea_is_one_dominant_landmass():
    shares = []
    for seed in SEEDS:
        components = land_components(MapGenerator(10, "pangaea", seed=seed).generate())
        shares.append(len(components[0]) / sum(map(len, components)))
    assert min(shares) >= 0.6
    assert sum(shares) / len(shares) >= 0.9


def test_continents_usually_have_multiple_landmasses():
    big_counts = []
    for seed in SEEDS:
        components = land_components(MapGenerator(10, "continents", seed=seed).generate())
        big_counts.append(sum(1 for component in components if len(component) >= 15))
    assert sum(big_counts) / len(big_counts) >= 2.0
    assert max(big_counts) <= 4


def test_same_seed_is_deterministic():
    first = MapGenerator(10, "continents", seed=5).generate()
    second = MapGenerator(10, "continents", seed=5).generate()
    assert {c: t.terrain_type for c, t in first.items()} == {c: t.terrain_type for c, t in second.items()}


@pytest.mark.parametrize("map_type", ["continents", "pangaea"])
def test_spawns_are_fair_and_spaced_for_four_players(map_type):
    for seed in SEEDS:
        map_system = MapSystem(map_type)
        tiles = map_system.generate_map(seed)
        spawns = map_system.select_spawn_tiles(4, random.Random(seed))
        assert len(spawns) == 4
        component_size = {coord: len(c) for c in land_components(tiles) for coord in c}
        for spawn in spawns:
            assert spawn.terrain_type == TerrainType.LAND
            assert component_size[spawn.coord] >= SPAWN_MIN_COMPONENT
            assert map_system.buildable_area(spawn.coord) >= SPAWN_MIN_BUILDABLE
        spacing = min(a.coord.distance_to(b.coord) for i, a in enumerate(spawns) for b in spawns[i + 1:])
        assert spacing >= 4, (map_type, seed)


@pytest.mark.parametrize("map_size", sorted(MAP_SIZES))
def test_engine_supports_map_sizes_and_types(map_size):
    engine = GameEngine()
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=3, map_type="islands", map_size=map_size)
    radius = MAP_SIZES[map_size]
    assert engine.map_system.radius == radius
    assert len(engine.map_tiles) == 3 * radius * (radius + 1) + 1
    assert engine.map_system.generator_type == "islands"
    assert all(HexCoord(0, 0).distance_to(coord) <= radius for coord in engine.map_tiles)


def test_unknown_map_type_is_rejected():
    with pytest.raises(ValueError):
        MapSystem().configure(map_type="moon")
