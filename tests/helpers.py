"""
测试辅助函数。
"""
from src.models import HexCoord, TerrainType, UnitType

ANCHOR_COORDS = [HexCoord(-9, 9), HexCoord(9, -9), HexCoord(-9, 0), HexCoord(9, 0)]


def anchor_player(engine, player):
    """在地图角落放置一个移民，使玩家在测试中保持存活（规则：无城市且无移民即淘汰）。"""
    index = engine.player_system.players.index(player)
    coord = ANCHOR_COORDS[index]
    tile = engine.map_tiles[coord]
    tile.terrain_type = TerrainType.LAND
    settler = engine.unit_system.create_unit(UnitType.SETTLER, player, coord)
    tile.units.append(settler)
    player.units.append(settler)
    return settler


def place_unit(engine, player, unit_type, coord, quantity=1):
    """在指定坐标放置单位。"""
    unit = engine.unit_system.create_unit(unit_type, player, coord, quantity)
    engine.map_tiles[coord].units.append(unit)
    player.units.append(unit)
    return unit
