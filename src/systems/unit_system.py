"""
单位系统 - 负责单位创建、移动、管理
"""
from collections import deque
from typing import Dict, List, Optional
from ..models import Unit, UnitType, Player, HexCoord, Tile, TerrainType
from ..config import UNIT_CONFIG


class UnitSystem:
    """单位系统"""

    def __init__(self):
        self.units: List[Unit] = []

    def create_unit(self, unit_type: UnitType, owner: Player, position: HexCoord, quantity: int = 1) -> Unit:
        """创建单位；士兵 quantity 表示该单位栈的人数。"""
        if unit_type == UnitType.SETTLER:
            movement_points = UNIT_CONFIG["settler_movement"]
            vision_range = UNIT_CONFIG["settler_vision"]
        elif unit_type == UnitType.SOLDIER:
            movement_points = UNIT_CONFIG["soldier_movement"]
            vision_range = UNIT_CONFIG["soldier_vision"]
        else:
            raise ValueError(f"未知单位类型: {unit_type}")

        unit = Unit(
            id="",
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
        path = self.find_movement_path(unit, target_position, map_tiles)
        if not path or unit.movement_points <= 0:
            return False
        target_tile = map_tiles[target_position]
        start_tile = map_tiles.get(unit.position)

        if self._is_ocean(start_tile) or self._is_ocean(target_tile):
            movement_cost = unit.movement_points
        else:
            movement_cost = len(path) - 1

        if start_tile and unit in start_tile.units:
            start_tile.units.remove(unit)
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
        if not self._can_end_on(unit, target_tile):
            return "移动失败：移民不能进入敌方单位或城市所在地块"
        if self.find_movement_path(unit, target_position, map_tiles) is None:
            return "移动失败：目标不可达，请选择黄色高亮范围内的地块"
        return None

    def find_movement_path(self, unit: Unit, target_position: HexCoord, map_tiles: dict) -> Optional[List[HexCoord]]:
        """返回单位当前移动力内到目标的最短路径，包含起点和终点。"""
        if target_position == unit.position:
            return [unit.position]
        parents = self._explore(unit, map_tiles)
        if target_position not in parents:
            return None
        path = [target_position]
        while path[-1] != unit.position:
            path.append(parents[path[-1]])
        path.reverse()
        return path

    def get_reachable_tiles(self, unit: Unit, map_tiles: dict) -> List[HexCoord]:
        """获取单位当前移动力内真实可达的地块（单次 BFS）。"""
        return [coord for coord in self._explore(unit, map_tiles) if coord != unit.position]

    def _explore(self, unit: Unit, map_tiles: dict) -> Dict[HexCoord, HexCoord]:
        """BFS 求可达集，返回 {可达坐标: 前驱坐标}。

        规则：
        - 陆地出发：只能经过陆地；可在最后一步下海（下海清空移动力）。
        - 海上出发：可经过任意地形，步数为移动力的一半（至少 1）。
        - 敌方单位或敌方城市所在格不可穿过；士兵可将其作为终点发起战斗/攻城，移民不可进入。
        """
        start = unit.position
        start_tile = map_tiles.get(start)
        if not start_tile or unit.movement_points <= 0:
            return {start: start}

        start_at_sea = self._is_ocean(start_tile)
        budget = max(1, unit.movement_points // 2) if start_at_sea else unit.movement_points

        parents: Dict[HexCoord, HexCoord] = {start: start}
        queue = deque([(start, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= budget:
                continue
            for neighbor in current.neighbors():
                if neighbor in parents:
                    continue
                tile = map_tiles.get(neighbor)
                if not tile or not self._can_end_on(unit, tile):
                    continue
                if not start_at_sea and self._is_ocean(tile):
                    parents[neighbor] = current
                    continue
                parents[neighbor] = current
                if not self._is_hostile(unit, tile):
                    queue.append((neighbor, depth + 1))
        return parents

    def _is_hostile(self, unit: Unit, tile: Tile) -> bool:
        """地块上是否有敌方单位或敌方城市。"""
        if tile.city and tile.city.owner != unit.owner:
            return True
        return any(other.owner != unit.owner for other in tile.units)

    def _can_end_on(self, unit: Unit, tile: Tile) -> bool:
        """单位能否以该地块为终点。"""
        if self._is_hostile(unit, tile):
            return unit.unit_type == UnitType.SOLDIER
        return True

    @staticmethod
    def _is_ocean(tile: Optional[Tile]) -> bool:
        return bool(tile and tile.terrain_type == TerrainType.OCEAN)

    def restore_movement_points(self, player: Player):
        """恢复玩家所有单位的移动力"""
        for unit in player.units:
            unit.movement_points = unit.max_movement_points

    def remove_unit(self, unit: Unit, map_tiles: dict):
        """移除单位"""
        tile = map_tiles.get(unit.position)
        if tile and unit in tile.units:
            tile.units.remove(unit)
        if unit in self.units:
            self.units.remove(unit)
        if unit in unit.owner.units:
            unit.owner.units.remove(unit)
