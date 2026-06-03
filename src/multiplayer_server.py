"""
本机多人服务端权威原型。

该模块只提供进程内房间/席位/权威 GameEngine 管理，不负责 socket 或 HTTP 传输。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from .game_engine import GameEngine
from .models import ActionResult, GameAction
from .network_protocol import (
    deserialize_action,
    serialize_action_result,
    serialize_event,
    serialize_player_view,
    serialize_room_state,
)
from .systems.turn_system import TurnSystem


@dataclass
class PlayerSeat:
    """房间内的玩家席位。"""
    client_id: str
    player_name: str
    player_id: Optional[str] = None
    connected: bool = True


@dataclass
class MultiplayerRoom:
    """多人房间状态。"""
    room_id: str
    max_players: int
    turn_mode: str = TurnSystem.MODE_SIMULTANEOUS
    map_seed: Optional[int] = None
    seats: List[PlayerSeat] = field(default_factory=list)
    engine: Optional[GameEngine] = None
    started: bool = False
    closed: bool = False
    close_reason: str = ""
    event_log: List[Dict[str, object]] = field(default_factory=list)
    next_event_sequence: int = 1

    def get_seat(self, client_id: str) -> Optional[PlayerSeat]:
        for seat in self.seats:
            if seat.client_id == client_id:
                return seat
        return None


class MultiplayerServer:
    """服务端权威房间管理原型。"""

    def __init__(self):
        self.rooms: Dict[str, MultiplayerRoom] = {}
        self._next_room_index = 1
        self._next_client_index = 1

    def create_room(self, host_name: str, max_players: int = 2,
                    turn_mode: str = TurnSystem.MODE_SIMULTANEOUS,
                    map_seed: int = None) -> Dict[str, object]:
        """创建房间并占用第一个席位。"""
        if max_players < 2:
            raise ValueError("房间至少需要 2 名玩家")
        if max_players > 4:
            raise ValueError("当前最多支持 4 名玩家")

        room_id = self._allocate_room_id()
        client_id = self._allocate_client_id()
        room = MultiplayerRoom(
            room_id=room_id,
            max_players=max_players,
            turn_mode=turn_mode,
            map_seed=map_seed,
            seats=[PlayerSeat(client_id=client_id, player_name=host_name)]
        )
        self.rooms[room_id] = room
        return {
            "success": True,
            "room": serialize_room_state(room),
            "client_id": client_id
        }

    def join_room(self, room_id: str, player_name: str) -> Dict[str, object]:
        """加入未开始的房间。"""
        room = self._get_room(room_id)
        if room.closed:
            return self._room_failure(room, room.close_reason or "房间已关闭")
        if room.started:
            return self._failure("房间已开始，无法加入")
        if len(room.seats) >= room.max_players:
            return self._failure("房间已满")
        if any(seat.player_name == player_name for seat in room.seats):
            return self._failure("玩家名称重复")

        client_id = self._allocate_client_id()
        room.seats.append(PlayerSeat(client_id=client_id, player_name=player_name))
        return {
            "success": True,
            "room": serialize_room_state(room),
            "client_id": client_id
        }

    def start_room(self, room_id: str, map_seed: int = None,
                   turn_mode: str = None) -> Dict[str, object]:
        """启动房间，创建服务端唯一权威 GameEngine。"""
        room = self._get_room(room_id)
        if room.closed:
            return self._room_failure(room, room.close_reason or "房间已关闭")
        if room.started:
            return self._failure("房间已经开始")
        if len(room.seats) < 2:
            return self._failure("至少需要 2 名玩家才能开始")

        if map_seed is not None:
            room.map_seed = map_seed
        if turn_mode is not None:
            room.turn_mode = turn_mode

        engine = GameEngine(turn_mode=room.turn_mode)
        player_names = [seat.player_name for seat in room.seats]
        if not engine.initialize_game(player_names, room.map_seed, turn_mode=room.turn_mode):
            return self._failure("游戏初始化失败")

        for seat, player in zip(room.seats, engine.player_system.players):
            seat.player_id = player.id

        room.engine = engine
        room.started = True
        return {
            "success": True,
            "room": serialize_room_state(room),
            "views": {
                seat.client_id: serialize_player_view(engine, seat.player_id)
                for seat in room.seats
            }
        }

    def submit_action(self, room_id: str, client_id: str,
                      action_data: Union[Dict[str, object], GameAction]) -> Dict[str, object]:
        """提交行动到房间权威引擎，并返回行动结果与玩家安全视图。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return self._action_response(room, seat, ActionResult(False, room.close_reason or "房间已关闭"))
        if not seat.connected:
            return self._action_response(room, seat, ActionResult(False, "玩家已离线，请先重连"))
        if not room.started or not room.engine:
            return self._action_response(room, seat, ActionResult(False, "房间尚未开始"))
        if not seat.player_id:
            return self._action_response(room, seat, ActionResult(False, "玩家席位尚未绑定"))

        try:
            action = action_data if isinstance(action_data, GameAction) else deserialize_action(action_data)
        except (KeyError, TypeError, ValueError) as error:
            return self._action_response(room, seat, ActionResult(False, f"行动格式错误: {error}"))

        if action.player_id != seat.player_id:
            return self._action_response(room, seat, ActionResult(False, "无权操作该玩家"))

        result = room.engine.execute_action_with_result(action)
        self._record_action_events(room, seat, result)
        return self._action_response(room, seat, result)

    def get_player_view(self, room_id: str, client_id: str) -> Dict[str, object]:
        """获取指定客户端对应玩家的安全视图。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return {
                "success": False,
                "message": room.close_reason or "房间已关闭",
                "room": serialize_room_state(room),
                "view": None
            }
        if not room.started or not room.engine or not seat.player_id:
            return {
                "success": False,
                "message": "房间尚未开始",
                "room": serialize_room_state(room),
                "view": None
            }
        return {
            "success": True,
            "room": serialize_room_state(room),
            "view": serialize_player_view(room.engine, seat.player_id)
        }

    def get_room_state(self, room_id: str) -> Dict[str, object]:
        """获取房间状态。"""
        return serialize_room_state(self._get_room(room_id))

    def get_room_engine(self, room_id: str) -> Optional[GameEngine]:
        """获取房间权威引擎，供进程内 NetworkSession 镜像使用。"""
        return self._get_room(room_id).engine

    def get_client_player_id(self, room_id: str, client_id: str) -> Optional[str]:
        """获取客户端绑定的玩家 ID。"""
        return self._require_seat(self._get_room(room_id), client_id).player_id

    def leave_room(self, room_id: str, client_id: str) -> Dict[str, object]:
        """标记客户端离开房间；房主离开会关闭房间。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return {"success": True, "room": serialize_room_state(room)}

        was_connected = seat.connected
        seat.connected = False
        if was_connected:
            self._record_system_event(room, seat, f"{seat.player_name} 已离开房间", "player_left")

        if self._is_host(room, client_id):
            room.closed = True
            room.close_reason = "房主已退出，房间关闭"
            for current_seat in room.seats:
                current_seat.connected = False
            self._record_system_event(room, seat, room.close_reason, "room_closed")
        return {"success": True, "room": serialize_room_state(room)}

    def reconnect_room(self, room_id: str, client_id: str) -> Dict[str, object]:
        """标记客户端重新连接房间。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return self._room_failure(room, room.close_reason or "房间已关闭")
        if seat.connected:
            return {"success": True, "room": serialize_room_state(room)}
        seat.connected = True
        self._record_system_event(room, seat, f"{seat.player_name} 已重新连接", "player_reconnected")
        return {"success": True, "room": serialize_room_state(room)}

    def _record_action_events(self, room: MultiplayerRoom, seat: PlayerSeat,
                              result: ActionResult):
        """记录房间事件，供客户端轮询展示。"""
        event_items = [serialize_event(event) for event in result.events]
        if not event_items and result.message:
            event_items = [{"event_type": "action_result", "message": result.message, "data": {}}]
        for event in event_items:
            room.event_log.append({
                "sequence": room.next_event_sequence,
                "player_id": seat.player_id,
                "player_name": seat.player_name,
                "event_type": event.get("event_type"),
                "message": event.get("message", ""),
                "data": event.get("data", {})
            })
            room.next_event_sequence += 1
        room.event_log = room.event_log[-100:]

    def _record_system_event(self, room: MultiplayerRoom, seat: PlayerSeat,
                             message: str, event_type: str):
        room.event_log.append({
            "sequence": room.next_event_sequence,
            "player_id": seat.player_id,
            "player_name": seat.player_name,
            "event_type": event_type,
            "message": message,
            "data": {}
        })
        room.next_event_sequence += 1
        room.event_log = room.event_log[-100:]

    def _action_response(self, room: MultiplayerRoom, seat: PlayerSeat,
                         result: ActionResult) -> Dict[str, object]:
        view = None
        if room.started and room.engine and seat.player_id:
            view = serialize_player_view(room.engine, seat.player_id)
        return {
            "success": result.success,
            "result": serialize_action_result(result),
            "room": serialize_room_state(room),
            "view": view
        }

    def _allocate_room_id(self) -> str:
        room_id = f"room_{self._next_room_index}"
        self._next_room_index += 1
        return room_id

    def _allocate_client_id(self) -> str:
        client_id = f"client_{self._next_client_index}"
        self._next_client_index += 1
        return client_id

    def _get_room(self, room_id: str) -> MultiplayerRoom:
        if room_id not in self.rooms:
            raise KeyError(f"房间不存在: {room_id}")
        return self.rooms[room_id]

    def _require_seat(self, room: MultiplayerRoom, client_id: str) -> PlayerSeat:
        seat = room.get_seat(client_id)
        if not seat:
            raise KeyError(f"客户端不在房间中: {client_id}")
        return seat

    def _is_host(self, room: MultiplayerRoom, client_id: str) -> bool:
        return bool(room.seats and room.seats[0].client_id == client_id)

    def _failure(self, message: str) -> Dict[str, object]:
        return {"success": False, "message": message}

    def _room_failure(self, room: MultiplayerRoom, message: str) -> Dict[str, object]:
        return {"success": False, "message": message, "room": serialize_room_state(room)}
