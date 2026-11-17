"""
多人：HTTP 房间（创建 / 加入 / 重新连接 / 房主等待大厅）、本机双客户端调试房、视角切换、离开与状态轮询。
"""
import os
import time
from typing import Any, Dict, Optional

from src.game_session import HTTPNetworkSession, LocalGameSession, NetworkGameSession
from src.http_multiplayer import HTTPMultiplayerClient
from src.multiplayer_server import MultiplayerServer
from src.systems.ai_system import AIManager
from ui.controllers.menu import MAP_TYPE_OPTIONS, TURN_MODE_OPTIONS, is_dev_mode
from ui.identity_store import IdentityStore
from ui.ui_config import COLORS


class MultiplayerMixin:
    """多人房间流程。"""

    # ------------------------------------------------------------------ 公共
    @property
    def identity_store(self) -> IdentityStore:
        if getattr(self, "_identity_store", None) is None:
            self._identity_store = IdentityStore()
        return self._identity_store

    def _clear_multiplayer_context(self):
        self.multiplayer_server = None
        self.multiplayer_room_id = None
        self.multiplayer_sessions = {}
        self.active_multiplayer_client_id = None
        self.notified_multiplayer_event_sequences = set()
        self._invalidate_multiplayer_status()

    def _get_http_base_url(self) -> str:
        return os.environ.get("GEI_WORLD_HTTP_URL", "http://127.0.0.1:8000")

    def _enter_multiplayer_game(self, room_id: str, sessions: Dict[str, Any], active_client_id: str,
                                server: Optional[MultiplayerServer] = None):
        self.multiplayer_server = server
        self.multiplayer_room_id = room_id
        self.multiplayer_sessions = sessions
        self.ai_manager = AIManager()
        self.human_player_ids = []
        self.pending_host_room = None
        self.game_started = True
        self._activate_multiplayer_client(active_client_id, notify=False)
        self.camera_system.zoom = 1.6
        self._focus_on_player(self._get_controlled_player())
        self.ui_system.close_modal()
        self.ui_system.show_banner(f"房间 {room_id} · 对局开始")

    def _remember_http_room_info(self, base_url: str, room_id: str, client_id: str, player_name: str = ""):
        """记住最近房间与本机身份，供重新连接使用。"""
        self.last_http_room_info = {"base_url": base_url, "room_id": room_id, "client_id": client_id}
        self.identity_store.remember(base_url, room_id, client_id, player_name)
        if self.ui_system.has_active_modal():
            self.ui_system.set_modal_input_value("base_url", base_url)
            self.ui_system.set_modal_input_value("room_id", room_id)

    # ------------------------------------------------------------------ 本机调试
    def _start_local_multiplayer(self, turn_mode: str = "simultaneous", map_seed: int = 123):
        """进程内双客户端房间（调试/热座演示），TAB 切换视角。"""
        server = MultiplayerServer()
        created = server.create_room("玩家1", max_players=2, turn_mode=turn_mode, map_seed=map_seed)
        room_id = created["room"]["room_id"]
        host_client_id = created["client_id"]
        guest_client_id = server.join_room(room_id, "玩家2")["client_id"]
        host_session = NetworkGameSession(server, room_id, host_client_id)
        if not host_session.start_game(turn_mode=turn_mode):
            self._notify("本机多人房间启动失败")
            return False
        sessions = {host_client_id: host_session, guest_client_id: NetworkGameSession(server, room_id, guest_client_id)}
        self._enter_multiplayer_game(room_id, sessions, host_client_id, server)
        self._notify(f"本机双客户端房间已开始（{turn_mode}），按 TAB 切换视角。")
        return True

    def _show_local_multiplayer_modal(self):
        self.ui_system.show_modal(
            "本机双客户端（调试）",
            ["创建进程内双人房间，开始后按 TAB 在两个玩家视角间切换。"],
            [
                {'text': "轮流回合", 'callback': lambda: self._start_local_multiplayer("sequential"), 'color': COLORS['ACCENT']},
                {'text': "同时回合", 'callback': lambda: self._start_local_multiplayer("simultaneous"), 'color': COLORS['SUCCESS']},
                {'text': "取消", 'callback': self.ui_system.close_modal},
            ]
        )

    def _start_http_multiplayer(self, base_url: str = None, turn_mode: str = "simultaneous", map_seed: int = 123):
        """HTTP 调试房：一个客户端同时占两个席位（仅开发模式入口）。"""
        base_url = base_url or self._get_http_base_url()
        http_client = HTTPMultiplayerClient(base_url, timeout=1.5)
        created = http_client.create_room("玩家1", max_players=2, turn_mode=turn_mode, map_seed=map_seed)
        if not created.get("success"):
            self._notify(f"创建房间失败：{created.get('message', '未知错误')}")
            return False
        room_id = created["room"]["room_id"]
        host_client_id = created["client_id"]
        joined = http_client.join_room(room_id, "玩家2")
        if not joined.get("success"):
            self._notify(f"加入房间失败：{joined.get('message', '未知错误')}")
            return False
        host_session = HTTPNetworkSession(http_client, room_id, host_client_id)
        if not host_session.start_game(turn_mode=turn_mode):
            self._notify("房间启动失败")
            return False
        sessions = {host_client_id: host_session,
                    joined["client_id"]: HTTPNetworkSession(http_client, room_id, joined["client_id"])}
        self._remember_http_room_info(base_url, room_id, host_client_id, "玩家1")
        self._enter_multiplayer_game(room_id, sessions, host_client_id)
        self._notify("HTTP 调试房已开始，按 TAB 切换视角。")
        return True

    # ------------------------------------------------------------------ HTTP 表单
    def _get_http_form_values(self) -> Dict[str, Any]:
        values = self.ui_system.get_modal_input_values()
        values.setdefault("base_url", self.last_http_room_info.get("base_url") or self._get_http_base_url())
        values.setdefault("room_id", self.last_http_room_info.get("room_id", ""))
        values.setdefault("turn_mode", "simultaneous")
        values["room_id"] = str(values.get("room_id", "")).strip().upper()
        values["base_url"] = str(values.get("base_url", "")).strip() or self._get_http_base_url()
        return values

    def _show_http_multiplayer_modal(self):
        """多人联机：创建房间 / 加入房间 / 重新连接。"""
        latest = self.identity_store.latest() or {}
        base_url = self.last_http_room_info.get("base_url") or latest.get("base_url") or self._get_http_base_url()
        room_id = self.last_http_room_info.get("room_id") or latest.get("room_id", "")
        lines = ["房主点击「创建房间」后把房间码发给对手；对手填写房间码后点击「加入房间」。"]
        if room_id:
            lines.append(f"最近房间：{room_id}（断线后可直接「重新连接」）")

        def form():
            return self._get_http_form_values()

        actions = [
            {'text': "创建房间", 'color': COLORS['SUCCESS'], 'callback': lambda: self._create_http_room(
                base_url=form()["base_url"], turn_mode=form().get("turn_mode", "simultaneous"),
                map_seed=None, host_name=form().get("player_name") or "房主",
                map_type=form().get("map_type"), password=form().get("password") or None)},
            {'text': "加入房间", 'color': COLORS['ACCENT'], 'callback': lambda: self._join_http_multiplayer_room(
                base_url=form()["base_url"], room_id=form()["room_id"],
                player_name=form().get("player_name") or "挑战者", password=form().get("password") or None)},
            {'text': "重新连接", 'callback': lambda: self._connect_http_multiplayer_existing(
                base_url=form()["base_url"], room_id=form()["room_id"], player_name=form().get("player_name", ""))},
        ]
        if is_dev_mode():
            actions.append({'text': "调试双席位房", 'callback': lambda: self._start_http_multiplayer(
                base_url=form()["base_url"], turn_mode=form().get("turn_mode", "simultaneous"))})
        actions.append({'text': "取消", 'callback': self.ui_system.close_modal})
        self.ui_system.show_modal("多人联机", lines, actions, inputs=[
            {"key": "base_url", "label": "服务地址", "value": base_url},
            {"key": "player_name", "label": "你的名字", "value": latest.get("player_name") or "玩家"},
            {"key": "room_id", "label": "房间码", "value": room_id},
            {"key": "password", "label": "房间密码（可选）", "value": ""},
            {"key": "turn_mode", "label": "回合模式（房主）", "value": "simultaneous", "options": TURN_MODE_OPTIONS},
            {"key": "map_type", "label": "地图类型（房主）", "value": "continents", "options": MAP_TYPE_OPTIONS},
        ])

    # ------------------------------------------------------------------ HTTP 房间流程
    def _create_http_room(self, base_url: str = None, turn_mode: str = "simultaneous", map_seed: int = None,
                          host_name: str = "房主", map_type: str = None, password: str = None):
        """创建房间并进入等待大厅；对手加入后自动开局。"""
        base_url = base_url or self._get_http_base_url()
        response = HTTPMultiplayerClient(base_url, timeout=1.5).create_room(
            host_name, max_players=2, turn_mode=turn_mode, map_seed=map_seed, map_type=map_type, password=password)
        if not response.get("success"):
            self._notify(f"创建房间失败：{response.get('message', '未知错误')}")
            return None
        room_id = response["room"]["room_id"]
        client_id = response["client_id"]
        self._remember_http_room_info(base_url, room_id, client_id, host_name)
        self.pending_host_room = {"base_url": base_url, "room_id": room_id, "client_id": client_id}
        self._pending_poll_time = 0.0
        self.ui_system.show_modal(
            "等待对手加入",
            [f"房间码：{room_id}", f"服务地址：{base_url}",
             "把房间码（和密码）发给对手，对方加入后自动开局。"],
            [{'text': "取消房间", 'color': COLORS['DANGER'], 'callback': self._cancel_pending_host_room}],
        )
        self._notify(f"房间已创建：{room_id}，等待对手加入。")
        return response

    def _poll_pending_host_room(self, force: bool = False) -> bool:
        """房主等待大厅：对手加入且房间开始后自动进入对局。"""
        pending = getattr(self, "pending_host_room", None)
        if not pending or self.game_started:
            return False
        now = time.monotonic()
        if not force and now - self._pending_poll_time < self.multiplayer_poll_interval:
            return False
        self._pending_poll_time = now
        response = HTTPMultiplayerClient(pending["base_url"], timeout=1.5).get_room_state(pending["room_id"])
        room = response.get("room") or {}
        if not response.get("success"):
            self._notify(f"等待房间失败：{response.get('message', '未知错误')}")
            self.pending_host_room = None
            self.ui_system.close_modal()
            return False
        if room.get("closed"):
            self._notify(room.get("close_reason") or "房间已关闭")
            self.pending_host_room = None
            self.ui_system.close_modal()
            return False
        if room.get("started"):
            host_name = next((seat.get("player_name") for seat in room.get("seats", [])
                              if seat.get("client_id") == pending["client_id"]), "")
            return self._connect_http_multiplayer_existing(pending["base_url"], pending["room_id"],
                                                           pending["client_id"], host_name)
        return False

    def _cancel_pending_host_room(self):
        pending = getattr(self, "pending_host_room", None)
        if pending:
            HTTPMultiplayerClient(pending["base_url"], timeout=1.5).leave_room(pending["room_id"], pending["client_id"])
        self.pending_host_room = None
        self.ui_system.close_modal()
        self._notify("已取消房间。")

    def _join_http_multiplayer_room(self, base_url: str = None, room_id: str = None, player_name: str = "挑战者",
                                    turn_mode: str = None, map_seed: int = None, password: str = None):
        """加入房间；满员后按房主设置开局并进入对局。"""
        base_url = base_url or self._get_http_base_url()
        room_id = (room_id or os.environ.get("GEI_WORLD_ROOM_ID") or "").strip().upper()
        if not room_id:
            self._notify("缺少房间号：请输入房主提供的房间码。")
            return False
        http_client = HTTPMultiplayerClient(base_url, timeout=1.5)
        joined = http_client.join_room(room_id, player_name, password=password)
        if not joined.get("success"):
            self._notify(f"加入房间失败：{joined.get('message', '未知错误')}")
            return False
        client_id = joined["client_id"]
        self._remember_http_room_info(base_url, room_id, client_id, player_name)
        start_response = http_client.start_room(room_id, map_seed=map_seed, turn_mode=turn_mode)
        if not start_response.get("success"):
            self._notify(f"已加入，等待开局：{start_response.get('message', '等待房主开始')}")
            return False
        session = HTTPNetworkSession(http_client, room_id, client_id)
        session.get_player_view()
        self._enter_multiplayer_game(room_id, {client_id: session}, client_id)
        self._notify(f"已加入房间 {room_id}。")
        return True

    def _connect_http_multiplayer_existing(self, base_url: str = None, room_id: str = None, client_id: str = None,
                                           player_name: str = ""):
        """用本机记住的身份重新连接已开始的房间。"""
        base_url = base_url or self._get_http_base_url()
        room_id = (room_id or os.environ.get("GEI_WORLD_ROOM_ID") or "").strip().upper()
        if room_id and not client_id:
            identity = self.identity_store.lookup(base_url, room_id, player_name) or {}
            player_name = player_name or identity.get("player_name", "")
            client_id = identity.get("client_id") or os.environ.get("GEI_WORLD_CLIENT_ID")
        if not room_id or not client_id:
            self._notify("缺少房间号或客户端ID：本机没有该房间的身份记录，请确认服务地址和房间码。")
            return False
        http_client = HTTPMultiplayerClient(base_url, timeout=1.5)
        session = HTTPNetworkSession(http_client, room_id, client_id)
        http_client.reconnect_room(room_id, client_id)
        view_response = session.get_player_view()
        if not view_response.get("success"):
            self._notify(f"连接房间失败：{view_response.get('message', '未知错误')}")
            return False
        self._remember_http_room_info(base_url, room_id, client_id, player_name)
        self._enter_multiplayer_game(room_id, {client_id: session}, client_id)
        self._notify(f"已连接房间 {room_id}。")
        return True

    # ------------------------------------------------------------------ 视角 / 离开
    def _activate_multiplayer_client(self, client_id: str, notify: bool = True) -> bool:
        session = self.multiplayer_sessions.get(client_id)
        if not session:
            return False
        self.session = session
        self.active_multiplayer_client_id = client_id
        self._invalidate_multiplayer_status()
        self.local_player_id = session.player_id
        self._clear_ui_selection_state()
        if notify:
            player = self._get_controlled_player()
            self._notify(f"已切换到 {player.name if player else client_id} 视角")
        return True

    def _switch_multiplayer_client(self) -> bool:
        if len(self.multiplayer_sessions) < 2:
            return False
        client_ids = list(self.multiplayer_sessions.keys())
        if self.active_multiplayer_client_id not in client_ids:
            return self._activate_multiplayer_client(client_ids[0])
        next_index = (client_ids.index(self.active_multiplayer_client_id) + 1) % len(client_ids)
        return self._activate_multiplayer_client(client_ids[next_index])

    def _leave_multiplayer_room(self):
        if hasattr(self.session, 'leave_room'):
            response = self.session.leave_room()
            if not response.get("success"):
                self._notify(f"离开房间失败：{response.get('message', '未知错误')}")
                return False
        elif self.multiplayer_server and self.active_multiplayer_client_id:
            self.multiplayer_server.leave_room(self.multiplayer_room_id, self.active_multiplayer_client_id)
        self._clear_multiplayer_context()
        self.session = LocalGameSession()
        self.game_started = False
        self.local_player_id = None
        self._clear_ui_selection_state()
        self.ui_system.close_modal()
        self._notify("已离开多人房间。")
        return True

    def _show_leave_multiplayer_modal(self):
        self.ui_system.show_modal(
            "离开多人房间",
            ["确定要离开当前房间吗？普通玩家离开后可重新连接；房主离开会关闭房间。"],
            [
                {'text': "继续游戏", 'callback': self.ui_system.close_modal},
                {'text': "离开房间", 'callback': self._leave_multiplayer_room, 'color': COLORS['DANGER']},
            ]
        )

    # ------------------------------------------------------------------ 状态轮询
    def _sync_multiplayer_room_notifications(self, room_state: Dict[str, Any], active_player_id: Optional[str]):
        """根据房间事件提示关闭、离线和重连状态。"""
        for event in room_state.get("recent_events", []) if room_state else []:
            event_type = event.get("event_type")
            if event_type not in {"player_left", "player_reconnected", "player_timeout", "room_closed"}:
                continue
            sequence = event.get("sequence")
            event_key = sequence if sequence is not None else (event_type, event.get("player_name"), event.get("message"))
            if event_key in self.notified_multiplayer_event_sequences:
                continue
            self.notified_multiplayer_event_sequences.add(event_key)
            player_name = event.get("player_name") or "对手"
            is_self_event = bool(active_player_id and active_player_id == event.get("player_id"))
            if event_type == "room_closed":
                self._notify(event.get("message") or room_state.get("close_reason") or "房间已关闭")
            elif event_type in ("player_left", "player_timeout") and not is_self_event:
                self._notify(f"{player_name} 已离线，等待其重连。")
            elif event_type == "player_reconnected" and not is_self_event:
                self._notify(f"{player_name} 已重新连接。")

    def _invalidate_multiplayer_status(self):
        self._multiplayer_status_cache = None
        self._multiplayer_status_time = 0.0

    def _get_multiplayer_status(self) -> Optional[Dict[str, Any]]:
        """获取多人房间状态摘要；HTTP 会话按 multiplayer_poll_interval 节流。"""
        if not self.multiplayer_room_id:
            return None
        is_remote = not self.multiplayer_server and hasattr(self.session, 'http_client')
        now = time.monotonic()
        if (is_remote and self._multiplayer_status_cache is not None
                and now - self._multiplayer_status_time < self.multiplayer_poll_interval):
            return self._multiplayer_status_cache
        status = self._fetch_multiplayer_status()
        if is_remote:
            self._multiplayer_status_cache = status
            self._multiplayer_status_time = now
        return status

    def _fetch_multiplayer_status(self) -> Optional[Dict[str, Any]]:
        active_player_id = self.session.player_id if hasattr(self.session, 'player_id') else self.local_player_id
        view_response = None
        if self.multiplayer_server:
            try:
                room_state = self.multiplayer_server.get_room_state(self.multiplayer_room_id)
                if self.active_multiplayer_client_id and not room_state.get("closed"):
                    view_response = self.multiplayer_server.get_player_view(
                        self.multiplayer_room_id, self.active_multiplayer_client_id)
            except KeyError as error:
                room_state = {"room_id": self.multiplayer_room_id, "closed": True, "close_reason": str(error)}
        elif hasattr(self.session, 'http_client'):
            room_response = self.session.http_client.get_room_state(self.multiplayer_room_id)
            room_state = room_response.get("room") or {
                "room_id": self.multiplayer_room_id, "closed": False, "close_reason": room_response.get("message", "")}
            if not room_state.get("closed"):
                view_response = self.session.get_player_view()
        else:
            return None
        self._sync_multiplayer_room_notifications(room_state, active_player_id)
        view = view_response.get("view") if view_response and view_response.get("success") else None
        tiles = view["tiles"].values() if view else []
        return {
            "room_id": self.multiplayer_room_id,
            "active_client_id": self.active_multiplayer_client_id,
            "active_player_id": active_player_id,
            "closed": room_state.get("closed", False),
            "close_reason": room_state.get("close_reason", ""),
            "seats": room_state.get("seats", []),
            "offline_seats": [seat for seat in room_state.get("seats", [])
                              if not seat.get("connected") and seat.get("player_id") != active_player_id],
            "recent_events": room_state.get("recent_events", []),
            "visible_tile_count": sum(1 for tile in tiles if tile.get("visible")),
            "explored_tile_count": sum(1 for tile in (view["tiles"].values() if view else []) if tile.get("explored")),
        }
