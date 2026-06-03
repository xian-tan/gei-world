"""
回合系统 - 负责回合管理和流程控制
"""
from typing import Dict, List, Optional, Set
from ..models import Player


class TurnSystem:
    """回合系统，支持严格轮流回合和同时回合制。"""
    MODE_SEQUENTIAL = "sequential"
    MODE_SIMULTANEOUS = "simultaneous"
    SUPPORTED_MODES = {MODE_SEQUENTIAL, MODE_SIMULTANEOUS}

    def __init__(self, mode: str = MODE_SEQUENTIAL):
        self.current_turn = 1
        self.turn_number = 1  # 添加turn_number属性用于UI显示
        self.current_player_index = 0
        self.players: List[Player] = []
        self.mode = self._normalize_mode(mode)
        self.ended_player_ids: Set[str] = set()

    def _normalize_mode(self, mode: str) -> str:
        """校验并标准化回合模式。"""
        mode = mode or self.MODE_SEQUENTIAL
        if mode not in self.SUPPORTED_MODES:
            raise ValueError(f"未知回合模式: {mode}")
        return mode

    def initialize(self, players: List[Player], mode: Optional[str] = None):
        """初始化回合系统。"""
        if mode is not None:
            self.mode = self._normalize_mode(mode)
        self.players = players
        self.current_turn = 1
        self.turn_number = 1
        self.current_player_index = 0
        self.ended_player_ids = set()

    def set_mode(self, mode: str):
        """切换回合模式，并清理模式相关临时状态。"""
        self.mode = self._normalize_mode(mode)
        self.current_player_index = min(self.current_player_index, max(0, len(self.players) - 1))
        self.ended_player_ids = set()

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """根据玩家 ID 获取玩家。"""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def get_current_player(self) -> Optional[Player]:
        """获取当前行动玩家；同时回合制下返回首个未结束的存活玩家用于兼容旧 UI。"""
        if not self.players:
            return None
        if self.mode == self.MODE_SIMULTANEOUS:
            actionable_players = self.get_actionable_players()
            return actionable_players[0] if actionable_players else self.players[0]
        return self.players[self.current_player_index]

    def get_actionable_players(self) -> List[Player]:
        """获取当前允许提交行动的玩家列表。"""
        if self.mode == self.MODE_SEQUENTIAL:
            current_player = self.get_current_player()
            return [current_player] if current_player and self._player_has_assets(current_player) else []
        return [
            player for player in self.players
            if self._player_has_assets(player) and player.id not in self.ended_player_ids
        ]

    def can_player_act(self, player_id: str) -> bool:
        """判断玩家当前是否可以行动。"""
        player = self.get_player_by_id(player_id)
        if not player or not self._player_has_assets(player):
            return False
        if self.mode == self.MODE_SEQUENTIAL:
            current_player = self.get_current_player()
            return bool(current_player and current_player.id == player_id)
        return player_id not in self.ended_player_ids

    def get_action_denial_reason(self, player_id: str) -> str:
        """返回玩家当前不能行动的原因。"""
        player = self.get_player_by_id(player_id)
        if not player:
            return "玩家不存在"
        if not self._player_has_assets(player):
            return "该玩家已被淘汰，无法行动"
        if self.mode == self.MODE_SEQUENTIAL:
            return "还没轮到该玩家行动"
        if player_id in self.ended_player_ids:
            return "该玩家本回合已结束"
        return "该玩家当前不能行动"

    def end_turn(self, player_system, unit_system, vision_system, map_tiles: dict,
                 player_id: Optional[str] = None) -> Dict[str, object]:
        """结束指定玩家回合。"""
        if self.mode == self.MODE_SEQUENTIAL:
            return self._end_sequential_turn(player_system, unit_system, vision_system, map_tiles, player_id)
        return self._end_simultaneous_turn(player_system, unit_system, vision_system, map_tiles, player_id)

    def _end_sequential_turn(self, player_system, unit_system, vision_system, map_tiles: dict,
                             player_id: Optional[str]) -> Dict[str, object]:
        current_player = self.get_current_player()
        if not current_player:
            return {"success": False, "reason": "没有当前玩家"}
        if player_id and current_player.id != player_id:
            return {"success": False, "reason": "还没轮到该玩家行动"}

        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        turn_advanced = False
        if self.current_player_index == 0:
            turn_advanced = True
            self._advance_full_turn(player_system, unit_system, vision_system, map_tiles)

        next_player = self.get_current_player()
        return {
            "success": True,
            "mode": self.mode,
            "ended_player_id": current_player.id,
            "turn_advanced": turn_advanced,
            "turn": self.current_turn,
            "next_player_id": next_player.id if next_player else None,
            "ended_player_ids": []
        }

    def _end_simultaneous_turn(self, player_system, unit_system, vision_system, map_tiles: dict,
                               player_id: Optional[str]) -> Dict[str, object]:
        if not player_id:
            return {"success": False, "reason": "未指定结束回合玩家"}
        if not self.can_player_act(player_id):
            return {"success": False, "reason": self.get_action_denial_reason(player_id)}

        self.ended_player_ids.add(player_id)
        active_player_ids = {player.id for player in self.players if self._player_has_assets(player)}
        turn_advanced = bool(active_player_ids and active_player_ids.issubset(self.ended_player_ids))
        if turn_advanced:
            self._advance_full_turn(player_system, unit_system, vision_system, map_tiles)

        next_player = self.get_current_player()
        return {
            "success": True,
            "mode": self.mode,
            "ended_player_id": player_id,
            "turn_advanced": turn_advanced,
            "turn": self.current_turn,
            "next_player_id": next_player.id if next_player else None,
            "ended_player_ids": sorted(self.ended_player_ids)
        }

    def _advance_full_turn(self, player_system, unit_system, vision_system, map_tiles: dict):
        """推进到下一整轮并执行回合开始结算。"""
        self.current_turn += 1
        self.turn_number += 1
        self.current_player_index = 0
        self.ended_player_ids = set()
        self._start_new_turn(player_system, unit_system, vision_system, map_tiles)

    def _start_new_turn(self, player_system, unit_system, vision_system, map_tiles: dict):
        """开始新回合。"""
        for player in self.players:
            income = player_system.calculate_income(player, map_tiles)
            player_system.update_player_gold(player, income)
            unit_system.restore_movement_points(player)

        unit_system.merge_compatible_stacks(map_tiles)

        for player in self.players:
            vision_system.update_player_vision(player, map_tiles)

    def is_game_over(self) -> bool:
        """检查游戏是否结束。"""
        active_players = [p for p in self.players if self._player_has_assets(p)]
        return len(active_players) <= 1

    def get_winner(self) -> Optional[Player]:
        """获取胜利者。"""
        active_players = [p for p in self.players if self._player_has_assets(p)]
        return active_players[0] if len(active_players) == 1 else None

    def _player_has_assets(self, player: Player) -> bool:
        """玩家仍有城市或单位时，尚未被淘汰。"""
        return bool(player.cities or player.units)

    def get_turn_info(self) -> dict:
        """获取回合信息。"""
        return self.get_turn_status()

    def get_turn_status(self) -> dict:
        """获取适合 UI/网络层展示的回合状态。"""
        current_player = self.get_current_player()
        return {
            "turn": self.current_turn,
            "turn_number": self.turn_number,
            "mode": self.mode,
            "current_player": current_player,
            "current_player_id": current_player.id if current_player else None,
            "total_players": len(self.players),
            "ended_player_ids": sorted(self.ended_player_ids),
            "actionable_player_ids": [player.id for player in self.get_actionable_players()]
        }
