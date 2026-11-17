"""
战斗系统 - 负责战斗逻辑和占领机制
"""
from typing import Callable, List, Tuple, Optional
from ..models import Unit, Player, HexCoord, UnitType
from ..config import CITY_CONFIG


class CombatSystem:
    """战斗系统；单位移除委托给 UnitSystem，并通过回调上报被消灭的单位。"""
    
    def __init__(self, unit_system=None, on_unit_destroyed: Optional[Callable[[Unit], None]] = None):
        self.unit_system = unit_system
        self.on_unit_destroyed = on_unit_destroyed
    
    def resolve_combat(self, attacking_units: List[Unit], defending_units: List[Unit], 
                      position: HexCoord, map_tiles: dict) -> Tuple[List[Unit], List[Unit]]:
        """解决战斗"""
        if not attacking_units or not defending_units:
            return attacking_units, defending_units
        
        # 只有士兵可以参与战斗；无士兵保护的移民会被消灭
        attacking_soldiers = [u for u in attacking_units if u.unit_type == UnitType.SOLDIER]
        defending_soldiers = [u for u in defending_units if u.unit_type == UnitType.SOLDIER]
        
        if not attacking_soldiers:
            return attacking_units, defending_units
        if not defending_soldiers:
            for unit in defending_units:
                self._remove_unit_from_tile(unit, position, map_tiles)
            return attacking_units, []
        
        attack_strength = sum(unit.quantity for unit in attacking_soldiers)
        defense_strength = sum(unit.quantity for unit in defending_soldiers)
        
        # 简单的数量对比战斗；失败方地块上的全部单位被消灭
        if attack_strength > defense_strength:
            survivor = attacking_soldiers[0]
            survivor.quantity = attack_strength - defense_strength
            for unit in defending_units + attacking_soldiers[1:]:
                self._remove_unit_from_tile(unit, position, map_tiles)
            return [survivor] + [u for u in attacking_units if u.unit_type != UnitType.SOLDIER], []
            
        elif defense_strength > attack_strength:
            survivor = defending_soldiers[0]
            survivor.quantity = defense_strength - attack_strength
            for unit in attacking_units + defending_soldiers[1:]:
                self._remove_unit_from_tile(unit, position, map_tiles)
            return [], [survivor] + [u for u in defending_units if u.unit_type != UnitType.SOLDIER]
            
        else:
            for unit in attacking_soldiers + defending_soldiers:
                self._remove_unit_from_tile(unit, position, map_tiles)
            return ([u for u in attacking_units if u.unit_type != UnitType.SOLDIER], 
                   [u for u in defending_units if u.unit_type != UnitType.SOLDIER])
    
    def attack_city(self, attacking_units: List[Unit], city, map_tiles: dict) -> bool:
        """攻城：兵力大于城市防御时城市易主，否则进攻方全灭并削减城市防御。"""
        attacking_soldiers = [u for u in attacking_units if u.unit_type == UnitType.SOLDIER]
        if not attacking_soldiers:
            return False
        
        attack_strength = sum(unit.quantity for unit in attacking_soldiers)
        defense_value = city.defense
        
        if attack_strength > defense_value:
            old_owner = city.owner
            new_owner = attacking_soldiers[0].owner
            self._transfer_city_ownership(city, old_owner, new_owner, map_tiles)
            city.defense = CITY_CONFIG["captured_defense"]
            city.productions_this_turn = CITY_CONFIG["productions_per_turn"]
            
            survivor = attacking_soldiers[0]
            survivor.quantity = attack_strength - defense_value
            for unit in attacking_soldiers[1:]:
                self._remove_unit_from_tile(unit, city.center_tile, map_tiles)
            return True
        
        city.defense = max(0, defense_value - attack_strength)
        for unit in attacking_soldiers:
            self._remove_unit_from_tile(unit, city.center_tile, map_tiles)
        return False
    
    def check_for_combat(self, position: HexCoord, map_tiles: dict) -> bool:
        """检查指定位置是否需要战斗"""
        tile = map_tiles.get(position)
        if not tile or not tile.units:
            return False        # 检查是否有不同玩家的单位
        players = set(unit.owner for unit in tile.units)
        return len(players) > 1
    
    def _remove_unit_from_tile(self, unit: Unit, position: HexCoord, map_tiles: dict):
        """战斗中消灭单位：从地块、玩家和注册表中移除。"""
        if self.unit_system is not None:
            self.unit_system.remove_unit(unit, map_tiles)
        else:
            tile = map_tiles.get(position)
            if tile and unit in tile.units:
                tile.units.remove(unit)
            if unit in unit.owner.units:
                unit.owner.units.remove(unit)
        if self.on_unit_destroyed:
            self.on_unit_destroyed(unit)
    
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
        
        # 只能占领与己方领土相邻的地块，领土需要连片扩张
        return any(
            map_tiles.get(neighbor) is not None and map_tiles[neighbor].owner == unit.owner
            for neighbor in target_position.neighbors()
        )
    
    def occupy_tile(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> bool:
        """占领地块"""
        if not self.can_occupy_tile(unit, target_position, map_tiles):
            return False
        
        tile = map_tiles.get(target_position)
        if tile:
            tile.owner = unit.owner
            return True
        
        return False
