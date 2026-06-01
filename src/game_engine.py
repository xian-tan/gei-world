"""
主要游戏引擎 - 协调所有系统
"""
import random
from typing import List, Optional, Dict, Any

from .models import (Player, GameAction, ActionType, GameState, 
                     UnitType, HexCoord, TerrainType)
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
        for player in players:
            spawn_tile = self.map_system.get_random_land_tile()
            if spawn_tile:
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
    
    def execute_action(self, action: GameAction) -> bool:
        """执行游戏行动"""
        if not self.game_started or self.game_over:
            return False
        
        # 验证是否是当前玩家
        current_player = self.turn_system.get_current_player()
        if not current_player or current_player.id != action.player_id:
            return False
        
        # 根据行动类型执行
        if action.action_type == ActionType.MOVE_UNIT:
            return self._execute_move_unit(action)
        elif action.action_type == ActionType.BUILD_CITY:
            return self._execute_build_city(action)
        elif action.action_type == ActionType.BUILD_UNIT:
            return self._execute_build_unit(action)
        elif action.action_type == ActionType.END_TURN:
            return self._execute_end_turn(action)
        
        return False
    
    def _execute_move_unit(self, action: GameAction) -> bool:
        """执行移动单位行动"""
        unit_id = action.params.get("unit_id")
        target = action.params.get("target")
        
        if not unit_id or not target:
            return False
        
        unit = self.unit_system.get_unit_by_id(unit_id)
        if not unit:
            return False
        
        acting_player = unit.owner
        target_coord = HexCoord(target[0], target[1])
        
        # 执行移动
        if self.unit_system.move_unit(unit, target_coord, self.map_tiles):
            # 检查是否需要战斗
            if self.combat_system.check_for_combat(target_coord, self.map_tiles):
                self._resolve_combat_at_position(target_coord)
            
            target_tile = self.map_tiles.get(target_coord)
            unit = self.unit_system.get_unit_by_id(unit_id)
            if not unit or not target_tile or unit not in target_tile.units:
                self._update_all_visions()
                self._check_game_over()
                return True
            
            # 士兵进入敌方城市中心时触发攻城
            if (unit.unit_type == UnitType.SOLDIER and target_tile.city and
                    target_tile.city.owner != unit.owner):
                attacking_units = [u for u in target_tile.units if u.owner == acting_player]
                self.combat_system.attack_city(attacking_units, target_tile.city, self.map_tiles)
                self._sync_unit_registry()
                unit = self.unit_system.get_unit_by_id(unit_id)
            
            # 如果是士兵，尝试占领普通地块
            if unit and unit.unit_type == UnitType.SOLDIER:
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
            return False
        
        unit = self.unit_system.get_unit_by_id(unit_id)
        current_player = self.turn_system.get_current_player()
        if not unit or unit.owner != current_player or unit.unit_type != UnitType.SETTLER:
            return False
        
        # 建城
        try:
            city = self.city_system.create_city(unit.owner, unit.position, self.map_tiles)
            unit.owner.cities.append(city)
            
            # 移除移民
            self.unit_system.remove_unit(unit, self.map_tiles)
            
            # 更新视野
            self._update_all_visions()
            return True
        except ValueError:
            return False
    
    def _execute_build_unit(self, action: GameAction) -> bool:
        """执行建造单位行动"""
        city_id = action.params.get("city_id")
        unit_type_str = action.params.get("unit_type")
        
        if not city_id or not unit_type_str:
            return False
        
        try:
            unit_type = UnitType(unit_type_str)
        except ValueError:
            return False
        
        city = self.city_system.get_city_by_id(city_id)
        current_player = self.turn_system.get_current_player()
        if not city or city.owner != current_player:
            return False
        
        # 建造单位
        unit = self.city_system.build_unit(city, unit_type, self.unit_system, self.map_tiles)
        if unit:
            self._update_all_visions()
            return True
        return False
    
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
    
    def _resolve_combat_at_position(self, position: HexCoord):
        """解决指定位置的战斗"""
        tile = self.map_tiles.get(position)
        if not tile or len(tile.units) < 2:
            return
        
        # 按玩家分组单位
        player_units = {}
        for unit in tile.units:
            if unit.owner not in player_units:
                player_units[unit.owner] = []
            player_units[unit.owner].append(unit)
        
        if len(player_units) < 2:
            return
        
        # 简单实现：取前两个玩家的单位进行战斗
        players = list(player_units.keys())
        attacking_units = player_units[players[0]]
        defending_units = player_units[players[1]]
        
        # 解决战斗
        survivors_a, survivors_d = self.combat_system.resolve_combat(
            attacking_units, defending_units, position, self.map_tiles
        )
        
        # 更新地块单位
        tile.units = survivors_a + survivors_d
        self._sync_unit_registry()
    
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
