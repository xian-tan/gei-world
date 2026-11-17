"""
主要游戏引擎 - 协调所有系统并作为规则唯一入口。

所有状态变更都通过 execute_action_with_result 进入；规则执行过程中直接产出结构化事件，
UI、AI 和网络层只消费 ActionResult，不再依赖前后快照对比。
"""
import random
from typing import List, Optional

from .models import (Player, GameAction, ActionType, GameState, Unit,
                     UnitType, HexCoord, TerrainType, ActionEvent, ActionResult)
from .systems.map_system import MapSystem
from .systems.player_system import PlayerSystem
from .systems.unit_system import UnitSystem
from .systems.city_system import CitySystem
from .systems.combat_system import CombatSystem
from .systems.vision_system import VisionSystem
from .systems.turn_system import TurnSystem, is_player_alive
from .config import PLAYER_CONFIG, GAME_CONFIG

PRIORITY_EVENT_TYPES = ("game_over", "city_captured", "siege_failed", "combat_resolved", "unit_destroyed")


class GameEngine:
    """游戏引擎 - 协调所有系统"""

    def __init__(self, turn_mode: str = TurnSystem.MODE_SEQUENTIAL):
        self.map_system = MapSystem()
        self.player_system = PlayerSystem()
        self.unit_system = UnitSystem()
        self.city_system = CitySystem()
        self.combat_system = CombatSystem(self.unit_system, on_unit_destroyed=self._on_unit_destroyed)
        self.vision_system = VisionSystem()
        self.turn_system = TurnSystem(turn_mode)

        self.game_started = False
        self.game_over = False
        self.winner = None
        self.map_tiles = {}
        self.ai_player_configs = {}
        self.rng = random.Random()
        self._last_failure_reason = ""
        self._events: List[ActionEvent] = []
        self._destroyed: List[Unit] = []

    # ------------------------------------------------------------------ 初始化
    def initialize_game(self, player_names: List[str], map_seed: int = None, turn_mode: str = None,
                        map_type: str = None, map_size: str = None) -> bool:
        """初始化游戏。map_type: continents/pangaea/islands；map_size: small/medium/large。"""
        if len(player_names) < 2 or len(player_names) > PLAYER_CONFIG["max_players"]:
            return False

        self.map_system.configure(map_type, map_size)
        self.rng = random.Random(map_seed)
        self.map_tiles = self.map_system.generate_map(map_seed)

        players = [self.player_system.create_player(name) for name in player_names]
        spawn_tiles = self.map_system.select_spawn_tiles(len(players), self.rng)
        if len(spawn_tiles) < len(players):
            return False
        for player, spawn_tile in zip(players, spawn_tiles):
            self.unit_system.spawn_unit(UnitType.SETTLER, player, spawn_tile.coord, self.map_tiles)

        self.turn_system.initialize(players, turn_mode)
        self.vision_system.set_players(players)
        self._update_all_visions()
        self.game_started = True
        return True

    # ------------------------------------------------------------------ 行动入口
    def execute_action(self, action: GameAction) -> bool:
        """执行游戏行动，保留 bool 返回用于兼容旧调用。"""
        return self.execute_action_with_result(action).success

    def execute_action_with_result(self, action: GameAction) -> ActionResult:
        """执行游戏行动并返回结构化结果。"""
        self._last_failure_reason = ""
        self._events = []
        self._destroyed = []
        success = self._execute_action_bool(action)
        events = self._events if success else []
        return ActionResult(success=success, message=self._build_action_message(action, success, events), events=events)

    def _emit(self, event_type: str, message: str = "", **data):
        self._events.append(ActionEvent(event_type=event_type, message=message, data=data))

    def _fail(self, reason: str) -> bool:
        self._last_failure_reason = reason
        return False

    def _execute_action_bool(self, action: GameAction) -> bool:
        if not self.game_started:
            return self._fail("游戏尚未开始")
        if self.game_over:
            return self._fail("游戏已结束，无法继续行动")
        if not self.turn_system.can_player_act(action.player_id):
            return self._fail(self.turn_system.get_action_denial_reason(action.player_id))

        handlers = {
            ActionType.MOVE_UNIT: self._execute_move_unit,
            ActionType.BUILD_CITY: self._execute_build_city,
            ActionType.BUILD_UNIT: self._execute_build_unit,
            ActionType.END_TURN: self._execute_end_turn,
        }
        handler = handlers.get(action.action_type)
        return handler(action) if handler else self._fail("未知行动类型")

    # ------------------------------------------------------------------ 移动 / 战斗
    def _execute_move_unit(self, action: GameAction) -> bool:
        unit_id = action.params.get("unit_id")
        unit_ids = action.params.get("unit_ids") or ([unit_id] if unit_id else [])
        target = action.params.get("target")
        move_quantity = max(1, int(action.params.get("move_quantity", 1) or 1))

        if not unit_ids:
            return self._fail("移动失败：未指定单位")
        if not target:
            return self._fail("移动失败：未指定目标位置")

        acting_player = self.player_system.get_player_by_id(action.player_id)
        units = []
        for moving_unit_id in unit_ids:
            moving_unit = self.unit_system.get_unit_by_id(moving_unit_id)
            if not moving_unit:
                return self._fail("移动失败：未找到该单位")
            if moving_unit.owner != acting_player:
                return self._fail("移动失败：只能移动自己的单位")
            units.append(moving_unit)

        try:
            target_coord = HexCoord(int(target[0]), int(target[1]))
        except (TypeError, IndexError, ValueError):
            return self._fail("移动失败：目标位置格式错误")

        paths = {}
        for moving_unit in units:
            move_failure = self.unit_system.get_move_failure_reason(moving_unit, target_coord, self.map_tiles)
            if move_failure:
                return self._fail(move_failure)
            paths[moving_unit.id] = self.unit_system.find_movement_path(moving_unit, target_coord, self.map_tiles)

        stacks = []
        for moving_unit in units:
            quantity = move_quantity if len(units) == 1 and moving_unit.unit_type == UnitType.SOLDIER else moving_unit.quantity
            stack = self.unit_system.split_unit_stack(moving_unit, quantity, self.map_tiles)
            stacks.append((stack, paths[moving_unit.id]))
        action.params["unit_id"] = stacks[0][0].id
        action.params["unit_ids"] = [stack.id for stack, _path in stacks]

        for stack, path in stacks:
            from_tile = self.map_tiles[stack.position]
            from_position = [stack.position.q, stack.position.r]
            if not self.unit_system.move_unit(stack, target_coord, self.map_tiles):
                return self._fail("移动失败")
            self._emit("unit_moved", "单位移动成功",
                       unit_id=stack.id, owner_id=stack.owner.id, quantity=stack.quantity,
                       **{"from": from_position}, to=[target_coord.q, target_coord.r],
                       from_terrain=from_tile.terrain_type.value,
                       to_terrain=self.map_tiles[target_coord].terrain_type.value,
                       remaining_movement=stack.movement_points)
            self._occupy_intermediate_path_tiles(stack, path)

        self._resolve_arrival(target_coord, acting_player)
        self._update_all_visions()
        self._check_game_over()
        return True

    def _resolve_arrival(self, coord: HexCoord, acting_player: Player):
        """结算抵达目标格后的战斗、攻城与占领。"""
        tile = self.map_tiles[coord]
        attackers = [u for u in tile.units if u.owner == acting_player]
        defenders = [u for u in tile.units if u.owner != acting_player]
        if attackers and defenders:
            self.combat_system.resolve_combat(attackers, defenders, coord, self.map_tiles)

        soldiers = [u for u in tile.units if u.owner == acting_player and u.unit_type == UnitType.SOLDIER]
        city = tile.city
        if city and city.owner != acting_player and soldiers:
            old_owner = city.owner
            if self.combat_system.attack_city(soldiers, city, self.map_tiles):
                self._emit("city_captured", f"城市被 {acting_player.name} 占领",
                           city_id=city.id, old_owner_id=old_owner.id, new_owner_id=acting_player.id,
                           position=[coord.q, coord.r])
            else:
                self._emit("siege_failed", f"攻城失败，城市防御降至 {city.defense}",
                           city_id=city.id, defense=city.defense, position=[coord.q, coord.r])

        if self._destroyed:
            self._emit("combat_resolved", f"战斗结束，{len(self._destroyed)} 个单位被消灭",
                       destroyed_unit_ids=sorted(u.id for u in self._destroyed), position=[coord.q, coord.r])
            for unit in self._destroyed:
                self._emit("unit_destroyed", "单位被消灭", unit_id=unit.id, owner_id=unit.owner.id,
                           unit_type=unit.unit_type.value, quantity=unit.quantity)

        survivors = [u for u in tile.units if u.owner == acting_player and u.unit_type == UnitType.SOLDIER]
        if survivors and not (tile.city and tile.city.owner != acting_player):
            self.combat_system.occupy_tile(survivors[0], coord, self.map_tiles)

    def _on_unit_destroyed(self, unit: Unit):
        self._destroyed.append(unit)

    def _occupy_intermediate_path_tiles(self, unit: Unit, path: List[HexCoord]):
        """士兵沿路径占领中间普通地块，不处理终点战斗/攻城。"""
        if unit.unit_type != UnitType.SOLDIER:
            return
        for coord in path[1:-1]:
            tile = self.map_tiles.get(coord)
            if not tile or tile.terrain_type != TerrainType.LAND:
                continue
            if tile.city and tile.city.owner != unit.owner:
                continue
            if any(other.owner != unit.owner for other in tile.units):
                continue
            self.combat_system.occupy_tile(unit, coord, self.map_tiles)

    # ------------------------------------------------------------------ 建城 / 生产
    def _execute_build_city(self, action: GameAction) -> bool:
        unit_id = action.params.get("unit_id")
        if not unit_id:
            return self._fail("建城失败：未指定移民")
        unit = self.unit_system.get_unit_by_id(unit_id)
        acting_player = self.player_system.get_player_by_id(action.player_id)
        if not unit:
            return self._fail("建城失败：未找到该单位")
        if unit.owner != acting_player:
            return self._fail("建城失败：只能使用自己的移民建城")
        if unit.unit_type != UnitType.SETTLER:
            return self._fail("建城失败：只有移民可以建城")

        try:
            city = self.city_system.create_city(unit.owner, unit.position, self.map_tiles)
        except ValueError as error:
            return self._fail(str(error))
        unit.owner.cities.append(city)
        self.unit_system.remove_unit(unit, self.map_tiles)
        self._emit("city_built", f"{city.owner.name} 建立了城市",
                   city_id=city.id, owner_id=city.owner.id, position=[city.center_tile.q, city.center_tile.r])
        self._update_all_visions()
        return True

    def _execute_build_unit(self, action: GameAction) -> bool:
        city_id = action.params.get("city_id")
        unit_type_str = action.params.get("unit_type")
        quantity = max(1, int(action.params.get("quantity", 1) or 1))
        if not city_id:
            return self._fail("生产失败：未指定城市")
        if not unit_type_str:
            return self._fail("生产失败：未指定单位类型")
        try:
            unit_type = UnitType(unit_type_str)
        except ValueError:
            return self._fail("生产失败：未知单位类型")

        city = self.city_system.get_city_by_id(city_id)
        acting_player = self.player_system.get_player_by_id(action.player_id)
        if not city:
            return self._fail("生产失败：未找到该城市")
        if city.owner != acting_player:
            return self._fail("生产失败：只能在自己的城市生产")
        build_failure = self.city_system.get_build_unit_failure_reason(city, unit_type, quantity)
        if build_failure:
            return self._fail(build_failure)

        unit = self.city_system.build_unit(city, unit_type, self.unit_system, self.map_tiles, quantity)
        if not unit:
            return self._fail("生产失败")
        produced = 1 if unit_type == UnitType.SETTLER else quantity
        label = "移民" if unit_type == UnitType.SETTLER else f"士兵 {produced} 名"
        self._emit("unit_produced", f"{city.owner.name} 生产了{label}",
                   unit_id=unit.id, owner_id=city.owner.id, unit_type=unit_type.value, quantity=produced,
                   position=[city.center_tile.q, city.center_tile.r])
        self._update_all_visions()
        return True

    # ------------------------------------------------------------------ 回合
    def _execute_end_turn(self, action: GameAction) -> bool:
        transition = self.turn_system.end_turn(action.player_id, self._on_new_turn)
        if not transition.get("success"):
            return self._fail(str(transition.get("reason", "结束回合失败")))
        self._emit("turn_ended", "回合结束",
                   mode=transition.get("mode", self.turn_system.mode),
                   ended_player_id=transition.get("ended_player_id", action.player_id),
                   next_player_id=transition.get("next_player_id"),
                   turn_advanced=transition.get("turn_advanced", False),
                   ended_player_ids=transition.get("ended_player_ids", []))
        if transition.get("turn_advanced"):
            self._emit_turn_advanced()
        self._check_game_over()
        return True

    def _emit_turn_advanced(self):
        self._emit("turn_advanced", f"进入第 {self.turn_system.current_turn} 回合", turn=self.turn_system.current_turn)

    def _on_new_turn(self, players: List[Player] = None):
        """玩家回合开始：收入、移动力、城市防御/生产次数、合并士兵栈、刷新视野。"""
        for player in players if players is not None else self.player_system.players:
            income = self.player_system.calculate_income(player, self.map_tiles)
            self.player_system.update_player_gold(player, income)
            self.unit_system.restore_movement_points(player)
            for city in player.cities:
                self.city_system.start_turn(city)
        self.unit_system.merge_compatible_stacks(self.map_tiles)
        self._update_all_visions()

    def calculate_score(self, player: Player) -> int:
        """回合上限判胜使用的分数。"""
        territory = sum(1 for tile in self.map_tiles.values() if tile.owner == player)
        soldiers = sum(unit.quantity for unit in player.units if unit.unit_type == UnitType.SOLDIER)
        return (len(player.cities) * GAME_CONFIG["score_per_city"]
                + territory * GAME_CONFIG["score_per_territory"]
                + soldiers * GAME_CONFIG["score_per_soldier"])

    def _check_game_over(self):
        """统一检查淘汰与游戏结束状态。"""
        if self.game_over:
            return
        self._remove_defeated_players_units()
        if self.turn_system.is_game_over():
            self._finish(self.turn_system.get_winner())
            return
        if self.turn_system.advance_if_all_ended(self._on_new_turn):
            self._emit_turn_advanced()
        if self.turn_system.current_turn > GAME_CONFIG["max_turns"]:
            alive = self.turn_system.alive_players()
            scores = sorted(((self.calculate_score(p), p) for p in alive), key=lambda item: item[0], reverse=True)
            tied = len(scores) > 1 and scores[0][0] == scores[1][0]
            self._finish(None if tied or not scores else scores[0][1])

    def _finish(self, winner: Optional[Player]):
        self.game_over = True
        self.winner = winner
        self._emit("game_over", f"游戏结束，获胜者：{winner.name if winner else '无'}",
                   winner_id=winner.id if winner else None)

    def _remove_defeated_players_units(self):
        """被淘汰（无城市且无移民）的玩家残余单位撤出地图。"""
        for player in self.player_system.players:
            if player.units and not is_player_alive(player):
                for unit in list(player.units):
                    self.unit_system.remove_unit(unit, self.map_tiles)
                self._emit("player_eliminated", f"{player.name} 已被淘汰", player_id=player.id)
                self._update_all_visions()

    def _update_all_visions(self):
        for player in self.player_system.players:
            self.vision_system.update_player_vision(player, self.map_tiles)

    def _build_action_message(self, action: GameAction, success: bool, events: List[ActionEvent]) -> str:
        """生成人类可读的行动结果消息。"""
        if not success:
            return self._last_failure_reason or "行动失败"
        for event_type in PRIORITY_EVENT_TYPES:
            for event in reversed(events):
                if event.event_type == event_type:
                    return event.message
        messages = {
            ActionType.MOVE_UNIT: "单位移动成功",
            ActionType.BUILD_CITY: "城市建立成功",
            ActionType.BUILD_UNIT: "单位生产成功",
            ActionType.END_TURN: "回合结束",
        }
        return messages.get(action.action_type, "行动成功")

    # ------------------------------------------------------------------ 查询
    def get_current_player(self) -> Optional[Player]:
        return self.turn_system.get_current_player()

    def get_game_state(self) -> GameState:
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
        filtered_tiles = {}
        for coord, tile in self.map_tiles.items():
            if self.vision_system.is_tile_visible(player, coord):
                filtered_tiles[coord] = tile
            else:
                filtered_tiles[coord] = tile.__class__(coord=tile.coord, terrain_type=tile.terrain_type)
        current_player = self.turn_system.get_current_player()
        return GameState(
            turn=self.turn_system.current_turn,
            current_player_id=current_player.id if current_player else "",
            players=self.player_system.players.copy(),
            map_tiles=filtered_tiles,
            game_over=self.game_over,
            winner=self.winner
        )
