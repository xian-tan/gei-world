"""
AI 玩家系统：基于效用评分的策略 AI。

每次 get_action 只返回一个行动，调用方循环提交直到 AI 返回 END_TURN。
决策顺序：移民（选址/建城）→ 城市生产 → 士兵（攻击/攻城/防守/集结/扩张/探索）。
AI 只使用自身可见/已探索的信息判断敌情。
"""
import random
import zlib
from typing import Callable, Dict, List, Optional, Set

from ..config import CITY_CONFIG, UNIT_CONFIG
from ..models import ActionResult, ActionType, City, GameAction, HexCoord, Player, TerrainType, Unit, UnitType

DIFFICULTY_PROFILES = {
    "easy": {"target_cities": 2, "noise": 0.35, "attack_margin": 2, "gold_bonus": 0, "skip_attack_chance": 0.4},
    "normal": {"target_cities": 3, "noise": 0.1, "attack_margin": 1, "gold_bonus": 0, "skip_attack_chance": 0.0},
    "hard": {"target_cities": 4, "noise": 0.0, "attack_margin": 1, "gold_bonus": 2, "skip_attack_chance": 0.0},
}
DIFFICULTY_ALIASES = {"medium": "normal"}
SITE_SEARCH_RADIUS = 6
MIN_CITY_SPACING = 3
MIN_SITE_AREA = 7
MILITARY_TURN = 25


def normalize_difficulty(difficulty: str) -> str:
    difficulty = DIFFICULTY_ALIASES.get(difficulty, difficulty)
    return difficulty if difficulty in DIFFICULTY_PROFILES else "normal"


class StrategicAI:
    """效用评分 AI。"""

    def __init__(self, player: Player, difficulty: str = "normal", seed: int = None):
        self.player = player
        self.difficulty = normalize_difficulty(difficulty)
        self.profile = DIFFICULTY_PROFILES[self.difficulty]
        self.rng = random.Random(seed)
        self._turn = None
        self._done_units: Set[str] = set()
        self._handled_cities: Set[str] = set()

    # ---------- 回合状态 ----------
    def _sync_turn(self, engine):
        turn = engine.turn_system.current_turn
        if turn != self._turn:
            self._turn = turn
            self._done_units = set()
            self._handled_cities = set()

    def on_action_failed(self, action: GameAction):
        """行动失败时标记对应单位/城市本回合不再尝试。"""
        unit_id = action.params.get("unit_id")
        if unit_id:
            self._done_units.add(unit_id)
        city_id = action.params.get("city_id")
        if city_id:
            self._handled_cities.add(city_id)

    def get_action(self, engine) -> GameAction:
        self._sync_turn(engine)
        for step in (self._settler_action, self._production_action, self._soldier_action):
            action = step(engine)
            if action:
                return action
        return self._end_turn()

    def _end_turn(self) -> GameAction:
        return GameAction(self.player.id, ActionType.END_TURN, {})

    def _jitter(self) -> float:
        return self.rng.uniform(-1, 1) * self.profile["noise"] * 3

    # ---------- 情报 ----------
    def _visible_enemy_units(self, engine) -> List[Unit]:
        vision = self.player.vision_tiles
        return [
            unit for coord in vision
            for unit in engine.map_tiles[coord].units
            if unit.owner != self.player
        ] if vision else []

    def _known_enemy_cities(self, engine) -> List[City]:
        explored = self.player.explored_tiles
        return [city for city in engine.city_system.cities
                if city.owner != self.player and city.center_tile in explored]

    def _enemy_strength_near(self, engine, coord: HexCoord, radius: int) -> int:
        vision = self.player.vision_tiles
        total = 0
        for nearby in coord.within(radius):
            if nearby not in vision or nearby not in engine.map_tiles:
                continue
            total += sum(u.quantity for u in engine.map_tiles[nearby].units
                         if u.owner != self.player and u.unit_type == UnitType.SOLDIER)
        return total

    def _own_strength_near(self, engine, coord: HexCoord, radius: int) -> int:
        total = 0
        for nearby in coord.within(radius):
            tile = engine.map_tiles.get(nearby)
            if tile:
                total += sum(u.quantity for u in tile.units
                             if u.owner == self.player and u.unit_type == UnitType.SOLDIER)
        return total

    def _land_area(self, engine, coord: HexCoord, radius: int = 2) -> int:
        return sum(1 for c in coord.within(radius)
                   if c in engine.map_tiles and engine.map_tiles[c].terrain_type == TerrainType.LAND
                   and engine.map_tiles[c].owner in (None, self.player))

    def _threatened_cities(self, engine) -> List[City]:
        threatened = []
        for city in self.player.cities:
            enemy = self._enemy_strength_near(engine, city.center_tile, 2)
            if enemy and enemy >= self._own_strength_near(engine, city.center_tile, 1) + city.defense:
                threatened.append(city)
        return threatened

    # ---------- 移民 ----------
    def _settler_action(self, engine) -> Optional[GameAction]:
        for settler in [u for u in self.player.units if u.unit_type == UnitType.SETTLER]:
            if settler.id in self._done_units:
                continue
            position = settler.position
            can_build_here = engine.city_system.can_build_city(position, engine.map_tiles, self.player)
            if can_build_here and not self.player.cities:
                return self._build_city(settler)
            site = self._best_site(engine, settler)
            if can_build_here and self._is_good_site(engine, position):
                if site is None or self._site_score(engine, position, 0) >= \
                        self._site_score(engine, site, position.distance_to(site)) - 1.5:
                    return self._build_city(settler)
            if site and site != position and settler.movement_points > 0:
                step = self._step_toward(engine, settler, site, allow_ocean=False)
                if step:
                    return self._move(settler, step)
            if can_build_here and site is None:
                return self._build_city(settler)
            self._done_units.add(settler.id)
        return None

    def _build_city(self, settler: Unit) -> GameAction:
        self._done_units.add(settler.id)
        return GameAction(self.player.id, ActionType.BUILD_CITY, {"unit_id": settler.id})

    def _is_good_site(self, engine, coord: HexCoord) -> bool:
        if self._land_area(engine, coord) < MIN_SITE_AREA:
            return False
        return all(city.center_tile.distance_to(coord) >= MIN_CITY_SPACING for city in engine.city_system.cities)

    def _site_score(self, engine, coord: HexCoord, distance: int) -> float:
        return self._land_area(engine, coord) - 0.8 * distance

    def _best_site(self, engine, settler: Unit) -> Optional[HexCoord]:
        best, best_score = None, None
        for coord in settler.position.within(SITE_SEARCH_RADIUS):
            tile = engine.map_tiles.get(coord)
            if not tile or tile.terrain_type != TerrainType.LAND:
                continue
            if any(u.owner != self.player for u in tile.units):
                continue
            if not engine.city_system.can_build_city(coord, engine.map_tiles, self.player):
                continue
            if not self._is_good_site(engine, coord):
                continue
            score = self._site_score(engine, coord, settler.position.distance_to(coord)) + self._jitter()
            if best_score is None or score > best_score:
                best, best_score = coord, score
        return best

    # ---------- 生产 ----------
    def _production_action(self, engine) -> Optional[GameAction]:
        soldier_cost = UNIT_CONFIG["soldier_cost"]
        settler_cost = UNIT_CONFIG["settler_cost"]
        settlers = sum(1 for u in self.player.units if u.unit_type == UnitType.SETTLER)
        want_expand = (len(self.player.cities) + settlers < self.profile["target_cities"]
                       and engine.turn_system.current_turn < 60)
        threatened = {city.id for city in self._threatened_cities(engine)}

        for city in self.player.cities:
            if city.id in self._handled_cities or not engine.city_system.can_produce_this_turn(city):
                continue
            self._handled_cities.add(city.id)
            gold = self.player.gold
            if city.id in threatened and gold >= soldier_cost:
                return self._build(city, UnitType.SOLDIER, gold // soldier_cost)
            if want_expand and settlers == 0:
                if gold >= settler_cost:
                    return self._build(city, UnitType.SETTLER, 1)
                surplus = gold - settler_cost
                if surplus >= soldier_cost:
                    return self._build(city, UnitType.SOLDIER, surplus // soldier_cost)
                continue
            if gold >= soldier_cost:
                return self._build(city, UnitType.SOLDIER, gold // soldier_cost)
        return None

    def _build(self, city: City, unit_type: UnitType, quantity: int) -> GameAction:
        return GameAction(self.player.id, ActionType.BUILD_UNIT,
                          {"city_id": city.id, "unit_type": unit_type.value, "quantity": max(1, quantity)})

    # ---------- 士兵 ----------
    def _soldier_action(self, engine) -> Optional[GameAction]:
        stacks = [u for u in self.player.units
                  if u.unit_type == UnitType.SOLDIER and u.movement_points > 0 and u.id not in self._done_units]
        stacks.sort(key=lambda u: -u.quantity)
        for stack in stacks:
            action = self._soldier_move(engine, stack)
            if action:
                return action
            self._done_units.add(stack.id)
        return None

    def _soldier_move(self, engine, stack: Unit) -> Optional[GameAction]:
        reachable = set(engine.unit_system.get_reachable_tiles(stack, engine.map_tiles))
        if not reachable:
            return None
        options = []  # (value, target_coord, is_direct)
        margin = self.profile["attack_margin"]
        may_attack = self.rng.random() >= self.profile["skip_attack_chance"]
        vision = self.player.vision_tiles

        for coord in reachable:
            if coord not in vision:
                continue
            tile = engine.map_tiles[coord]
            enemy_units = [u for u in tile.units if u.owner != self.player]
            enemy_soldiers = sum(u.quantity for u in enemy_units if u.unit_type == UnitType.SOLDIER)
            if tile.city and tile.city.owner != self.player:
                if may_attack and stack.quantity - enemy_soldiers > tile.city.defense + margin - 1:
                    options.append((20 + tile.city.defense, coord, True))
            elif enemy_units:
                if enemy_soldiers == 0:
                    options.append((12, coord, True))
                elif may_attack and stack.quantity > enemy_soldiers + margin - 1:
                    options.append((8 + enemy_soldiers, coord, True))

        threatened = self._threatened_cities(engine)
        if threatened:
            city = min(threatened, key=lambda c: c.center_tile.distance_to(stack.position))
            if stack.position != city.center_tile and city.center_tile.distance_to(stack.position) <= 4:
                options.append((10, city.center_tile, False))

        military_phase = (len(self.player.cities) >= self.profile["target_cities"]
                          or engine.turn_system.current_turn >= MILITARY_TURN)
        enemy_cities = self._known_enemy_cities(engine)
        if military_phase and enemy_cities and self.player.cities:
            target_city = min(enemy_cities, key=lambda c: c.center_tile.distance_to(stack.position))
            needed = target_city.defense + margin + self._enemy_strength_near(engine, target_city.center_tile, 0)
            army = self._own_strength_near(engine, stack.position, 1)
            if army >= needed or stack.quantity >= needed:
                options.append((6, target_city.center_tile, False))
            else:
                rally = min(self.player.cities, key=lambda c: c.center_tile.distance_to(target_city.center_tile))
                if stack.position != rally.center_tile:
                    options.append((4, rally.center_tile, False))

        expand = self._expansion_target(engine, stack, reachable)
        if expand:
            options.append((3, expand, True))

        explore = self._exploration_target(engine, stack)
        if explore:
            options.append((1, explore, False))

        options.sort(key=lambda option: option[0] + self._jitter(), reverse=True)
        for _value, target, direct in options:
            if direct and target in reachable:
                return self._move(stack, target)
            step = self._step_toward(engine, stack, target, allow_ocean=True, reachable=reachable)
            if step:
                return self._move(stack, step)
        return None

    def _expansion_target(self, engine, stack: Unit, reachable: Set[HexCoord]) -> Optional[HexCoord]:
        economic = {c for city in self.player.cities for c in city.center_tile.within(CITY_CONFIG["economic_radius"])}
        best = None
        for coord in reachable:
            tile = engine.map_tiles[coord]
            if coord not in economic or tile.terrain_type != TerrainType.LAND or tile.owner is not None or tile.units:
                continue
            if not any(engine.map_tiles.get(n) and engine.map_tiles[n].owner == self.player for n in coord.neighbors()):
                continue
            if best is None or coord.distance_to(stack.position) < best.distance_to(stack.position):
                best = coord
        return best

    def _exploration_target(self, engine, stack: Unit) -> Optional[HexCoord]:
        explored = self.player.explored_tiles
        unexplored = [c for c in engine.map_tiles if c not in explored]
        if not unexplored:
            return None
        return min(unexplored, key=lambda c: (c.distance_to(stack.position), c.q, c.r))

    def _step_toward(self, engine, unit: Unit, target: HexCoord, allow_ocean: bool,
                     reachable: Optional[Set[HexCoord]] = None) -> Optional[HexCoord]:
        if reachable is None:
            reachable = set(engine.unit_system.get_reachable_tiles(unit, engine.map_tiles))
        current = unit.position.distance_to(target)
        best, best_distance = None, current
        for coord in reachable:
            tile = engine.map_tiles[coord]
            if not allow_ocean and tile.terrain_type == TerrainType.OCEAN:
                continue
            if coord != target and (tile.city and tile.city.owner != self.player
                                    or any(u.owner != self.player for u in tile.units)):
                continue
            distance = coord.distance_to(target)
            if distance < best_distance or (distance == best_distance and best is not None
                                            and (coord.q, coord.r) < (best.q, best.r)):
                best, best_distance = coord, distance
        return best

    def _move(self, unit: Unit, target: HexCoord) -> GameAction:
        return GameAction(self.player.id, ActionType.MOVE_UNIT, {
            "unit_id": unit.id,
            "target": [target.q, target.r],
            "move_quantity": unit.quantity,
        })


class AIManager:
    """AI管理器"""

    def __init__(self, seed: int = None):
        self.ai_players: Dict[str, StrategicAI] = {}
        self._seed = seed
        self._bonus_turns: Dict[str, int] = {}

    def clear(self):
        """清空 AI 玩家。"""
        self.ai_players.clear()
        self._bonus_turns.clear()

    def add_ai_player(self, player: Player, ai_type: str = "strategic", difficulty: str = "normal"):
        """添加AI玩家；ai_type 保留兼容，所有 AI 使用同一策略，难度决定强度。"""
        seed = None if self._seed is None else zlib.crc32(f"{self._seed}:{player.id}".encode())
        self.ai_players[player.id] = StrategicAI(player, difficulty, seed)

    def get_ai_action(self, player_id: str, engine) -> Optional[GameAction]:
        """获取AI行动"""
        ai = self.ai_players.get(player_id)
        return ai.get_action(engine) if ai else None

    def is_ai_player(self, player_id: str) -> bool:
        """检查是否是AI玩家"""
        return player_id in self.ai_players

    def play_turn(self, player_id: str, engine, submit: Callable[[GameAction], ActionResult],
                  on_result: Optional[Callable[[GameAction, ActionResult], None]] = None,
                  max_actions: int = 60) -> List[ActionResult]:
        """让 AI 完成本回合：循环取行动并提交，直到结束回合。"""
        ai = self.ai_players.get(player_id)
        if not ai:
            return []
        turn = engine.turn_system.current_turn
        bonus = ai.profile["gold_bonus"]
        if bonus and self._bonus_turns.get(player_id) != turn:
            self._bonus_turns[player_id] = turn
            ai.player.gold += bonus

        results = []
        for _ in range(max_actions):
            if engine.game_over or not engine.turn_system.can_player_act(player_id):
                return results
            action = ai.get_action(engine)
            result = submit(action)
            results.append(result)
            if on_result:
                on_result(action, result)
            if action.action_type == ActionType.END_TURN:
                return results
            if not result.success:
                ai.on_action_failed(action)
        if not engine.game_over and engine.turn_system.can_player_act(player_id):
            action = GameAction(player_id, ActionType.END_TURN, {})
            result = submit(action)
            results.append(result)
            if on_result:
                on_result(action, result)
        return results
