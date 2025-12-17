"""
单位系统 - 负责单位创建、移动、管理
"""
from typing import List, Optional
from ..models import Unit, UnitType, Player, HexCoord, Tile
from ..config import UNIT_CONFIG


class UnitSystem:
    """单位系统"""
    
    def __init__(self):
        self.units: List[Unit] = []
    
    def create_unit(self, unit_type: UnitType, owner: Player, position: HexCoord) -> Unit:
        """创建单位"""
        if unit_type == UnitType.SETTLER:
            movement_points = 1
            vision_range = UNIT_CONFIG["settler_vision"]
        elif unit_type == UnitType.SOLDIER:
            movement_points = UNIT_CONFIG["soldier_movement"]
            vision_range = UNIT_CONFIG["soldier_vision"]
        else:
            raise ValueError(f"未知单位类型: {unit_type}")
        
        unit = Unit(
            id="",  # 将在__post_init__中自动生成
            owner=owner,
            position=position,
            unit_type=unit_type,
            movement_points=movement_points,
            max_movement_points=movement_points,
            vision_range=vision_range
        )
        
        self.units.append(unit)
        return unit
    
    def get_unit_by_id(self, unit_id: str) -> Optional[Unit]:
        """根据ID获取单位"""
        for unit in self.units:
            if unit.id == unit_id:
                return unit
        return None
    
    def get_units_at_position(self, position: HexCoord) -> List[Unit]:
        """获取指定位置的所有单位"""
        return [unit for unit in self.units if unit.position == position]
    
    def get_player_units(self, player: Player) -> List[Unit]:
        """获取玩家的所有单位"""
        return [unit for unit in self.units if unit.owner == player]
    
    def move_unit(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> bool:
        """移动单位"""
        # 检查目标位置是否存在
        target_tile = map_tiles.get(target_position)
        if not target_tile:
            return False
        
        # 检查移动距离
        distance = unit.position.distance_to(target_position)
        if distance > unit.movement_points:
            return False
        
        # 检查是否为陆地（简单检查，后续可扩展）
        if target_tile.terrain_type.value == "ocean":
            return False
        
        # 执行移动
        old_tile = map_tiles.get(unit.position)
        if old_tile and unit in old_tile.units:
            old_tile.units.remove(unit)
        
        unit.position = target_position
        unit.movement_points -= distance
        target_tile.units.append(unit)
        
        return True
    
    def restore_movement_points(self, player: Player):
        """恢复玩家所有单位的移动力"""
        for unit in self.get_player_units(player):
            unit.movement_points = unit.max_movement_points
    
    def remove_unit(self, unit: Unit, map_tiles: dict):
        """移除单位"""
        # 从地图中移除
        tile = map_tiles.get(unit.position)
        if tile and unit in tile.units:
            tile.units.remove(unit)
        
        # 从单位列表中移除
        if unit in self.units:
            self.units.remove(unit)
        
        # 从玩家单位列表中移除
        if unit in unit.owner.units:
            unit.owner.units.remove(unit)
    
    def get_unit_vision_tiles(self, unit: Unit, map_tiles: dict) -> List[HexCoord]:
        """获取单位的视野范围内的地块"""
        vision_tiles = []
        for coord, tile in map_tiles.items():
            if unit.position.distance_to(coord) <= unit.vision_range:
                vision_tiles.append(coord)
        return vision_tiles
