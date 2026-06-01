"""
回合系统 - 负责回合管理和流程控制
"""
from typing import List
from ..models import Player


class TurnSystem:
    """回合系统"""
    def __init__(self):
        self.current_turn = 1
        self.turn_number = 1  # 添加turn_number属性用于UI显示
        self.current_player_index = 0
        self.players: List[Player] = []
    
    def initialize(self, players: List[Player]):
        """初始化回合系统"""
        self.players = players
        self.current_turn = 1
        self.turn_number = 1
        self.current_player_index = 0
    
    def get_current_player(self) -> Player:
        """获取当前行动玩家"""
        if not self.players:
            return None
        return self.players[self.current_player_index]
    
    def end_turn(self, player_system, unit_system, vision_system, map_tiles: dict):
        """结束当前玩家回合"""
        current_player = self.get_current_player()
        if not current_player:
            return
        
        # 切换到下一个玩家
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
          # 如果回到第一个玩家，增加回合数
        if self.current_player_index == 0:
            self.current_turn += 1
            self.turn_number += 1  # 同步更新turn_number
            self._start_new_turn(player_system, unit_system, vision_system, map_tiles)
    
    def _start_new_turn(self, player_system, unit_system, vision_system, map_tiles: dict):
        """开始新回合"""
        # 为所有玩家执行回合开始逻辑
        for player in self.players:
            # 收入结算
            income = player_system.calculate_income(player)
            player_system.update_player_gold(player, income)
            
            # 恢复单位移动力
            unit_system.restore_movement_points(player)
            
            # 更新视野
            vision_system.update_player_vision(player, map_tiles)
    
    def is_game_over(self) -> bool:
        """检查游戏是否结束"""
        active_players = [p for p in self.players if self._player_has_assets(p)]
        return len(active_players) <= 1
    
    def get_winner(self) -> Player:
        """获取胜利者"""
        active_players = [p for p in self.players if self._player_has_assets(p)]
        return active_players[0] if len(active_players) == 1 else None
    
    def _player_has_assets(self, player: Player) -> bool:
        """玩家仍有城市或单位时，尚未被淘汰。"""
        return bool(player.cities or player.units)
    
    def get_turn_info(self) -> dict:
        """获取回合信息"""
        return {
            "turn": self.current_turn,
            "current_player": self.get_current_player(),
            "total_players": len(self.players)
        }
