"""
玩家系统 - 负责玩家数据管理
"""
from typing import List, Optional
from ..models import Player, Unit, City, TerrainType
from ..config import PLAYER_CONFIG, ECONOMY_CONFIG, CITY_CONFIG


class PlayerSystem:
    """玩家系统"""
    
    def __init__(self):
        self.players: List[Player] = []
        self.current_player_index = 0
    
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
    
    def get_current_player(self) -> Optional[Player]:
        """获取当前行动玩家"""
        if not self.players:
            return None
        return self.players[self.current_player_index]
    
    def next_player(self):
        """切换到下一个玩家"""
        if self.players:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
    
    def add_unit_to_player(self, player: Player, unit: Unit):
        """为玩家添加单位"""
        player.units.append(unit)
    
    def remove_unit_from_player(self, player: Player, unit: Unit):
        """从玩家移除单位"""
        if unit in player.units:
            player.units.remove(unit)
    
    def add_city_to_player(self, player: Player, city: City):
        """为玩家添加城市"""
        player.cities.append(city)
    
    def calculate_income(self, player: Player, map_tiles: dict = None) -> int:
        """计算玩家收入。
        
        有地图数据时，只统计玩家已拥有、且落在任一己方城市经济范围内的陆地地块。
        兼容旧调用时退回到城市初始领土去重统计。
        """
        if not player:
            return 0
        
        income_tiles = set()
        if map_tiles is not None:
            economic_radius = CITY_CONFIG["economic_radius"]
            for city in player.cities:
                for coord, tile in map_tiles.items():
                    if city.center_tile.distance_to(coord) > economic_radius:
                        continue
                    if tile.terrain_type != TerrainType.LAND:
                        continue
                    if tile.owner == player:
                        income_tiles.add(coord)
        else:
            for city in player.cities:
                income_tiles.update(city.territory_tiles)
        
        return len(income_tiles) * ECONOMY_CONFIG["territory_income"]
    
    def update_player_gold(self, player: Player, amount: int):
        """更新玩家金币"""
        player.gold += amount
        if player.gold < 0:
            player.gold = 0
