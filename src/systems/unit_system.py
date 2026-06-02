"""
单位系统 - 负责单位创建、移动、管理
"""
from collections import deque
from typing import Callable, List, Optional
from ..models import Unit, UnitType, Player, HexCoord, Tile
from ..config import UNIT_CONFIG


class UnitSystem:
    """单位系统"""
    
    def __init__(self):
        self.units: List[Unit] = []
    
    def create_unit(self, unit_type: UnitType, owner: Player, position: HexCoord, quantity: int = 1) -> Unit:
        """创建单位；士兵 quantity 表示该单位栈的人数。"""
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
            vision_range=vision_range,
            quantity=max(1, quantity) if unit_type == UnitType.SOLDIER else 1
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
    
    def split_unit_stack(self, unit: Unit, quantity: int, map_tiles: dict) -> Unit:
        """从士兵栈中拆出指定人数，返回用于移动/战斗的新栈。"""
        quantity = max(1, min(quantity, unit.quantity))
        if unit.unit_type != UnitType.SOLDIER or quantity >= unit.quantity:
            return unit
        unit.quantity -= quantity
        split_unit = Unit(
            id="",
            owner=unit.owner,
            position=unit.position,
            unit_type=unit.unit_type,
            movement_points=unit.movement_points,
            max_movement_points=unit.max_movement_points,
            vision_range=unit.vision_range,
            quantity=quantity
        )
        self.units.append(split_unit)
        unit.owner.units.append(split_unit)
        tile = map_tiles.get(unit.position)
        if tile:
            tile.units.append(split_unit)
        return split_unit
    
    def merge_compatible_stacks(self, map_tiles: dict):
        """合并同玩家、同位置、同移动状态的士兵栈。"""
        seen = {}
        for unit in list(self.units):
            if unit.unit_type != UnitType.SOLDIER:
                continue
            key = (
                unit.owner.id,
                unit.position,
                unit.movement_points,
                unit.max_movement_points,
                unit.vision_range,
            )
            if key not in seen:
                seen[key] = unit
                continue
            primary = seen[key]
            primary.quantity += unit.quantity
            self.remove_unit(unit, map_tiles)
    
    def move_unit(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> bool:
        """移动单位"""
        target_tile = map_tiles.get(target_position)
        if self.get_move_failure_reason(unit, target_position, map_tiles):
            return False
        
        movement_cost = self._find_movement_cost(
            unit.position, target_position, unit.movement_points, map_tiles
        )
        
        # 执行移动
        old_tile = map_tiles.get(unit.position)
        if old_tile and unit in old_tile.units:
            old_tile.units.remove(unit)
        
        unit.position = target_position
        unit.movement_points = max(0, unit.movement_points - movement_cost)
        target_tile.units.append(unit)
        
        return True
    
    def get_move_failure_reason(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> Optional[str]:
        """获取移动失败原因；可移动时返回 None。"""
        target_tile = map_tiles.get(target_position)
        if not target_tile:
            return "移动失败：目标不在地图内"
        if unit.movement_points <= 0:
            return "移动失败：该单位本回合移动力已用完，请结束回合恢复"
        path = self.find_movement_path(unit, target_position, map_tiles)
        if path is None:
            return "移动失败：目标不可达，请选择黄色高亮范围内的地块"
        return None
    
    def find_movement_path(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> Optional[List[HexCoord]]:
        """返回单位当前移动力内到目标的最短路径，包含起点和终点。"""
        return self._find_movement_path(unit.position, target_position, unit.movement_points, map_tiles)
    
    def get_reachable_tiles(self, unit: Unit, map_tiles: dict) -> List[HexCoord]:
        """获取单位当前移动力内真实可达的地块。"""
        reachable = []
        for coord in map_tiles.keys():
            if coord == unit.position:
                continue
            if self._find_movement_cost(unit.position, coord, unit.movement_points, map_tiles) is not None:
                reachable.append(coord)
        return reachable
    
    def _find_movement_cost(self, start: HexCoord, target: HexCoord,
                            max_movement: int, map_tiles: dict) -> Optional[int]:
        """按地形规则查找移动消耗。"""
        path = self._find_movement_path(start, target, max_movement, map_tiles)
        if path is None:
            return None
        if start == target:
            return 0
        start_tile = map_tiles.get(start)
        target_tile = map_tiles.get(target)
        if not start_tile or not target_tile:
            return None
        start_is_ocean = start_tile.terrain_type.value == "ocean"
        target_is_ocean = target_tile.terrain_type.value == "ocean"
        if start_is_ocean or target_is_ocean:
            return max_movement
        return len(path) - 1
    
    def _find_movement_path(self, start: HexCoord, target: HexCoord,
                            max_movement: int, map_tiles: dict) -> Optional[List[HexCoord]]:
        """按地形规则查找最短路径。"""
        if start == target:
            return [start]
        if max_movement <= 0:
            return None
        
        start_tile = map_tiles.get(start)
        target_tile = map_tiles.get(target)
        if not start_tile or not target_tile:
            return None
        
        start_is_ocean = start_tile.terrain_type.value == "ocean"
        target_is_ocean = target_tile.terrain_type.value == "ocean"
        
        if not start_is_ocean and not target_is_ocean:
            return self._find_shortest_path(
                start, target, max_movement, map_tiles,
                lambda coord, tile: tile.terrain_type.value != "ocean"
            )
        
        # 陆地下海：必须把海格作为最终落点，并清空全部移动力
        if not start_is_ocean and target_is_ocean:
            return self._find_shortest_path(
                start, target, max_movement, map_tiles,
                lambda coord, tile: (coord == target and tile.terrain_type.value == "ocean")
                or tile.terrain_type.value != "ocean"
            )
        
        # 海面移动力减半；最少允许移动 1 格，避免低移动力单位困死海上
        sea_budget = max(1, max_movement // 2)
        return self._find_shortest_path(
            start, target, sea_budget, map_tiles,
            lambda coord, tile: True
        )
    
    def _find_shortest_path(self, start: HexCoord, target: HexCoord, max_steps: int,
                            map_tiles: dict, can_enter: Callable[[HexCoord, Tile], bool]) -> Optional[List[HexCoord]]:
        """查找步数限制内的最短路径。"""
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            current, path = queue.popleft()
            if len(path) - 1 >= max_steps:
                continue
            for neighbor in current.neighbors():
                if neighbor in visited:
                    continue
                tile = map_tiles.get(neighbor)
                if not tile or not can_enter(neighbor, tile):
                    continue
                next_path = path + [neighbor]
                if neighbor == target:
                    return next_path
                visited.add(neighbor)
                queue.append((neighbor, next_path))
        return None
    
    def _find_land_path_distance(self, start: HexCoord, target: HexCoord,
                                 max_distance: int, map_tiles: dict) -> Optional[int]:
        """查找移动力范围内的陆地路径距离。"""
        if start == target:
            return 0
        
        queue = deque([(start, 0)])
        visited = {start}
        
        while queue:
            current, distance = queue.popleft()
            if distance >= max_distance:
                continue
            
            for neighbor in current.neighbors():
                if neighbor in visited:
                    continue
                tile = map_tiles.get(neighbor)
                if not tile or tile.terrain_type.value == "ocean":
                    continue
                next_distance = distance + 1
                if neighbor == target:
                    return next_distance
                visited.add(neighbor)
                queue.append((neighbor, next_distance))
        
        return None
    
    def _can_reach_ocean_as_final_step(self, start: HexCoord, target: HexCoord,
                                       max_distance: int, map_tiles: dict) -> bool:
        """判断能否在本回合最后一步从陆地进入目标海格。"""
        queue = deque([(start, 0)])
        visited = {start}
        
        while queue:
            current, distance = queue.popleft()
            if distance >= max_distance:
                continue
            
            for neighbor in current.neighbors():
                tile = map_tiles.get(neighbor)
                if not tile:
                    continue
                next_distance = distance + 1
                if neighbor == target and tile.terrain_type.value == "ocean":
                    return next_distance <= max_distance
                if neighbor in visited or tile.terrain_type.value == "ocean":
                    continue
                visited.add(neighbor)
                queue.append((neighbor, next_distance))
        
        return False
    
    def _can_reach_with_any_terrain(self, start: HexCoord, target: HexCoord,
                                    max_steps: int, map_tiles: dict) -> bool:
        """判断海上移动预算内能否到达目标，允许海陆混合。"""
        queue = deque([(start, 0)])
        visited = {start}
        
        while queue:
            current, distance = queue.popleft()
            if distance >= max_steps:
                continue
            
            for neighbor in current.neighbors():
                if neighbor in visited or neighbor not in map_tiles:
                    continue
                next_distance = distance + 1
                if neighbor == target:
                    return True
                visited.add(neighbor)
                queue.append((neighbor, next_distance))
        
        return False
    
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
