"""
视野系统 - 负责视野计算和战争迷雾
"""
from typing import Set, List
from ..models import Player, Unit, HexCoord


class VisionSystem:
    """视野系统"""

    def __init__(self):
        self.all_players = []

    def set_players(self, players: List[Player]):
        """设置玩家列表"""
        self.all_players = players

    def update_player_vision(self, player: Player, map_tiles: dict):
        """更新玩家视野：领土及其周围 1 格、单位视野范围。"""
        visible_tiles = self.get_territory_vision(player, map_tiles)
        for unit in player.units:
            visible_tiles.update(self.get_unit_vision(unit, map_tiles))
        player.vision_tiles = visible_tiles
        player.explored_tiles.update(visible_tiles)

    def get_unit_vision(self, unit: Unit, map_tiles: dict) -> Set[HexCoord]:
        """获取单位视野范围"""
        return {coord for coord in unit.position.within(unit.vision_range) if coord in map_tiles}

    def get_territory_vision(self, player: Player, map_tiles: dict) -> Set[HexCoord]:
        """获取领土视野范围 - 每个领土地块提供1格视野"""
        territory_tiles = set()
        for city in player.cities:
            territory_tiles.update(city.territory_tiles)
        for coord, tile in map_tiles.items():
            if tile.owner == player:
                territory_tiles.add(coord)

        visible_tiles = set()
        for territory_coord in territory_tiles:
            if territory_coord in map_tiles:
                visible_tiles.add(territory_coord)
            for neighbor_coord in territory_coord.neighbors():
                if neighbor_coord in map_tiles:
                    visible_tiles.add(neighbor_coord)
        return visible_tiles

    def is_tile_visible(self, player: Player, tile_coord: HexCoord) -> bool:
        """检查地块对玩家是否可见"""
        return tile_coord in player.vision_tiles

    def _find_player(self, player_or_id):
        if isinstance(player_or_id, str):
            return next((player for player in self.all_players if player.id == player_or_id), None)
        return player_or_id

    def get_visible_tiles(self, player_or_id) -> Set[HexCoord]:
        """获取玩家所有可见地块"""
        player = self._find_player(player_or_id)
        return set(getattr(player, 'vision_tiles', set())) if player else set()

    def get_explored_tiles(self, player_or_id) -> Set[HexCoord]:
        """获取玩家已探索的地块。"""
        player = self._find_player(player_or_id)
        return set(getattr(player, 'explored_tiles', set())) if player else set()
