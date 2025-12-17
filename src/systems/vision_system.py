"""
视野系统 - 负责视野计算和战争迷雾
"""
from typing import Set, List
from ..models import Player, Unit, HexCoord


class VisionSystem:
    """视野系统"""
    
    def __init__(self):
        self.all_players = []  # 缓存所有玩家列表
    
    def set_players(self, players: List[Player]):
        """设置玩家列表"""
        self.all_players = players
    
    def update_player_vision(self, player: Player, map_tiles: dict):
        """更新玩家视野"""
        visible_tiles = set()
        
        # 玩家领土总是可见
        for city in player.cities:
            visible_tiles.update(city.territory_tiles)
        
        # 领土视野：每个领土地块提供1格视野
        territory_vision = self.get_territory_vision(player, map_tiles)
        visible_tiles.update(territory_vision)
        
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
    
    def get_territory_vision(self, player: Player, map_tiles: dict) -> Set[HexCoord]:
        """获取领土视野范围 - 每个领土地块提供1格视野"""
        visible_tiles = set()
        
        # 收集所有玩家拥有的领土地块
        territory_tiles = set()
        
        # 从城市领土中收集
        for city in player.cities:
            territory_tiles.update(city.territory_tiles)
        
        # 从直接拥有的地块中收集（被士兵占领的地块）
        for coord, tile in map_tiles.items():
            if tile.owner == player:
                territory_tiles.add(coord)
        
        # 为每个领土地块提供1格视野
        for territory_coord in territory_tiles:
            # 领土地块本身可见
            visible_tiles.add(territory_coord)
            
            # 周围1格范围内可见
            neighbors = territory_coord.neighbors()
            for neighbor_coord in neighbors:
                if neighbor_coord in map_tiles:
                    visible_tiles.add(neighbor_coord)
        
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
    
    def get_visible_tiles(self, player_or_id) -> Set[HexCoord]:
        """获取玩家所有可见地块"""
        if isinstance(player_or_id, str):
            # 根据player_id找到玩家对象
            for player in self.all_players:
                if player.id == player_or_id:
                    return getattr(player, 'vision_tiles', set()).copy()
            return set()
        else:
            # 直接是Player对象
            return getattr(player_or_id, 'vision_tiles', set()).copy()
    
    def get_explored_tiles(self, player_or_id) -> Set[HexCoord]:
        """获取玩家已探索的地块(简化实现：假设可见地块即为已探索)"""
        # 简化实现：假设所有可见地块都是已探索的
        # 在更复杂的实现中，这里应该维护一个永久的已探索地块集合
        return self.get_visible_tiles(player_or_id)
    
    def has_line_of_sight(self, start: HexCoord, end: HexCoord, map_tiles: dict) -> bool:
        """检查两点间是否有视线（简单实现）"""
        # 简单实现：如果距离在合理范围内就有视线
        # 实际游戏中可能需要考虑地形阻挡等因素
        distance = start.distance_to(end)
        return distance <= 10  # 最大视线距离
