"""
AI玩家系统
"""
import random
from typing import Optional, List
from ..models import Player, GameAction, ActionType, UnitType, HexCoord
from ..game_engine import GameEngine


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
        
        # 士兵优先寻找真实可达的敌方目标
        reachable_tiles = engine.unit_system.get_reachable_tiles(unit, engine.map_tiles)
        
        # 寻找敌方单位或领土
        for coord in reachable_tiles:
            tile = engine.map_tiles.get(coord)
            if tile and tile.terrain_type.value == "land":
                # 检查是否有敌方单位
                if tile.units:
                    for enemy_unit in tile.units:
                        if enemy_unit.owner != self.player:
                            return coord
                
                # 检查是否是敌方领土
                if tile.owner and tile.owner != self.player:
                    return coord
        
        # 如果没有敌方目标，随机移动
        return super()._find_move_target(unit, engine)


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
