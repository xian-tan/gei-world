"""
回合系统 - 负责回合顺序和回合模式。

回合开始时的经济、移动力、城市结算由 GameEngine 通过 on_new_turn 回调完成，
本模块只维护"谁可以行动、何时进入下一整轮"。
"""
from typing import Callable, Dict, List, Optional, Set
from ..models import Player, UnitType


def is_player_alive(player: Player) -> bool:
    """玩家仍拥有城市或移民（还能重新建城）时未被淘汰。"""
    if player.cities:
        return True
    return any(unit.unit_type == UnitType.SETTLER for unit in player.units)


class TurnSystem:
    """回合系统，支持严格轮流回合和同时回合制。"""
    MODE_SEQUENTIAL = "sequential"
    MODE_SIMULTANEOUS = "simultaneous"
    SUPPORTED_MODES = {MODE_SEQUENTIAL, MODE_SIMULTANEOUS}

    def __init__(self, mode: str = MODE_SEQUENTIAL):
        self.current_turn = 1
        self.turn_number = 1
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

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """根据玩家 ID 获取玩家。"""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def alive_players(self) -> List[Player]:
        return [player for player in self.players if is_player_alive(player)]

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
            return [current_player] if current_player and is_player_alive(current_player) else []
        return [
            player for player in self.players
            if is_player_alive(player) and player.id not in self.ended_player_ids
        ]

    def can_player_act(self, player_id: str) -> bool:
        """判断玩家当前是否可以行动。"""
        player = self.get_player_by_id(player_id)
        if not player or not is_player_alive(player):
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
        if not is_player_alive(player):
            return "该玩家已被淘汰，无法行动"
        if self.mode == self.MODE_SEQUENTIAL:
            return "还没轮到该玩家行动"
        if player_id in self.ended_player_ids:
            return "该玩家本回合已结束"
        return "该玩家当前不能行动"

    def end_turn(self, player_id: Optional[str] = None,
                 on_new_turn: Optional[Callable[[], None]] = None) -> Dict[str, object]:
        """结束指定玩家回合；进入新一整轮时调用 on_new_turn。"""
        if self.mode == self.MODE_SEQUENTIAL:
            return self._end_sequential_turn(player_id, on_new_turn)
        return self._end_simultaneous_turn(player_id, on_new_turn)

    def _end_sequential_turn(self, player_id: Optional[str],
                             on_new_turn: Optional[Callable[[], None]]) -> Dict[str, object]:
        current_player = self.get_current_player()
        if not current_player:
            return {"success": False, "reason": "没有当前玩家"}
        if player_id and current_player.id != player_id:
            return {"success": False, "reason": "还没轮到该玩家行动"}

        turn_advanced = False
        for _ in range(len(self.players)):
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            if self.current_player_index == 0:
                turn_advanced = True
                self._advance_full_turn(on_new_turn)
            if is_player_alive(self.players[self.current_player_index]):
                break

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

    def _end_simultaneous_turn(self, player_id: Optional[str],
                               on_new_turn: Optional[Callable[[], None]]) -> Dict[str, object]:
        if not player_id:
            return {"success": False, "reason": "未指定结束回合玩家"}
        if not self.can_player_act(player_id):
            return {"success": False, "reason": self.get_action_denial_reason(player_id)}

        self.ended_player_ids.add(player_id)
        turn_advanced = self.advance_if_all_ended(on_new_turn)
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

    def advance_if_all_ended(self, on_new_turn: Optional[Callable[[], None]] = None) -> bool:
        """同时回合：所有存活玩家都已结束时推进整轮。"""
        if self.mode != self.MODE_SIMULTANEOUS:
            return False
        active_player_ids = {player.id for player in self.alive_players()}
        if active_player_ids and active_player_ids.issubset(self.ended_player_ids):
            self._advance_full_turn(on_new_turn)
            return True
        return False

    def _advance_full_turn(self, on_new_turn: Optional[Callable[[], None]]):
        """推进到下一整轮并执行回合开始结算。"""
        self.current_turn += 1
        self.turn_number += 1
        self.ended_player_ids = set()
        if on_new_turn:
            on_new_turn()

    def is_game_over(self) -> bool:
        """检查是否只剩一名存活玩家。"""
        return len(self.alive_players()) <= 1

    def get_winner(self) -> Optional[Player]:
        """获取唯一存活玩家。"""
        alive = self.alive_players()
        return alive[0] if len(alive) == 1 else None

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
