"""
AI玩家系统
"""
import random
from typing import Optional, List
from ..models import Player, GameAction, ActionType, UnitType, HexCoord
from ..game_engine import GameEngine
from ..config import CITY_CONFIG


class AIPlayer:
    """AI玩家基类"""
    
    def __init__(self, player: Player, difficulty: str = "easy"):
        self.player = player
        self.difficulty = difficulty
    
    def get_action(self, engine: GameEngine) -> Optional[GameAction]:
        """获取AI行动"""
        raise NotImplementedError


class SimpleAI(AIPlayer):
    """简单AI实现"""
    
    def get_action(self, engine: GameEngine) -> Optional[GameAction]:
        """简单AI决策"""
        # 优先级策略：
        # 1. 用移民建城
        # 2. 在城市建造单位
        # 3. 移动士兵探索或攻击
        # 4. 结束回合
        
        # 尝试建城
        action = self._try_build_city(engine)
        if action:
            return action
        
        # 尝试建造单位
        action = self._try_build_units(engine)
        if action:
            return action
        
        # 尝试移动单位
        action = self._try_move_units(engine)
        if action:
            return action
        
        # 默认结束回合
        return GameAction(
            player_id=self.player.id,
            action_type=ActionType.END_TURN,
            params={}
        )
    
    def _try_build_city(self, engine: GameEngine) -> Optional[GameAction]:
        """尝试建城"""
        settlers = [unit for unit in self.player.units 
                   if unit.unit_type == UnitType.SETTLER]
        
        for settler in settlers:
            # 检查是否可以在当前位置建城
            try:
                if engine.city_system.can_build_city(settler.position, engine.map_tiles, settler.owner):
                    return GameAction(
                        player_id=self.player.id,
                        action_type=ActionType.BUILD_CITY,
                        params={"unit_id": settler.id}
                    )
            except:
                continue
        
        return None
    
    def _try_build_units(self, engine: GameEngine) -> Optional[GameAction]:
        """尝试建造单位"""
        for city in self.player.cities:
            # 如果金币足够，优先建造士兵
            if self.player.gold >= 30:  # 士兵成本
                if engine.city_system.can_build_unit(city, UnitType.SOLDIER):
                    return GameAction(
                        player_id=self.player.id,
                        action_type=ActionType.BUILD_UNIT,
                        params={
                            "city_id": city.id,
                            "unit_type": UnitType.SOLDIER.value
                        }
                    )
            
            # 如果金币更多，建造移民
            if self.player.gold >= 50 and len(self.player.cities) < 3:
                if engine.city_system.can_build_unit(city, UnitType.SETTLER):
                    return GameAction(
                        player_id=self.player.id,
                        action_type=ActionType.BUILD_UNIT,
                        params={
                            "city_id": city.id,
                            "unit_type": UnitType.SETTLER.value
                        }
                    )
        
        return None
    
    def _try_move_units(self, engine: GameEngine) -> Optional[GameAction]:
        """尝试移动单位"""
        # 随机选择一个可移动的单位
        movable_units = [unit for unit in self.player.units 
                        if unit.movement_points > 0]
        
        if not movable_units:
            return None
        
        unit = random.choice(movable_units)
        
        # 寻找合适的移动目标
        target = self._find_move_target(unit, engine)
        if target:
            return GameAction(
                player_id=self.player.id,
                action_type=ActionType.MOVE_UNIT,
                params={
                    "unit_id": unit.id,
                    "target": [target.q, target.r]
                }
            )
        
        return None
    
    def _find_move_target(self, unit, engine: GameEngine) -> Optional[HexCoord]:
        """为单位寻找移动目标"""
        valid_targets = engine.unit_system.get_reachable_tiles(unit, engine.map_tiles)
        
        if not valid_targets:
            return None
        
        # 简单策略：随机选择
        return random.choice(valid_targets)


class AggressiveAI(SimpleAI):
    """激进AI - 更倾向于军事行动"""
    
    def _try_build_units(self, engine: GameEngine) -> Optional[GameAction]:
        """优先建造士兵"""
        for city in self.player.cities:
            # 优先建造士兵
            if self.player.gold >= 30:
                if engine.city_system.can_build_unit(city, UnitType.SOLDIER):
                    return GameAction(
                        player_id=self.player.id,
                        action_type=ActionType.BUILD_UNIT,
                        params={
                            "city_id": city.id,
                            "unit_type": UnitType.SOLDIER.value
                        }
                    )
        
        # 调用父类方法处理移民
        return super()._try_build_units(engine)
    
    def _find_move_target(self, unit, engine: GameEngine) -> Optional[HexCoord]:
        """寻找攻击目标"""
        if unit.unit_type != UnitType.SOLDIER:
            return super()._find_move_target(unit, engine)
        
        reachable_tiles = engine.unit_system.get_reachable_tiles(unit, engine.map_tiles)
        if not reachable_tiles:
            return None
        
        enemy_unit_target = self._find_reachable_enemy_unit(reachable_tiles, engine)
        if enemy_unit_target:
            return enemy_unit_target
        
        city_attack_target = self._find_reachable_capturable_city(unit, reachable_tiles, engine)
        if city_attack_target:
            return city_attack_target
        
        enemy_city = self._find_nearest_enemy_city(unit.position, engine)
        if enemy_city:
            return self._find_best_staging_tile(enemy_city.center_tile, reachable_tiles, engine)
        
        enemy_territory_target = self._find_reachable_enemy_territory(reachable_tiles, engine)
        if enemy_territory_target:
            return enemy_territory_target
        
        # 如果没有敌方目标，随机移动
        return super()._find_move_target(unit, engine)
    
    def _find_reachable_enemy_unit(self, reachable_tiles, engine: GameEngine) -> Optional[HexCoord]:
        """寻找可达的敌方单位。"""
        for coord in reachable_tiles:
            tile = engine.map_tiles.get(coord)
            if tile and any(enemy.owner != self.player for enemy in tile.units):
                return coord
        return None
    
    def _find_reachable_capturable_city(self, unit, reachable_tiles, engine: GameEngine) -> Optional[HexCoord]:
        """如果兵力足够，寻找可直接攻占的敌方城市。"""
        for coord in reachable_tiles:
            tile = engine.map_tiles.get(coord)
            if not tile or not tile.city or tile.city.owner == self.player:
                continue
            attacking_soldiers = [
                other for other in tile.units
                if other.owner == self.player and other.unit_type == UnitType.SOLDIER
            ]
            if unit not in attacking_soldiers:
                attacking_soldiers.append(unit)
            if len(attacking_soldiers) >= CITY_CONFIG["defense_value"]:
                return coord
        return None
    
    def _find_nearest_enemy_city(self, position: HexCoord, engine: GameEngine):
        """寻找最近的敌方城市。"""
        enemy_cities = [city for city in engine.city_system.cities if city.owner != self.player]
        if not enemy_cities:
            return None
        return min(enemy_cities, key=lambda city: position.distance_to(city.center_tile))
    
    def _find_best_staging_tile(self, target: HexCoord, reachable_tiles, engine: GameEngine) -> Optional[HexCoord]:
        """向敌方城市集结，避免兵力不足时直接送死攻城。"""
        candidates = []
        for coord in reachable_tiles:
            tile = engine.map_tiles.get(coord)
            if not tile:
                continue
            if tile.city and tile.city.owner != self.player:
                continue
            candidates.append(coord)
        if not candidates:
            return None
        return min(candidates, key=lambda coord: coord.distance_to(target))
    
    def _find_reachable_enemy_territory(self, reachable_tiles, engine: GameEngine) -> Optional[HexCoord]:
        """寻找可达的敌方领土。"""
        enemy_tiles = [
            coord for coord in reachable_tiles
            if engine.map_tiles.get(coord)
            and engine.map_tiles[coord].owner
            and engine.map_tiles[coord].owner != self.player
        ]
        return enemy_tiles[0] if enemy_tiles else None


class AIManager:
    """AI管理器"""
    
    def __init__(self):
        self.ai_players = {}
    
    def clear(self):
        """清空 AI 玩家。"""
        self.ai_players.clear()
    
    def add_ai_player(self, player: Player, ai_type: str = "simple", difficulty: str = "easy"):
        """添加AI玩家"""
        if ai_type == "simple":
            ai = SimpleAI(player, difficulty)
        elif ai_type == "aggressive":
            ai = AggressiveAI(player, difficulty)
        else:
            ai = SimpleAI(player, difficulty)
        
        self.ai_players[player.id] = ai
    
    def get_ai_action(self, player_id: str, engine: GameEngine) -> Optional[GameAction]:
        """获取AI行动"""
        ai = self.ai_players.get(player_id)
        if ai:
            return ai.get_action(engine)
        return None
    
    def is_ai_player(self, player_id: str) -> bool:
        """检查是否是AI玩家"""
        return player_id in self.ai_players
