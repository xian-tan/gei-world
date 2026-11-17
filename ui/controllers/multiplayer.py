"""
多人：本机/HTTP 房间流程、视角切换、离开重连与状态轮询。
"""
import os
import time
from typing import Any, Dict, Optional


from src.game_session import HTTPNetworkSession, LocalGameSession, NetworkGameSession
from src.http_multiplayer import HTTPMultiplayerClient
from src.multiplayer_server import MultiplayerServer
from src.systems.ai_system import AIManager
from ui.ui_config import COLORS


class MultiplayerMixin:
    """多人：本机/HTTP 房间流程、视角切换、离开重连与状态轮询。"""

    def _clear_multiplayer_context(self):
        """清理进程内多人房间上下文。"""
        self.multiplayer_server = None
        self.multiplayer_room_id = None
        self.multiplayer_sessions = {}
        self.active_multiplayer_client_id = None
        self.notified_multiplayer_event_sequences = set()
        self._invalidate_multiplayer_status()

    def _start_local_multiplayer(self, turn_mode: str = "simultaneous", map_seed: int = 123):
        """启动进程内本机双人多人房间。"""
        server = MultiplayerServer()
        created = server.create_room("玩家1", max_players=2, turn_mode=turn_mode, map_seed=map_seed)
        room_id = created["room"]["room_id"]
        host_client_id = created["client_id"]
        joined = server.join_room(room_id, "玩家2")
        guest_client_id = joined["client_id"]
        host_session = NetworkGameSession(server, room_id, host_client_id)
        if not host_session.start_game(turn_mode=turn_mode):
            self._notify("本机多人房间启动失败")
            return False
        guest_session = NetworkGameSession(server, room_id, guest_client_id)
        self.multiplayer_server = server
        self.multiplayer_room_id = room_id
        self.multiplayer_sessions = {
            host_client_id: host_session,
            guest_client_id: guest_session,
        }
        self.ai_manager = AIManager()
        self.game_started = True
        self._activate_multiplayer_client(host_client_id, notify=False)
        self._center_camera_on_map()
        self.ui_system.close_modal()
        self._notify(f"本机多人房间已开始：{turn_mode}")
        self._notify("按 TAB 在玩家1/玩家2视角间切换。")
        return True

    def _get_http_base_url(self) -> str:
        """获取 HTTP 多人服务地址；可用环境变量覆盖。"""
        return os.environ.get("GEI_WORLD_HTTP_URL", "http://127.0.0.1:8000")

    def _start_http_multiplayer(self, base_url: str = None,
                                turn_mode: str = "simultaneous", map_seed: int = 123):
        """连接 HTTP 多人服务并创建调试双人房间。"""
        base_url = base_url or self._get_http_base_url()
        try:
            http_client = HTTPMultiplayerClient(base_url, timeout=1.5)
            created = http_client.create_room("玩家1", max_players=2, turn_mode=turn_mode, map_seed=map_seed)
            if not created.get("success"):
                self._notify(f"HTTP 多人创建失败：{created.get('message', '未知错误')}")
                return False
            room_id = created["room"]["room_id"]
            host_client_id = created["client_id"]
            joined = http_client.join_room(room_id, "玩家2")
            if not joined.get("success"):
                self._notify(f"HTTP 多人加入失败：{joined.get('message', '未知错误')}")
                return False
            guest_client_id = joined["client_id"]
            host_session = HTTPNetworkSession(http_client, room_id, host_client_id)
            if not host_session.start_game(turn_mode=turn_mode):
                self._notify("HTTP 多人房间启动失败")
                return False
            guest_session = HTTPNetworkSession(http_client, room_id, guest_client_id)
        except Exception as error:
            self._notify(f"HTTP 多人连接失败：{error}")
            return False
        self._remember_http_room_info(base_url, room_id, host_client_id)
        self.multiplayer_server = None
        self.multiplayer_room_id = room_id
        self.multiplayer_sessions = {
            host_client_id: host_session,
            guest_client_id: guest_session,
        }
        self.ai_manager = AIManager()
        self.game_started = True
        self._activate_multiplayer_client(host_client_id, notify=False)
        self._center_camera_on_map()
        self.ui_system.close_modal()
        self._notify(f"HTTP 多人房间已开始：{turn_mode}")
        self._notify("按 TAB 在玩家1/玩家2视角间切换。")
        return True

    def _create_http_room(self, base_url: str = None, turn_mode: str = "simultaneous",
                          map_seed: int = 123, host_name: str = "玩家1"):
        """创建 HTTP 房间但不立即开始，供另一客户端按房间号加入。"""
        base_url = base_url or self._get_http_base_url()
        response = HTTPMultiplayerClient(base_url, timeout=1.5).create_room(
            host_name,
            max_players=2,
            turn_mode=turn_mode,
            map_seed=map_seed
        )
        if not response.get("success"):
            self._notify(f"创建 HTTP 房间失败：{response.get('message', '未知错误')}")
            return None
        room_id = response["room"]["room_id"]
        client_id = response["client_id"]
        self._remember_http_room_info(base_url, room_id, client_id)
        if self.ui_system.has_active_modal():
            self.ui_system.active_modal['lines'] = [
                "HTTP 等待房已创建，请记录以下信息。",
                f"房间ID: {room_id}",
                f"客户端ID: {client_id}",
                "另一客户端加入后，房主可用这些信息重连。"
            ]
        self._notify(f"HTTP 房间已创建：{room_id}，客户端：{client_id}")
        self._notify("另一客户端可用房间号加入；房主可稍后重连。")
        return response

    def _remember_http_room_info(self, base_url: str, room_id: str, client_id: str):
        """记录并回填最近 HTTP 房间信息。"""
        self.last_http_room_info = {
            "base_url": base_url,
            "room_id": room_id,
            "client_id": client_id,
        }
        if self.ui_system.has_active_modal():
            self.ui_system.set_modal_input_value("base_url", base_url)
            self.ui_system.set_modal_input_value("room_id", room_id)
            self.ui_system.set_modal_input_value("client_id", client_id)

    def _join_http_multiplayer_room(self, base_url: str = None, room_id: str = None,
                                    player_name: str = "玩家2", turn_mode: str = None,
                                    map_seed: int = None):
        """加入已有 HTTP 房间；满 2 人后尝试启动房间并进入游戏。"""
        base_url = base_url or self._get_http_base_url()
        room_id = room_id or os.environ.get("GEI_WORLD_ROOM_ID")
        player_name = os.environ.get("GEI_WORLD_PLAYER_NAME", player_name)
        if not room_id:
            self._notify("缺少房间号：请设置 GEI_WORLD_ROOM_ID。")
            return False
        http_client = HTTPMultiplayerClient(base_url, timeout=1.5)
        joined = http_client.join_room(room_id, player_name)
        if not joined.get("success"):
            self._notify(f"加入 HTTP 房间失败：{joined.get('message', '未知错误')}")
            return False
        client_id = joined["client_id"]
        start_response = http_client.start_room(room_id, map_seed=map_seed, turn_mode=turn_mode)
        if not start_response.get("success"):
            self._notify(f"加入成功但房间未开始：{start_response.get('message', '等待房主开始')}")
            return False
        session = HTTPNetworkSession(http_client, room_id, client_id)
        session.get_player_view()
        self._remember_http_room_info(base_url, room_id, client_id)
        self.multiplayer_server = None
        self.multiplayer_room_id = room_id
        self.multiplayer_sessions = {client_id: session}
        self.ai_manager = AIManager()
        self.game_started = True
        self._activate_multiplayer_client(client_id, notify=False)
        self._center_camera_on_map()
        self.ui_system.close_modal()
        self._notify(f"已加入 HTTP 房间：{room_id}，客户端：{client_id}")
        return True

    def _connect_http_multiplayer_existing(self, base_url: str = None, room_id: str = None,
                                           client_id: str = None):
        """使用已有 room_id/client_id 连接已开始的 HTTP 房间。"""
        base_url = base_url or self._get_http_base_url()
        room_id = room_id or os.environ.get("GEI_WORLD_ROOM_ID")
        client_id = client_id or os.environ.get("GEI_WORLD_CLIENT_ID")
        if not room_id or not client_id:
            self._notify("缺少房间号或客户端ID：请设置 GEI_WORLD_ROOM_ID / GEI_WORLD_CLIENT_ID。")
            return False
        http_client = HTTPMultiplayerClient(base_url, timeout=1.5)
        session = HTTPNetworkSession(http_client, room_id, client_id)
        view_response = session.get_player_view()
        if not view_response.get("success"):
            self._notify(f"连接 HTTP 房间失败：{view_response.get('message', '未知错误')}")
            return False
        self._remember_http_room_info(base_url, room_id, client_id)
        self.multiplayer_server = None
        self.multiplayer_room_id = room_id
        self.multiplayer_sessions = {client_id: session}
        self.ai_manager = AIManager()
        self.game_started = True
        self._activate_multiplayer_client(client_id, notify=False)
        self._center_camera_on_map()
        self.ui_system.close_modal()
        self._notify(f"已连接 HTTP 房间：{room_id}，客户端：{client_id}")
        return True

    def _activate_multiplayer_client(self, client_id: str, notify: bool = True) -> bool:
        """切换当前 UI 到指定多人客户端。"""
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
        """在本机多人客户端之间切换。"""
        if not self.multiplayer_sessions:
            return False
        client_ids = list(self.multiplayer_sessions.keys())
        if self.active_multiplayer_client_id not in client_ids:
            return self._activate_multiplayer_client(client_ids[0])
        next_index = (client_ids.index(self.active_multiplayer_client_id) + 1) % len(client_ids)
        return self._activate_multiplayer_client(client_ids[next_index])

    def _leave_multiplayer_room(self):
        """离开当前多人房间并回到开始界面。"""
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
        """显示离开多人房间确认。"""
        self.ui_system.show_modal(
            "离开多人房间",
            ["确定要离开当前多人房间吗？"],
            [
                {
                    'text': "继续游戏",
                    'callback': self.ui_system.close_modal,
                    'color': COLORS['LIGHT_GRAY'],
                    'text_color': COLORS['BLACK']
                },
                {
                    'text': "离开房间",
                    'callback': self._leave_multiplayer_room,
                    'color': COLORS['RED'],
                    'text_color': COLORS['WHITE']
                }
            ]
        )

    def _show_local_multiplayer_modal(self):
        """显示本机多人模式选择。"""
        self.ui_system.show_modal(
            "本机多人原型",
            ["创建一个进程内双人房间。", "开始后按 TAB 在两个玩家视角间切换。"],
            [
                {
                    'text': "轮流回合多人",
                    'callback': lambda: self._start_local_multiplayer("sequential"),
                    'color': COLORS['BLUE'],
                    'text_color': COLORS['WHITE']
                },
                {
                    'text': "同时回合多人",
                    'callback': lambda: self._start_local_multiplayer("simultaneous"),
                    'color': COLORS['GREEN'],
                    'text_color': COLORS['WHITE']
                },
                {
                    'text': "取消",
                    'callback': self.ui_system.close_modal,
                    'color': COLORS['LIGHT_GRAY'],
                    'text_color': COLORS['BLACK']
                }
            ]
        )

    def _get_http_form_values(self) -> Dict[str, str]:
        values = self.ui_system.get_modal_input_values()
        values.setdefault("base_url", self.last_http_room_info.get("base_url") or self._get_http_base_url())
        values.setdefault("room_id", self.last_http_room_info.get("room_id", ""))
        values.setdefault("client_id", self.last_http_room_info.get("client_id", ""))
        values.setdefault("turn_mode", os.environ.get("GEI_WORLD_TURN_MODE", "simultaneous"))
        return values

    def _show_http_multiplayer_modal(self):
        """显示 HTTP 多人模式选择。"""
        base_url = self.last_http_room_info.get("base_url") or self._get_http_base_url()
        room_id = os.environ.get("GEI_WORLD_ROOM_ID") or self.last_http_room_info.get("room_id", "")
        client_id = os.environ.get("GEI_WORLD_CLIENT_ID") or self.last_http_room_info.get("client_id", "")
        lines = ["填写服务/房间信息；TAB 切换输入框。"]
        if room_id or client_id:
            lines.extend([
                f"最近房间ID: {room_id or '无'}",
                f"最近客户端ID: {client_id or '无'}"
            ])
        self.ui_system.show_modal(
            "HTTP 多人原型",
            lines,
            [
                {
                    'text': "创建调试房",
                    'callback': lambda: self._start_http_multiplayer(
                        base_url=self._get_http_form_values().get("base_url"),
                        turn_mode=self._get_http_form_values().get("turn_mode", "simultaneous")
                    ),
                    'color': COLORS['GREEN'],
                    'text_color': COLORS['WHITE']
                },
                {
                    'text': "仅创建等待房",
                    'callback': lambda: self._create_http_room(
                        base_url=self._get_http_form_values().get("base_url"),
                        turn_mode=self._get_http_form_values().get("turn_mode", "simultaneous"),
                        host_name=self._get_http_form_values().get("player_name", "玩家1") or "玩家1"
                    ),
                    'color': COLORS['ORANGE'],
                    'text_color': COLORS['BLACK']
                },
                {
                    'text': "加入房间",
                    'callback': lambda: self._join_http_multiplayer_room(
                        base_url=self._get_http_form_values().get("base_url"),
                        room_id=self._get_http_form_values().get("room_id"),
                        player_name=self._get_http_form_values().get("player_name", "玩家2") or "玩家2",
                        turn_mode=self._get_http_form_values().get("turn_mode") or None
                    ),
                    'color': COLORS['PURPLE'],
                    'text_color': COLORS['WHITE']
                },
                {
                    'text': "重连房间",
                    'callback': lambda: self._connect_http_multiplayer_existing(
                        base_url=self._get_http_form_values().get("base_url"),
                        room_id=self._get_http_form_values().get("room_id"),
                        client_id=self._get_http_form_values().get("client_id")
                    ),
                    'color': COLORS['BLUE'],
                    'text_color': COLORS['WHITE']
                },
                {
                    'text': "取消",
                    'callback': self.ui_system.close_modal,
                    'color': COLORS['LIGHT_GRAY'],
                    'text_color': COLORS['BLACK']
                }
            ],
            inputs=[
                {"key": "base_url", "label": "服务地址", "value": base_url},
                {"key": "room_id", "label": "房间ID", "value": room_id},
                {"key": "client_id", "label": "客户端ID", "value": client_id},
                {"key": "player_name", "label": "玩家名", "value": os.environ.get("GEI_WORLD_PLAYER_NAME", "玩家2")},
                {"key": "turn_mode", "label": "回合模式", "value": os.environ.get("GEI_WORLD_TURN_MODE", "simultaneous")},
            ]
        )

    def _sync_multiplayer_room_notifications(self, room_state: Dict[str, Any]):
        """根据房间事件提示关闭、离线和重连状态。"""
        if not room_state:
            return
        for event in room_state.get("recent_events", []):
            event_type = event.get("event_type")
            if event_type not in {"player_left", "player_reconnected", "room_closed"}:
                continue
            sequence = event.get("sequence")
            event_key = sequence if sequence is not None else (event_type, event.get("player_name"), event.get("message"))
            if event_key in self.notified_multiplayer_event_sequences:
                continue
            self.notified_multiplayer_event_sequences.add(event_key)
            player_name = event.get("player_name") or "对手"
            active_seat = next(
                (seat for seat in room_state.get("seats", [])
                 if seat.get("client_id") == self.active_multiplayer_client_id),
                None
            )
            is_self_event = bool(active_seat and active_seat.get("player_id") == event.get("player_id"))
            if event_type == "room_closed":
                self._notify(event.get("message") or room_state.get("close_reason") or "房间已关闭")
            elif event_type == "player_left" and not is_self_event:
                self._notify(f"{player_name} 已离线，等待其重连。")
            elif event_type == "player_reconnected" and not is_self_event:
                self._notify(f"{player_name} 已重新连接。")

    def _invalidate_multiplayer_status(self):
        """使多人状态缓存失效，下一帧立即刷新。"""
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
        """拉取多人房间状态。"""
        active_player_id = self.session.player_id if hasattr(self.session, 'player_id') else self.local_player_id
        view_response = None
        if self.multiplayer_server:
            try:
                room_state = self.multiplayer_server.get_room_state(self.multiplayer_room_id)
                if self.active_multiplayer_client_id and not room_state.get("closed"):
                    view_response = self.multiplayer_server.get_player_view(
                        self.multiplayer_room_id,
                        self.active_multiplayer_client_id
                    )
            except KeyError as error:
                room_state = {"room_id": self.multiplayer_room_id, "closed": True, "close_reason": str(error)}
        elif hasattr(self.session, 'http_client'):
            room_response = self.session.http_client.get_room_state(self.multiplayer_room_id)
            room_state = room_response.get("room", {}) if room_response.get("success") else room_response.get("room", {})
            if not room_state:
                room_state = {"room_id": self.multiplayer_room_id, "closed": False, "close_reason": room_response.get("message", "")}
            if not room_state.get("closed"):
                view_response = self.session.get_player_view()
        else:
            return None
        self._sync_multiplayer_room_notifications(room_state)
        view = view_response.get("view") if view_response and view_response.get("success") else None
        visible_tile_count = 0
        explored_tile_count = 0
        if view:
            visible_tile_count = sum(1 for tile in view["tiles"].values() if tile.get("visible"))
            explored_tile_count = sum(1 for tile in view["tiles"].values() if tile.get("explored"))
        offline_seats = [
            seat for seat in room_state.get("seats", [])
            if not seat.get("connected") and seat.get("client_id") != self.active_multiplayer_client_id
        ]
        return {
            "room_id": self.multiplayer_room_id,
            "active_client_id": self.active_multiplayer_client_id,
            "active_player_id": active_player_id,
            "closed": room_state.get("closed", False),
            "close_reason": room_state.get("close_reason", ""),
            "seats": room_state.get("seats", []),
            "offline_seats": offline_seats,
            "recent_events": room_state.get("recent_events", []),
            "visible_tile_count": visible_tile_count,
            "explored_tile_count": explored_tile_count,
        }
