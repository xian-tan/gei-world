"""
主要游戏引擎 - 协调所有系统
"""
import random
from typing import List, Optional, Dict, Any

from .models import (Player, GameAction, ActionType, GameState, 
                     UnitType, HexCoord, TerrainType, ActionEvent, ActionResult)
from .systems.map_system import MapSystem
from .systems.player_system import PlayerSystem
from .systems.unit_system import UnitSystem
from .systems.city_system import CitySystem
from .systems.combat_system import CombatSystem
from .systems.vision_system import VisionSystem
from .systems.turn_system import TurnSystem
from .config import PLAYER_CONFIG


class GameEngine:
    """游戏引擎 - 协调所有系统"""
    
    def __init__(self):
        # 初始化所有系统
        self.map_system = MapSystem()
        self.player_system = PlayerSystem()
        self.unit_system = UnitSystem()
        self.city_system = CitySystem()
        self.combat_system = CombatSystem()
        self.vision_system = VisionSystem()
        self.turn_system = TurnSystem()
        
        # 游戏状态
        self.game_started = False
        self.game_over = False
        self.winner = None
        self.map_tiles = {}
        self.ai_player_configs = {}
        self._last_failure_reason = ""
    
    def initialize_game(self, player_names: List[str], map_seed: int = None) -> bool:
        """初始化游戏"""
        if len(player_names) < 2 or len(player_names) > PLAYER_CONFIG["max_players"]:
            return False
        
        # 生成地图
        self.map_tiles = self.map_system.generate_map(map_seed)
        
        # 创建玩家
        players = []
        for name in player_names:
            player = self.player_system.create_player(name)
            players.append(player)
        
        # 为每个玩家创建初始移民
        spawn_tiles = self._select_spawn_tiles(len(players))
        if len(spawn_tiles) < len(players):
            return False
        
        for player, spawn_tile in zip(players, spawn_tiles):
            settler = self.unit_system.create_unit(
                UnitType.SETTLER, player, spawn_tile.coord
            )
            spawn_tile.units.append(settler)
            player.units.append(settler)
          # 初始化回合系统
        self.turn_system.initialize(players)
        
        # 初始化视野系统的玩家列表
        self.vision_system.set_players(players)
        
        # 更新所有玩家视野
        for player in players:
            self.vision_system.update_player_vision(player, self.map_tiles)
        
        self.game_started = True
        return True
    
    def _select_spawn_tiles(self, player_count: int) -> List:
        """选择不重叠且尽量分散的出生地块。"""
        land_tiles = [
            tile for tile in self.map_tiles.values()
            if tile.terrain_type == TerrainType.LAND and not tile.units and not tile.city
        ]
        random.shuffle(land_tiles)
        
        preferred_distance = max(2, self.map_system.radius // 2)
        for min_distance in range(preferred_distance, 0, -1):
            selected = []
            for tile in land_tiles:
                if all(tile.coord.distance_to(existing.coord) >= min_distance for existing in selected):
                    selected.append(tile)
                    if len(selected) == player_count:
                        return selected
        
        return land_tiles[:player_count]
    
    def execute_action(self, action: GameAction) -> bool:
        """执行游戏行动，保留 bool 返回用于兼容旧调用。"""
        return self.execute_action_with_result(action).success
    
    def execute_action_with_result(self, action: GameAction) -> ActionResult:
        """执行游戏行动并返回结构化结果。"""
        self._last_failure_reason = ""
        before = self._capture_action_snapshot()
        success = self._execute_action_bool(action)
        events = self._build_action_events(before, action, success)
        message = self._build_action_message(action, success, events)
        return ActionResult(success=success, message=message, events=events)
    
    def _fail(self, reason: str) -> bool:
        """记录失败原因并返回 False。"""
        self._last_failure_reason = reason
        return False
    
    def _execute_action_bool(self, action: GameAction) -> bool:
        """执行游戏行动的内部 bool 实现。"""
        if not self.game_started:
            return self._fail("游戏尚未开始")
        if self.game_over:
            return self._fail("游戏已结束，无法继续行动")
        
        # 验证是否是当前玩家
        current_player = self.turn_system.get_current_player()
        if not current_player or current_player.id != action.player_id:
            return self._fail("还没轮到该玩家行动")
        
        # 根据行动类型执行
        if action.action_type == ActionType.MOVE_UNIT:
            return self._execute_move_unit(action)
        elif action.action_type == ActionType.BUILD_CITY:
            return self._execute_build_city(action)
        elif action.action_type == ActionType.BUILD_UNIT:
            return self._execute_build_unit(action)
        elif action.action_type == ActionType.END_TURN:
            return self._execute_end_turn(action)
        
        return self._fail("未知行动类型")
    
    def _execute_move_unit(self, action: GameAction) -> bool:
        """执行移动单位行动"""
        unit_id = action.params.get("unit_id")
        unit_ids = action.params.get("unit_ids") or ([unit_id] if unit_id else [])
        target = action.params.get("target")
        
        if not unit_ids:
            return self._fail("移动失败：未指定单位")
        if not target:
            return self._fail("移动失败：未指定目标位置")
        
        current_player = self.turn_system.get_current_player()
        units = []
        for moving_unit_id in unit_ids:
            moving_unit = self.unit_system.get_unit_by_id(moving_unit_id)
            if not moving_unit:
                return self._fail("移动失败：未找到该单位")
            if moving_unit.owner != current_player:
                return self._fail("移动失败：只能移动自己的单位")
            units.append(moving_unit)
        
        unit = units[0]
        acting_player = current_player
        try:
            target_coord = HexCoord(target[0], target[1])
        except (TypeError, IndexError):
            return self._fail("移动失败：目标位置格式错误")
        
        for moving_unit in units:
            move_failure = self.unit_system.get_move_failure_reason(moving_unit, target_coord, self.map_tiles)
            if move_failure:
                return self._fail(move_failure)
        
        # 先移动所有选中的单位，再统一结算战斗/攻城
        moved_any = False
        for moving_unit in units:
            moved_any = self.unit_system.move_unit(moving_unit, target_coord, self.map_tiles) or moved_any
        if moved_any:
            # 检查是否需要战斗
            if self.combat_system.check_for_combat(target_coord, self.map_tiles):
                self._resolve_combat_at_position(target_coord, acting_player)
            
            target_tile = self.map_tiles.get(target_coord)
            unit = self.unit_system.get_unit_by_id(unit_id)
            if not unit or not target_tile or unit not in target_tile.units:
                self._update_all_visions()
                self._check_game_over()
                return True
            
            # 士兵进入敌方城市中心时立即攻城，由本次批量移动的士兵共同结算
            if (target_tile.city and target_tile.city.owner != acting_player and
                    any(u.owner == acting_player and u.unit_type == UnitType.SOLDIER for u in target_tile.units)):
                attacking_units = [u for u in target_tile.units if u.owner == acting_player]
                self.combat_system.attack_city(attacking_units, target_tile.city, self.map_tiles)
                self._sync_unit_registry()
                unit = self.unit_system.get_unit_by_id(unit.id)
            
            # 如果是士兵，尝试占领普通地块；敌方城市未攻下前不改变城市中心归属
            if unit and unit.unit_type == UnitType.SOLDIER and not (target_tile.city and target_tile.city.owner != unit.owner):
                self.combat_system.occupy_tile(unit, target_coord, self.map_tiles)
            
            # 更新视野
            self._update_all_visions()
            self._check_game_over()
            return True
        
        return False
    
    def _execute_build_city(self, action: GameAction) -> bool:
        """执行建城行动"""
        unit_id = action.params.get("unit_id")
        
        if not unit_id:
            return self._fail("建城失败：未指定移民")
        
        unit = self.unit_system.get_unit_by_id(unit_id)
        current_player = self.turn_system.get_current_player()
        if not unit:
            return self._fail("建城失败：未找到该单位")
        if unit.owner != current_player:
            return self._fail("建城失败：只能使用自己的移民建城")
        if unit.unit_type != UnitType.SETTLER:
            return self._fail("建城失败：只有移民可以建城")
        
        # 建城
        try:
            city = self.city_system.create_city(unit.owner, unit.position, self.map_tiles)
            unit.owner.cities.append(city)
            
            # 移除移民
            self.unit_system.remove_unit(unit, self.map_tiles)
            
            # 更新视野
            self._update_all_visions()
            return True
        except ValueError as error:
            return self._fail(str(error))
    
    def _execute_build_unit(self, action: GameAction) -> bool:
        """执行建造单位行动"""
        city_id = action.params.get("city_id")
        unit_type_str = action.params.get("unit_type")
        
        if not city_id:
            return self._fail("生产失败：未指定城市")
        if not unit_type_str:
            return self._fail("生产失败：未指定单位类型")
        
        try:
            unit_type = UnitType(unit_type_str)
        except ValueError:
            return self._fail("生产失败：未知单位类型")
        
        city = self.city_system.get_city_by_id(city_id)
        current_player = self.turn_system.get_current_player()
        if not city:
            return self._fail("生产失败：未找到该城市")
        if city.owner != current_player:
            return self._fail("生产失败：只能在自己的城市生产")
        
        build_failure = self.city_system.get_build_unit_failure_reason(city, unit_type)
        if build_failure:
            return self._fail(build_failure)
        
        # 建造单位
        unit = self.city_system.build_unit(city, unit_type, self.unit_system, self.map_tiles)
        if unit:
            self._update_all_visions()
            return True
        return self._fail("生产失败")
    
    def _execute_end_turn(self, action: GameAction) -> bool:
        """执行结束回合行动"""
        self.turn_system.end_turn(
            self.player_system, 
            self.unit_system, 
            self.vision_system, 
            self.map_tiles
        )
        
        # 检查游戏是否结束
        self._check_game_over()
        
        return True
    
    def _resolve_combat_at_position(self, position: HexCoord, attacking_player: Player):
        """解决指定位置的战斗"""
        tile = self.map_tiles.get(position)
        if not tile or len(tile.units) < 2:
            return
        
        attacking_units = [unit for unit in tile.units if unit.owner == attacking_player]
        defending_units = [unit for unit in tile.units if unit.owner != attacking_player]
        
        if not attacking_units or not defending_units:
            return
        
        # 解决战斗
        survivors_a, survivors_d = self.combat_system.resolve_combat(
            attacking_units, defending_units, position, self.map_tiles
        )
        
        # 更新地块单位
        tile.units = survivors_a + survivors_d
        self._sync_unit_registry()
    
    def _capture_action_snapshot(self) -> Dict[str, Any]:
        """捕获行动前状态，用于生成结构化事件。"""
        return {
            "unit_ids": {unit.id for unit in self.unit_system.units},
            "unit_owner_by_id": {unit.id: unit.owner.id for unit in self.unit_system.units},
            "unit_position_by_id": {unit.id: [unit.position.q, unit.position.r] for unit in self.unit_system.units},
            "tile_terrain_by_coord": {
                (coord.q, coord.r): tile.terrain_type.value
                for coord, tile in self.map_tiles.items()
            },
            "city_ids": {city.id for city in self.city_system.cities},
            "city_owner_by_id": {city.id: city.owner.id for city in self.city_system.cities},
            "game_over": self.game_over,
            "winner_id": self.winner.id if self.winner else None,
        }
    
    def _build_action_events(self, before: Dict[str, Any], action: GameAction, success: bool) -> List[ActionEvent]:
        """根据行动前后状态生成结构化事件。"""
        events = []
        current_unit_ids = {unit.id for unit in self.unit_system.units}
        current_city_ids = {city.id for city in self.city_system.cities}
        
        if success and action.action_type == ActionType.MOVE_UNIT:
            unit_ids = action.params.get("unit_ids") or [action.params.get("unit_id")]
            for unit_id in unit_ids:
                unit = self.unit_system.get_unit_by_id(unit_id)
                if unit:
                    from_position = before["unit_position_by_id"].get(unit.id)
                    to_position = [unit.position.q, unit.position.r]
                    from_terrain = None
                    if from_position:
                        from_terrain = before["tile_terrain_by_coord"].get(tuple(from_position))
                    to_tile = self.map_tiles.get(unit.position)
                    to_terrain = to_tile.terrain_type.value if to_tile else None
                    events.append(ActionEvent(
                        event_type="unit_moved",
                        message="单位移动成功",
                        data={
                            "unit_id": unit.id,
                            "owner_id": unit.owner.id,
                            "from": from_position,
                            "to": to_position,
                            "from_terrain": from_terrain,
                            "to_terrain": to_terrain,
                            "remaining_movement": unit.movement_points
                        }
                    ))
        
        if success and action.action_type == ActionType.BUILD_CITY:
            new_city_ids = current_city_ids - before["city_ids"]
            for city in self.city_system.cities:
                if city.id in new_city_ids:
                    events.append(ActionEvent(
                        event_type="city_built",
                        message=f"{city.owner.name} 建立了城市",
                        data={
                            "city_id": city.id,
                            "owner_id": city.owner.id,
                            "position": [city.center_tile.q, city.center_tile.r]
                        }
                    ))
        
        if success and action.action_type == ActionType.BUILD_UNIT:
            new_unit_ids = current_unit_ids - before["unit_ids"]
            for unit in self.unit_system.units:
                if unit.id in new_unit_ids:
                    events.append(ActionEvent(
                        event_type="unit_produced",
                        message=f"{unit.owner.name} 生产了 {unit.unit_type.value}",
                        data={
                            "unit_id": unit.id,
                            "owner_id": unit.owner.id,
                            "unit_type": unit.unit_type.value,
                            "position": [unit.position.q, unit.position.r]
                        }
                    ))
        
        if success and action.action_type == ActionType.END_TURN:
            current_player = self.turn_system.get_current_player()
            events.append(ActionEvent(
                event_type="turn_ended",
                message="回合结束",
                data={"next_player_id": current_player.id if current_player else None}
            ))
        
        destroyed_unit_ids = before["unit_ids"] - current_unit_ids
        consumed_unit_id = action.params.get("unit_id") if action.action_type == ActionType.BUILD_CITY else None
        combat_destroyed_unit_ids = {
            unit_id for unit_id in destroyed_unit_ids
            if unit_id != consumed_unit_id
        }
        if success and action.action_type == ActionType.MOVE_UNIT and combat_destroyed_unit_ids:
            events.append(ActionEvent(
                event_type="combat_resolved",
                message=f"战斗结束，{len(combat_destroyed_unit_ids)} 个单位被消灭",
                data={"destroyed_unit_ids": sorted(combat_destroyed_unit_ids)}
            ))
        
        for unit_id in sorted(destroyed_unit_ids):
            if unit_id == consumed_unit_id:
                continue
            events.append(ActionEvent(
                event_type="unit_destroyed",
                message="单位被消灭",
                data={
                    "unit_id": unit_id,
                    "owner_id": before["unit_owner_by_id"].get(unit_id)
                }
            ))
        
        for city in self.city_system.cities:
            old_owner_id = before["city_owner_by_id"].get(city.id)
            if old_owner_id and old_owner_id != city.owner.id:
                events.append(ActionEvent(
                    event_type="city_captured",
                    message=f"城市被 {city.owner.name} 占领",
                    data={
                        "city_id": city.id,
                        "old_owner_id": old_owner_id,
                        "new_owner_id": city.owner.id,
                        "position": [city.center_tile.q, city.center_tile.r]
                    }
                ))
        
        if self.game_over and not before["game_over"]:
            events.append(ActionEvent(
                event_type="game_over",
                message=f"游戏结束，获胜者：{self.winner.name if self.winner else '无'}",
                data={"winner_id": self.winner.id if self.winner else None}
            ))
        
        return events
    
    def _build_action_message(self, action: GameAction, success: bool, events: List[ActionEvent]) -> str:
        """生成人类可读的行动结果消息。"""
        if events:
            for event in reversed(events):
                if event.event_type in {"game_over", "city_captured", "combat_resolved", "unit_destroyed"}:
                    return event.message
        if not success:
            return self._last_failure_reason or "行动失败"
        messages = {
            ActionType.MOVE_UNIT: "单位移动成功",
            ActionType.BUILD_CITY: "城市建立成功",
            ActionType.BUILD_UNIT: "单位生产成功",
            ActionType.END_TURN: "回合结束",
        }
        return messages.get(action.action_type, "行动成功")
    
    def _sync_unit_registry(self):
        """同步全局单位列表，移除已从玩家列表或地图上消失的单位。"""
        live_units = []
        for unit in self.unit_system.units:
            tile = self.map_tiles.get(unit.position)
            if unit in unit.owner.units and tile and unit in tile.units:
                live_units.append(unit)
        self.unit_system.units = live_units
    
    def _update_all_visions(self):
        """刷新所有玩家视野。"""
        for player in self.player_system.players:
            self.vision_system.update_player_vision(player, self.map_tiles)
    
    def _check_game_over(self):
        """统一检查并更新游戏结束状态。"""
        if self.turn_system.is_game_over():
            self.game_over = True
            self.winner = self.turn_system.get_winner()
    
    def get_current_player(self) -> Optional[Player]:
        """获取当前行动玩家"""
        return self.turn_system.get_current_player()
    
    def get_game_state(self) -> GameState:
        """获取当前游戏状态"""
        current_player = self.turn_system.get_current_player()
        
        return GameState(
            turn=self.turn_system.current_turn,
            current_player_id=current_player.id if current_player else "",
            players=self.player_system.players.copy(),
            map_tiles=self.map_tiles.copy(),
            game_over=self.game_over,
            winner=self.winner
        )
    
    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        """获取玩家可见的游戏状态（用于战争迷雾）"""
        player = self.player_system.get_player_by_id(player_id)
        if not player:
            return None
        
        # 创建过滤后的地图状态
        filtered_tiles = {}
        for coord, tile in self.map_tiles.items():
            if self.vision_system.is_tile_visible(player, coord):
                # 可见地块，显示完整信息
                filtered_tiles[coord] = tile
            else:
                # 不可见地块，只显示基本地形信息
                filtered_tile = tile.__class__(
                    coord=tile.coord,
                    terrain_type=tile.terrain_type,
                    owner=None,
                    city=None,
                    units=[]
                )
                filtered_tiles[coord] = filtered_tile
        
        current_player = self.turn_system.get_current_player()
        
        return GameState(
            turn=self.turn_system.current_turn,
            current_player_id=current_player.id if current_player else "",
            players=self.player_system.players.copy(),
            map_tiles=filtered_tiles,
            game_over=self.game_over,
            winner=self.winner
        )
