"""
游戏会话抽象。

该层用于把 UI 与具体的本地 GameEngine 实例解耦，后续可用同一接口接入网络会话。
"""
from typing import Dict, List, Optional, Protocol, Set

from .game_engine import GameEngine
from .models import ActionResult, GameAction, GameState, HexCoord, Player
from .network_protocol import deserialize_action_result, serialize_action
from .systems.turn_system import TurnSystem


class GameSessionClient(Protocol):
    """UI/网络层面向的游戏会话接口。"""

    @property
    def engine(self) -> GameEngine:
        """当前会话使用的本地引擎；网络会话可返回只读镜像。"""
        ...

    def start_game(self, player_names: List[str], map_seed: int = None,
                   turn_mode: str = TurnSystem.MODE_SEQUENTIAL) -> bool:
        """开始一局游戏。"""
        ...

    def submit_action(self, action: GameAction) -> ActionResult:
        """提交玩家行动。"""
        ...

    def get_turn_status(self) -> Dict[str, object]:
        """获取回合状态。"""
        ...

    def get_controlled_player(self, local_player_id: str = None) -> Optional[Player]:
        """获取当前客户端视角下控制/查看的玩家。"""
        ...

    def can_player_act(self, player_id: str) -> bool:
        """判断玩家当前是否可提交行动。"""
        ...

    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        """获取玩家可见状态。"""
        ...

    def get_visible_tiles(self, player_id: str) -> Set[HexCoord]:
        """获取玩家当前可见地块集合。"""
        ...

    def get_explored_tiles(self, player_id: str) -> Set[HexCoord]:
        """获取玩家已探索地块集合。"""
        ...


class LocalGameSession:
    """本地单机会话，直接包装 GameEngine。"""

    def __init__(self, engine: GameEngine = None):
        self._engine = engine or GameEngine()

    @property
    def engine(self) -> GameEngine:
        return self._engine

    def replace_engine(self, engine: GameEngine):
        """替换当前引擎，主要用于加载存档。"""
        self._engine = engine

    def start_game(self, player_names: List[str], map_seed: int = None,
                   turn_mode: str = TurnSystem.MODE_SEQUENTIAL) -> bool:
        new_engine = GameEngine(turn_mode=turn_mode)
        if not new_engine.initialize_game(player_names, map_seed, turn_mode=turn_mode):
            return False
        self._engine = new_engine
        return True

    def submit_action(self, action: GameAction) -> ActionResult:
        return self._engine.execute_action_with_result(action)

    def get_turn_status(self) -> Dict[str, object]:
        return self._engine.turn_system.get_turn_status()

    def get_controlled_player(self, local_player_id: str = None) -> Optional[Player]:
        turn_system = self._engine.turn_system
        if turn_system.mode == TurnSystem.MODE_SIMULTANEOUS and local_player_id:
            player = self._engine.player_system.get_player_by_id(local_player_id)
            if player:
                return player
        return self._engine.get_current_player()

    def can_player_act(self, player_id: str) -> bool:
        return self._engine.turn_system.can_player_act(player_id)

    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        return self._engine.get_visible_state(player_id)

    def get_visible_tiles(self, player_id: str) -> Set[HexCoord]:
        return self._engine.vision_system.get_visible_tiles(player_id)

    def get_explored_tiles(self, player_id: str) -> Set[HexCoord]:
        return self._engine.vision_system.get_explored_tiles(player_id)


class NetworkGameSession:
    """进程内网络会话骨架，通过 MultiplayerServer 访问服务端权威引擎。"""

    def __init__(self, server, room_id: str, client_id: str):
        self.server = server
        self.room_id = room_id
        self.client_id = client_id

    @property
    def engine(self) -> GameEngine:
        """当前进程内服务端权威引擎；真实网络版可替换为只读镜像。"""
        engine = self.server.get_room_engine(self.room_id)
        return engine or GameEngine()

    @property
    def player_id(self) -> Optional[str]:
        """当前客户端绑定的玩家 ID。"""
        return self.server.get_client_player_id(self.room_id, self.client_id)

    def start_game(self, player_names: List[str] = None, map_seed: int = None,
                   turn_mode: str = TurnSystem.MODE_SIMULTANEOUS) -> bool:
        """启动当前房间。player_names 由房间席位决定，参数仅用于兼容接口。"""
        response = self.server.start_room(self.room_id, map_seed=map_seed, turn_mode=turn_mode)
        return bool(response.get("success"))

    def submit_action(self, action: GameAction) -> ActionResult:
        response = self.server.submit_action(self.room_id, self.client_id, serialize_action(action))
        return deserialize_action_result(response["result"])

    def get_turn_status(self) -> Dict[str, object]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.turn_system.get_turn_status() if engine else {}

    def get_controlled_player(self, local_player_id: str = None) -> Optional[Player]:
        engine = self.server.get_room_engine(self.room_id)
        player_id = self.player_id
        return engine.player_system.get_player_by_id(player_id) if engine and player_id else None

    def can_player_act(self, player_id: str) -> bool:
        engine = self.server.get_room_engine(self.room_id)
        return bool(engine and engine.turn_system.can_player_act(player_id))

    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.get_visible_state(player_id) if engine else None

    def get_visible_tiles(self, player_id: str) -> Set[HexCoord]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.vision_system.get_visible_tiles(player_id) if engine else set()

    def get_explored_tiles(self, player_id: str) -> Set[HexCoord]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.vision_system.get_explored_tiles(player_id) if engine else set()

    def get_player_view(self) -> Dict[str, object]:
        """获取服务端返回的当前玩家安全视图。"""
        return self.server.get_player_view(self.room_id, self.client_id)
