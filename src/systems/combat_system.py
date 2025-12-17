"""
战斗系统 - 负责战斗逻辑和占领机制
"""
from typing import List, Tuple, Optional
from ..models import Unit, Player, HexCoord, UnitType
from ..config import CITY_CONFIG


class CombatSystem:
    """战斗系统"""
    
    def __init__(self):
        pass
    
    def resolve_combat(self, attacking_units: List[Unit], defending_units: List[Unit], 
                      position: HexCoord, map_tiles: dict) -> Tuple[List[Unit], List[Unit]]:
        """解决战斗"""
        if not attacking_units or not defending_units:
            return attacking_units, defending_units
        
        # 只有士兵可以参与战斗
        attacking_soldiers = [u for u in attacking_units if u.unit_type == UnitType.SOLDIER]
        defending_soldiers = [u for u in defending_units if u.unit_type == UnitType.SOLDIER]
        
        if not attacking_soldiers or not defending_soldiers:
            return attacking_units, defending_units
        
        attack_strength = len(attacking_soldiers)
        defense_strength = len(defending_soldiers)
        
        # 简单的数量对比战斗
        if attack_strength > defense_strength:
            # 攻击方胜利
            survivors_count = attack_strength - defense_strength
            # 保留部分攻击单位
            survivors = attacking_soldiers[:survivors_count]
            # 防守方全灭
            for unit in defending_soldiers:
                self._remove_unit_from_tile(unit, position, map_tiles)
            
            return survivors + [u for u in attacking_units if u.unit_type != UnitType.SOLDIER], []
            
        elif defense_strength > attack_strength:
            # 防守方胜利  
            survivors_count = defense_strength - attack_strength
            # 保留部分防守单位
            survivors = defending_soldiers[:survivors_count]
            # 攻击方全灭
            for unit in attacking_soldiers:
                self._remove_unit_from_tile(unit, position, map_tiles)
            
            return [], survivors + [u for u in defending_units if u.unit_type != UnitType.SOLDIER]
            
        else:
            # 平手，双方全灭
            for unit in attacking_soldiers + defending_soldiers:
                self._remove_unit_from_tile(unit, position, map_tiles)
            
            return ([u for u in attacking_units if u.unit_type != UnitType.SOLDIER], 
                   [u for u in defending_units if u.unit_type != UnitType.SOLDIER])
    
    def attack_city(self, attacking_units: List[Unit], city, map_tiles: dict) -> bool:
        """攻击城市"""
        attacking_soldiers = [u for u in attacking_units if u.unit_type == UnitType.SOLDIER]
        if not attacking_soldiers:
            return False
        
        attack_strength = len(attacking_soldiers)
        defense_value = CITY_CONFIG["defense_value"]
        
        if attack_strength >= defense_value:
            # 攻击成功，城市易主
            old_owner = city.owner
            new_owner = attacking_soldiers[0].owner
            
            # 转移城市所有权
            self._transfer_city_ownership(city, old_owner, new_owner, map_tiles)
            
            # 部分攻击单位存活
            survivors_count = max(1, attack_strength - defense_value)
            survivors = attacking_soldiers[:survivors_count]
            
            # 移除多余的攻击单位
            for unit in attacking_soldiers[survivors_count:]:
                self._remove_unit_from_tile(unit, city.center_tile, map_tiles)
            
            return True
        else:
            # 攻击失败，攻击单位全灭
            for unit in attacking_soldiers:
                self._remove_unit_from_tile(unit, city.center_tile, map_tiles)
            return False
    
    def check_for_combat(self, position: HexCoord, map_tiles: dict) -> bool:
        """检查指定位置是否需要战斗"""
        tile = map_tiles.get(position)
        if not tile or not tile.units:
            return False
        
        # 检查是否有不同玩家的单位
        players = set(unit.owner for unit in tile.units)
        return len(players) > 1
    
    def _remove_unit_from_tile(self, unit: Unit, position: HexCoord, map_tiles: dict):
        """从地块移除单位"""
        tile = map_tiles.get(position)
        if tile and unit in tile.units:
            tile.units.remove(unit)
        
        # 从玩家单位列表移除
        if unit in unit.owner.units:
            unit.owner.units.remove(unit)
    
    def _transfer_city_ownership(self, city, old_owner: Player, new_owner: Player, map_tiles: dict):
        """转移城市所有权"""
        # 从旧拥有者移除
        if city in old_owner.cities:
            old_owner.cities.remove(city)
        
        # 添加到新拥有者
        city.owner = new_owner
        new_owner.cities.append(city)
        
        # 更新领土所有权
        for tile_coord in city.territory_tiles:
            tile = map_tiles.get(tile_coord)
            if tile:
                tile.owner = new_owner
    
    def can_occupy_tile(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> bool:
        """检查是否可以占领地块"""
        if unit.unit_type != UnitType.SOLDIER:
            return False
        
        tile = map_tiles.get(target_position)
        if not tile:
            return False
        
        # 只能占领陆地
        if tile.terrain_type.value != "land":
            return False
        
        # 如果已经是自己的领土，不需要占领
        if tile.owner == unit.owner:
            return False
        
        return True
    
    def occupy_tile(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> bool:
        """占领地块"""
        if not self.can_occupy_tile(unit, target_position, map_tiles):
            return False
        
        tile = map_tiles.get(target_position)
        if tile:
            tile.owner = unit.owner
            return True
        
        return False
