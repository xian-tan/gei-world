"""
多人服务端（服务端权威）。

职责：房间/席位/唯一权威 GameEngine 管理、行动鉴权、心跳与断线超时、离线玩家自动跳过、
房主强制跳过、房间清理、房间快照保存与恢复。传输层见 http_multiplayer.py。

安全约定：
- 房间码为 6 位不易混淆字符；客户端令牌（client_id）为随机令牌，只下发给本人，公开房间状态中不出现。
- 所有写操作与玩家视图都必须携带本人令牌；可选房间密码。
"""
import functools
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from .game_engine import GameEngine
from .models import ActionResult, ActionType, GameAction
from .network_protocol import (
    deserialize_action,
    serialize_action_result,
    serialize_event,
    serialize_player_view,
    serialize_room_state,
)
from .systems.turn_system import TurnSystem

logger = logging.getLogger("gei_world.server")

ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
HEARTBEAT_TIMEOUT = 60.0      # 秒：超过该时长未收到请求视为离线
CLOSED_ROOM_TTL = 600.0       # 秒：已关闭/已结束房间保留时长
IDLE_ROOM_TTL = 1800.0        # 秒：无人在线或未开局房间的保留时长


@dataclass
class PlayerSeat:
    """房间内的玩家席位。"""
    client_id: str
    player_name: str
    player_id: Optional[str] = None
    connected: bool = True
    claimed: bool = True
    left_explicitly: bool = False
    last_seen: float = 0.0


@dataclass
class MultiplayerRoom:
    """多人房间状态。"""
    room_id: str
    max_players: int
    turn_mode: str = TurnSystem.MODE_SIMULTANEOUS
    map_seed: Optional[int] = None
    map_type: Optional[str] = None
    map_size: Optional[str] = None
    password: Optional[str] = None
    auto_skip_offline: bool = True
    seats: List[PlayerSeat] = field(default_factory=list)
    engine: Optional[GameEngine] = None
    started: bool = False
    closed: bool = False
    close_reason: str = ""
    event_log: List[Dict[str, object]] = field(default_factory=list)
    next_event_sequence: int = 1
    created_at: float = 0.0
    last_activity: float = 0.0
    closed_at: Optional[float] = None

    def get_seat(self, client_id: str) -> Optional[PlayerSeat]:
        for seat in self.seats:
            if seat.client_id == client_id:
                return seat
        return None


def _locked(method):
    """串行化公开方法，并在执行前做一次心跳超时与房间清理。"""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            self._sweep()
            return method(self, *args, **kwargs)
    return wrapper


class MultiplayerServer:
    """服务端权威房间管理。"""

    def __init__(self, clock: Callable[[], float] = time.monotonic, heartbeat_timeout: float = HEARTBEAT_TIMEOUT,
                 closed_room_ttl: float = CLOSED_ROOM_TTL, idle_room_ttl: float = IDLE_ROOM_TTL,
                 save_directory: Optional[str] = None):
        self.rooms: Dict[str, MultiplayerRoom] = {}
        self._lock = threading.RLock()
        self.clock = clock
        self.heartbeat_timeout = heartbeat_timeout
        self.closed_room_ttl = closed_room_ttl
        self.idle_room_ttl = idle_room_ttl
        self.save_directory = save_directory

    # ------------------------------------------------------------------ 房间生命周期
    @_locked
    def create_room(self, host_name: str, max_players: int = 2,
                    turn_mode: str = TurnSystem.MODE_SIMULTANEOUS,
                    map_seed: int = None, map_type: str = None, map_size: str = None,
                    password: str = None) -> Dict[str, object]:
        """创建房间并占用第一个席位（房主）。"""
        if max_players < 2:
            raise ValueError("房间至少需要 2 名玩家")
        if max_players > 4:
            raise ValueError("当前最多支持 4 名玩家")
        if turn_mode not in TurnSystem.SUPPORTED_MODES:
            raise ValueError(f"未知回合模式: {turn_mode}")

        now = self.clock()
        client_id = self._allocate_client_id()
        room = MultiplayerRoom(
            room_id=self._allocate_room_id(), max_players=max_players, turn_mode=turn_mode,
            map_seed=map_seed, map_type=map_type, map_size=map_size, password=password or None,
            seats=[PlayerSeat(client_id=client_id, player_name=host_name, last_seen=now)],
            created_at=now, last_activity=now,
        )
        self.rooms[room.room_id] = room
        logger.info("room %s created by %s (%s)", room.room_id, host_name, turn_mode)
        return {"success": True, "room": serialize_room_state(room, client_id), "client_id": client_id}

    @_locked
    def join_room(self, room_id: str, player_name: str, password: str = None) -> Dict[str, object]:
        """加入未开始的房间；恢复的房间可按玩家名认领预留席位。"""
        room = self._get_room(room_id)
        if room.closed:
            return self._room_failure(room, room.close_reason or "房间已关闭")
        if room.password and password != room.password:
            return self._failure("房间密码错误")

        reserved = next((seat for seat in room.seats if not seat.claimed and seat.player_name == player_name), None)
        if reserved:
            reserved.client_id = self._allocate_client_id()
            reserved.claimed = True
            self._mark_online(room, reserved, announce=True)
            return {"success": True, "room": serialize_room_state(room, reserved.client_id), "client_id": reserved.client_id}
        if room.started:
            open_names = [seat.player_name for seat in room.seats if not seat.claimed]
            hint = f"（可用席位：{'、'.join(open_names)}）" if open_names else ""
            return self._failure(f"房间已开始，无法加入{hint}")
        if len(room.seats) >= room.max_players:
            return self._failure("房间已满")
        if any(seat.player_name == player_name for seat in room.seats):
            return self._failure("玩家名称重复")

        client_id = self._allocate_client_id()
        room.seats.append(PlayerSeat(client_id=client_id, player_name=player_name, last_seen=self.clock()))
        room.last_activity = self.clock()
        logger.info("room %s joined by %s", room.room_id, player_name)
        return {"success": True, "room": serialize_room_state(room, client_id), "client_id": client_id}

    @_locked
    def start_room(self, room_id: str, map_seed: int = None, turn_mode: str = None) -> Dict[str, object]:
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
        if not engine.initialize_game([seat.player_name for seat in room.seats], room.map_seed,
                                      turn_mode=room.turn_mode, map_type=room.map_type, map_size=room.map_size):
            return self._failure("游戏初始化失败")
        for seat, player in zip(room.seats, engine.player_system.players):
            seat.player_id = player.id
        room.engine = engine
        room.started = True
        room.last_activity = self.clock()
        logger.info("room %s started with %d players", room.room_id, len(room.seats))
        return {
            "success": True,
            "room": serialize_room_state(room),
            "views": {seat.client_id: serialize_player_view(engine, seat.player_id) for seat in room.seats},
        }

    @_locked
    def leave_room(self, room_id: str, client_id: str) -> Dict[str, object]:
        """离开房间；房主离开会关闭房间，普通玩家可之后重连。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return {"success": True, "room": serialize_room_state(room, client_id)}
        seat.left_explicitly = True
        if seat.connected:
            seat.connected = False
            self._record_system_event(room, seat, f"{seat.player_name} 已离开房间", "player_left")
        if self._is_host(room, client_id):
            self._close_room(room, "房主已退出，房间关闭", seat)
        else:
            self._auto_skip_offline(room)
        return {"success": True, "room": serialize_room_state(room, client_id)}

    @_locked
    def reconnect_room(self, room_id: str, client_id: str) -> Dict[str, object]:
        """显式重新连接（离开后回到房间）。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return self._room_failure(room, room.close_reason or "房间已关闭")
        seat.left_explicitly = False
        self._mark_online(room, seat, announce=True)
        return {"success": True, "room": serialize_room_state(room, client_id)}

    @_locked
    def heartbeat(self, room_id: str, client_id: str) -> Dict[str, object]:
        """心跳：刷新在线时间；超时掉线的玩家会自动恢复在线。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if not room.closed:
            self._touch(room, seat)
        return {"success": True, "room": serialize_room_state(room, client_id)}

    @_locked
    def force_skip(self, room_id: str, client_id: str) -> Dict[str, object]:
        """房主强制结束所有离线玩家的当前回合。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if not self._is_host(room, client_id):
            return self._failure("只有房主可以强制跳过")
        self._touch(room, seat)
        skipped = self._auto_skip_offline(room, force=True)
        if not skipped:
            return self._room_failure(room, "没有可跳过的离线玩家")
        return {"success": True, "skipped": skipped, "room": serialize_room_state(room, client_id)}

    # ------------------------------------------------------------------ 对局
    @_locked
    def submit_action(self, room_id: str, client_id: str,
                      action_data: Union[Dict[str, object], GameAction]) -> Dict[str, object]:
        """提交行动到房间权威引擎，返回行动结果与本人安全视图。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return self._action_response(room, seat, ActionResult(False, room.close_reason or "房间已关闭"))
        if seat.left_explicitly:
            return self._action_response(room, seat, ActionResult(False, "玩家已离线，请先重连"))
        self._touch(room, seat)
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
        if result.success:
            self._auto_skip_offline(room)
            self._maybe_mark_finished(room)
        return self._action_response(room, seat, result)

    @_locked
    def get_player_view(self, room_id: str, client_id: str) -> Dict[str, object]:
        """获取本人安全视图（同时视为心跳）。"""
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if room.closed:
            return {"success": False, "message": room.close_reason or "房间已关闭",
                    "room": serialize_room_state(room, client_id), "view": None}
        if not seat.left_explicitly:
            self._touch(room, seat)
        if not room.started or not room.engine or not seat.player_id:
            return {"success": False, "message": "房间尚未开始", "room": serialize_room_state(room, client_id), "view": None}
        return {"success": True, "room": serialize_room_state(room, client_id),
                "view": serialize_player_view(room.engine, seat.player_id)}

    @_locked
    def get_room_state(self, room_id: str, client_id: str = None) -> Dict[str, object]:
        """公开房间状态（不含任何令牌）。"""
        room = self._get_room(room_id)
        viewer = client_id if client_id and room.get_seat(client_id) else None
        return serialize_room_state(room, viewer)

    @_locked
    def get_room_engine(self, room_id: str) -> Optional[GameEngine]:
        """进程内会话使用的权威引擎。"""
        return self._get_room(room_id).engine

    @_locked
    def get_client_player_id(self, room_id: str, client_id: str) -> Optional[str]:
        return self._require_seat(self._get_room(room_id), client_id).player_id

    # ------------------------------------------------------------------ 快照
    @_locked
    def save_room(self, room_id: str, client_id: str) -> Dict[str, object]:
        """房主把对局保存为服务端快照，存档名即房间码。"""
        from .systems.save_system import GameSaveSystem
        room = self._get_room(room_id)
        seat = self._require_seat(room, client_id)
        if not self._is_host(room, client_id):
            return self._failure("只有房主可以保存房间")
        if not room.started or not room.engine:
            return self._failure("房间尚未开始")
        self._touch(room, seat)
        save_system = GameSaveSystem(self._snapshot_directory())
        room.engine.ai_player_configs = {}
        if not save_system.save_game(room.engine, f"room_{room.room_id}"):
            return self._failure("保存失败")
        self._record_system_event(room, seat, f"房间已保存，恢复码 {room.room_id}", "room_saved")
        return {"success": True, "save_code": room.room_id, "room": serialize_room_state(room, client_id)}

    @_locked
    def restore_room(self, save_code: str, host_name: str, password: str = None) -> Dict[str, object]:
        """从快照恢复对局：房主认领同名席位，其余玩家用原名字加入认领席位。"""
        from .systems.save_system import GameSaveSystem
        save_system = GameSaveSystem(self._snapshot_directory())
        engine = save_system.load_game(f"room_{str(save_code).strip().upper()}")
        if engine is None:
            return self._failure("未找到该恢复码对应的房间存档")
        names = [player.name for player in engine.player_system.players]
        if host_name not in names:
            return self._failure(f"房主名字必须是原对局中的玩家之一：{'、'.join(names)}")
        now = self.clock()
        seats = []
        host_client_id = None
        for player in engine.player_system.players:
            is_host = player.name == host_name
            client_id = self._allocate_client_id() if is_host else secrets.token_urlsafe(12)
            if is_host:
                host_client_id = client_id
            seats.append(PlayerSeat(client_id=client_id, player_name=player.name, player_id=player.id,
                                    connected=is_host, claimed=is_host, last_seen=now))
        host_index = names.index(host_name)
        seats.insert(0, seats.pop(host_index))
        room = MultiplayerRoom(
            room_id=self._allocate_room_id(), max_players=len(seats), turn_mode=engine.turn_system.mode,
            map_type=engine.map_system.generator_type, password=password or None, seats=seats,
            engine=engine, started=True, created_at=now, last_activity=now,
        )
        self.rooms[room.room_id] = room
        logger.info("room %s restored from %s by %s", room.room_id, save_code, host_name)
        return {"success": True, "client_id": host_client_id, "room": serialize_room_state(room, host_client_id)}

    def _snapshot_directory(self) -> Optional[str]:
        if self.save_directory:
            return self.save_directory
        from .systems.save_system import GameSaveSystem
        return str(Path(GameSaveSystem.get_default_save_directory()).parent / "server_rooms")

    # ------------------------------------------------------------------ 内部：在线状态
    def _touch(self, room: MultiplayerRoom, seat: PlayerSeat):
        seat.last_seen = self.clock()
        room.last_activity = seat.last_seen
        if not seat.connected and not seat.left_explicitly and seat.claimed:
            self._mark_online(room, seat, announce=True)

    def _mark_online(self, room: MultiplayerRoom, seat: PlayerSeat, announce: bool):
        seat.last_seen = self.clock()
        room.last_activity = seat.last_seen
        if not seat.connected:
            seat.connected = True
            if announce:
                self._record_system_event(room, seat, f"{seat.player_name} 已重新连接", "player_reconnected")

    def _sweep(self):
        """心跳超时标记离线、离线自动跳过、清理过期房间。"""
        now = self.clock()
        for room_id, room in list(self.rooms.items()):
            if room.closed:
                if room.closed_at is not None and now - room.closed_at > self.closed_room_ttl:
                    del self.rooms[room_id]
                    logger.info("room %s removed (closed)", room_id)
                continue
            for seat in room.seats:
                if seat.connected and seat.claimed and now - seat.last_seen > self.heartbeat_timeout:
                    seat.connected = False
                    self._record_system_event(room, seat, f"{seat.player_name} 连接超时", "player_timeout")
            if room.started:
                self._auto_skip_offline(room)
            if not any(seat.connected for seat in room.seats) and now - room.last_activity > self.idle_room_ttl:
                self._close_room(room, "房间长时间无人在线，已关闭")
            elif not room.started and now - room.created_at > self.idle_room_ttl:
                self._close_room(room, "房间长时间未开局，已关闭")

    def _auto_skip_offline(self, room: MultiplayerRoom, force: bool = False) -> List[str]:
        """离线玩家轮到行动时自动结束其回合（房间开启自动跳过或房主强制）。"""
        if not room.started or not room.engine or room.closed or room.engine.game_over:
            return []
        if not (room.auto_skip_offline or force):
            return []
        skipped = []
        for _ in range(len(room.seats) * 2):
            progressed = False
            for seat in room.seats:
                if seat.connected or not seat.player_id:
                    continue
                if not room.engine.turn_system.can_player_act(seat.player_id):
                    continue
                result = room.engine.execute_action_with_result(GameAction(seat.player_id, ActionType.END_TURN, {}))
                if not result.success:
                    continue
                skipped.append(seat.player_name)
                progressed = True
                self._record_system_event(room, seat, f"{seat.player_name} 离线，已自动跳过回合", "turn_skipped")
                self._record_action_events(room, seat, result)
            if not progressed or room.engine.game_over:
                break
        self._maybe_mark_finished(room)
        return skipped

    def _maybe_mark_finished(self, room: MultiplayerRoom):
        if room.engine and room.engine.game_over and room.closed_at is None:
            room.closed_at = self.clock()

    def _close_room(self, room: MultiplayerRoom, reason: str, seat: Optional[PlayerSeat] = None):
        room.closed = True
        room.close_reason = reason
        room.closed_at = self.clock()
        for current in room.seats:
            current.connected = False
        self._record_system_event(room, seat or room.seats[0], reason, "room_closed")
        logger.info("room %s closed: %s", room.room_id, reason)

    # ------------------------------------------------------------------ 内部：事件与工具
    def _record_action_events(self, room: MultiplayerRoom, seat: PlayerSeat, result: ActionResult):
        events = [serialize_event(event) for event in result.events]
        if not events and result.message:
            events = [{"event_type": "action_result", "message": result.message, "data": {}}]
        for event in events:
            self._append_event(room, seat, event.get("event_type"), event.get("message", ""), event.get("data", {}))

    def _record_system_event(self, room: MultiplayerRoom, seat: PlayerSeat, message: str, event_type: str):
        self._append_event(room, seat, event_type, message, {})

    def _append_event(self, room, seat, event_type, message, data):
        room.event_log.append({
            "sequence": room.next_event_sequence, "player_id": seat.player_id, "player_name": seat.player_name,
            "event_type": event_type, "message": message, "data": data,
        })
        room.next_event_sequence += 1
        room.event_log = room.event_log[-100:]

    def _action_response(self, room: MultiplayerRoom, seat: PlayerSeat, result: ActionResult) -> Dict[str, object]:
        view = serialize_player_view(room.engine, seat.player_id) if room.started and room.engine and seat.player_id else None
        return {"success": result.success, "result": serialize_action_result(result),
                "room": serialize_room_state(room, seat.client_id), "view": view}

    def _allocate_room_id(self) -> str:
        """6 位房间码：大写字母与数字，去掉易混淆的 0/O/1/I。"""
        while True:
            room_id = "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(6))
            if room_id not in self.rooms:
                return room_id

    @staticmethod
    def _allocate_client_id() -> str:
        """客户端身份令牌：不可猜测，只下发给加入者本人。"""
        return secrets.token_urlsafe(12)

    def _get_room(self, room_id: str) -> MultiplayerRoom:
        key = str(room_id or "").strip().upper()
        if key not in self.rooms:
            raise KeyError(f"房间不存在: {room_id}")
        return self.rooms[key]

    def _require_seat(self, room: MultiplayerRoom, client_id: str) -> PlayerSeat:
        seat = room.get_seat(client_id) if client_id else None
        if not seat or not seat.claimed:
            raise KeyError("客户端不在房间中或身份无效")
        return seat

    @staticmethod
    def _is_host(room: MultiplayerRoom, client_id: str) -> bool:
        return bool(room.seats and room.seats[0].client_id == client_id)

    @staticmethod
    def _failure(message: str) -> Dict[str, object]:
        return {"success": False, "message": message}

    def _room_failure(self, room: MultiplayerRoom, message: str) -> Dict[str, object]:
        return {"success": False, "message": message, "room": serialize_room_state(room)}
