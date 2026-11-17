"""
视野与战争迷雾测试。
"""
from src.game_engine import GameEngine
from src.models import ActionType, City, GameAction, HexCoord, Player, TerrainType, Unit, UnitType
from src.network_protocol import serialize_player_view
from src.systems.map_system import MapSystem
from src.systems.vision_system import VisionSystem


def _land_map():
    tiles = MapSystem().generate_map(seed=12345)
    for tile in tiles.values():
        tile.terrain_type = TerrainType.LAND
    return tiles


def test_territory_and_its_neighbors_are_visible():
    tiles = _land_map()
    player = Player(id="test", name="测试玩家", gold=0)
    center = HexCoord(0, 0)
    territory = {center, *center.neighbors()}
    player.cities.append(City(id="c", owner=player, center_tile=center, territory_tiles=territory))
    for coord in territory:
        tiles[coord].owner = player
    vision = VisionSystem()
    vision.set_players([player])
    vision.update_player_vision(player, tiles)
    expected = {n for coord in territory for n in [coord, *coord.neighbors()] if n in tiles}
    assert expected == player.vision_tiles


def test_building_city_reveals_territory():
    engine = GameEngine()
    assert engine.initialize_game(["测试玩家", "AI玩家"], 12345)
    player = engine.get_current_player()
    settler = player.units[0]
    assert engine.execute_action(GameAction(player.id, ActionType.BUILD_CITY, {"unit_id": settler.id}))
    city = player.cities[0]
    assert city.territory_tiles <= player.vision_tiles


def test_explored_tiles_keep_history_after_visibility_changes():
    tiles = _land_map()
    player = Player(id="test", name="测试玩家", gold=0)
    unit = Unit(id="u", owner=player, position=HexCoord(0, 0), unit_type=UnitType.SETTLER,
                movement_points=1, max_movement_points=1, vision_range=1)
    player.units.append(unit)
    vision = VisionSystem()
    vision.set_players([player])
    vision.update_player_vision(player, tiles)
    first_visible = set(player.vision_tiles)
    unit.position = HexCoord(4, 0)
    vision.update_player_vision(player, tiles)
    assert HexCoord(0, 0) not in player.vision_tiles
    assert first_visible <= player.explored_tiles
    assert vision.get_explored_tiles(player.id) >= first_visible


def test_player_view_hides_enemy_units_outside_vision():
    engine = GameEngine()
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=21)
    player1, player2 = engine.player_system.players
    enemy_position = player2.units[0].position
    assert enemy_position not in player1.vision_tiles
    view = serialize_player_view(engine, player1.id)
    tile_data = view["tiles"][f"{enemy_position.q},{enemy_position.r}"]
    assert tile_data["units"] == []
    assert not tile_data["visible"]
