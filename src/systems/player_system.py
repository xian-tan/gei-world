"""
玩家系统 - 负责玩家数据管理
"""
from typing import List, Optional
from ..models import Player, TerrainType
from ..config import PLAYER_CONFIG, ECONOMY_CONFIG, CITY_CONFIG


class PlayerSystem:
    """玩家系统"""

    def __init__(self):
        self.players: List[Player] = []

    def create_player(self, name: str) -> Player:
        """创建新玩家"""
        if len(self.players) >= PLAYER_CONFIG["max_players"]:
            raise ValueError("已达到最大玩家数量")

        player = Player(
            id=f"player_{len(self.players)}",
            name=name,
            gold=PLAYER_CONFIG["initial_gold"]
        )
        self.players.append(player)
        return player

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """根据ID获取玩家"""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def calculate_income(self, player: Player, map_tiles: dict = None) -> int:
        """计算玩家收入。

        收入 = 城市数 × 城市中心收入 + 任一己方城市经济范围内的己方陆地数 × 领土收入。
        无地图数据时退回到城市初始领土去重统计。
        """
        if not player:
            return 0

        income_tiles = set()
        if map_tiles is not None:
            economic_radius = CITY_CONFIG["economic_radius"]
            for city in player.cities:
                for coord in city.center_tile.within(economic_radius):
                    tile = map_tiles.get(coord)
                    if tile and tile.terrain_type == TerrainType.LAND and tile.owner == player:
                        income_tiles.add(coord)
        else:
            for city in player.cities:
                income_tiles.update(city.territory_tiles)

        return (len(player.cities) * ECONOMY_CONFIG["city_center_income"]
                + len(income_tiles) * ECONOMY_CONFIG["territory_income"])

    def update_player_gold(self, player: Player, amount: int):
        """更新玩家金币"""
        player.gold = max(0, player.gold + amount)
