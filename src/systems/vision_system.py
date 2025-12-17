"""
视野系统 - 负责视野计算和战争迷雾
"""
from typing import Set, List
from ..models import Player, Unit, HexCoord


class VisionSystem:
    """视野系统"""
    
    def __init__(self):
        pass
    
    def update_player_vision(self, player: Player, map_tiles: dict):
        """更新玩家视野"""
        visible_tiles = set()
        
        # 玩家领土总是可见
        for city in player.cities:
            visible_tiles.update(city.territory_tiles)
        
        # 单位视野范围内可见
        for unit in player.units:
            unit_vision = self.get_unit_vision(unit, map_tiles)
            visible_tiles.update(unit_vision)
        
        player.vision_tiles = visible_tiles
    
    def get_unit_vision(self, unit: Unit, map_tiles: dict) -> Set[HexCoord]:
        """获取单位视野范围"""
        visible_tiles = set()
        
        for coord in map_tiles.keys():
            distance = unit.position.distance_to(coord)
            if distance <= unit.vision_range:
                visible_tiles.add(coord)
        
        return visible_tiles
    
    def is_tile_visible(self, player: Player, tile_coord: HexCoord) -> bool:
        """检查地块对玩家是否可见"""
        return tile_coord in player.vision_tiles
    
    def get_visible_units_at_tile(self, player: Player, tile_coord: HexCoord, 
                                 map_tiles: dict) -> List[Unit]:
        """获取玩家在指定地块可见的单位"""
        if not self.is_tile_visible(player, tile_coord):
            return []
        
        tile = map_tiles.get(tile_coord)
        if not tile:
            return []
        
        # 返回所有在该地块的单位
        return tile.units.copy()
    
    def get_visible_tiles(self, player: Player) -> Set[HexCoord]:
        """获取玩家所有可见地块"""
        return player.vision_tiles.copy()
    
    def has_line_of_sight(self, start: HexCoord, end: HexCoord, map_tiles: dict) -> bool:
        """检查两点间是否有视线（简单实现）"""
        # 简单实现：如果距离在合理范围内就有视线
        # 实际游戏中可能需要考虑地形阻挡等因素
        distance = start.distance_to(end)
        return distance <= 10  # 最大视线距离
