"""
城市系统 - 负责城市建设、生产、领土管理
"""
from typing import List, Optional, Set
from ..models import City, Player, HexCoord, UnitType, Unit
from ..config import CITY_CONFIG, UNIT_CONFIG


class CitySystem:
    """城市系统"""
    
    def __init__(self):
        self.cities: List[City] = []
    
    def create_city(self, owner: Player, center_tile: HexCoord, map_tiles: dict) -> City:
        """建立城市"""
        # 检查是否可以建城
        if not self.can_build_city(center_tile, map_tiles, owner):
            raise ValueError("无法在此位置建城")
        
        # 创建城市
        city = City(
            id="",  # 将在__post_init__中自动生成
            owner=owner,
            center_tile=center_tile,
            territory_tiles=set()
        )
        
        # 获得初始领土
        territory_tiles = self._get_initial_territory(center_tile, map_tiles)
        city.territory_tiles = territory_tiles
        
        # 设置地块所有者
        for tile_coord in territory_tiles:
            tile = map_tiles.get(tile_coord)
            if tile:
                tile.owner = owner
        
        # 设置城市中心
        center_tile_obj = map_tiles.get(center_tile)
        if center_tile_obj:
            center_tile_obj.city = city
        
        self.cities.append(city)
        return city
    
    def can_build_city(self, position: HexCoord, map_tiles: dict, owner: Player = None) -> bool:
        """检查是否可以建城"""
        tile = map_tiles.get(position)
        if not tile:
            return False
        
        # 必须是陆地
        if tile.terrain_type.value != "land":
            return False
        
        # 不能已经有城市
        if tile.city:
            return False
        
        # 不能在敌方已拥有地块建城
        if owner and tile.owner and tile.owner != owner:
            return False
        
        # 不能在敌方城市核心范围内建城
        if owner:
            core_radius = CITY_CONFIG["territory_radius"]
            for city in self.cities:
                if city.owner != owner and city.center_tile.distance_to(position) <= core_radius:
                    return False
        
        return True
    
    def _get_initial_territory(self, center: HexCoord, map_tiles: dict) -> Set[HexCoord]:
        """获取城市初始领土"""
        territory = set()
        radius = CITY_CONFIG["territory_radius"]
        
        # 获取中心点及周围指定半径内的所有地块
        for coord, tile in map_tiles.items():
            if center.distance_to(coord) <= radius:
                # 只占领陆地
                if tile.terrain_type.value == "land":
                    territory.add(coord)
        
        return territory
    
    def get_city_by_id(self, city_id: str) -> Optional[City]:
        """根据ID获取城市"""
        for city in self.cities:
            if city.id == city_id:
                return city
        return None
    
    def get_player_cities(self, player: Player) -> List[City]:
        """获取玩家的所有城市"""
        return [city for city in self.cities if city.owner == player]
    
    def add_to_production_queue(self, city: City, unit_type: UnitType):
        """向生产队列添加单位"""
        city.production_queue.append(unit_type)
    
    def can_build_unit(self, city: City, unit_type: UnitType) -> bool:
        """检查是否可以建造单位"""
        cost = self._get_unit_cost(unit_type)
        return city.owner.gold >= cost
    
    def build_unit(self, city: City, unit_type: UnitType, unit_system, map_tiles: dict) -> Optional[Unit]:
        """建造单位"""
        if not self.can_build_unit(city, unit_type):
            return None
        
        # 扣除金币
        cost = self._get_unit_cost(unit_type)
        city.owner.gold -= cost
        
        # 创建单位
        unit = unit_system.create_unit(unit_type, city.owner, city.center_tile)
        
        # 添加到地图
        center_tile = map_tiles.get(city.center_tile)
        if center_tile:
            center_tile.units.append(unit)
        
        # 添加到玩家单位列表
        city.owner.units.append(unit)
        
        return unit
    
    def _get_unit_cost(self, unit_type: UnitType) -> int:
        """获取单位建造成本"""
        if unit_type == UnitType.SETTLER:
            return UNIT_CONFIG["settler_cost"]
        elif unit_type == UnitType.SOLDIER:
            return UNIT_CONFIG["soldier_cost"]
        return 0
    
    def remove_city(self, city: City, map_tiles: dict):
        """移除城市"""
        # 清除地块所有者
        for tile_coord in city.territory_tiles:
            tile = map_tiles.get(tile_coord)
            if tile and tile.owner == city.owner:
                tile.owner = None
        
        # 清除城市中心
        center_tile = map_tiles.get(city.center_tile)
        if center_tile:
            center_tile.city = None
        
        # 从城市列表中移除
        if city in self.cities:
            self.cities.remove(city)
        
        # 从玩家城市列表中移除
        if city in city.owner.cities:
            city.owner.cities.remove(city)
