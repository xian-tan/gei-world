"""
UI客户端控制器 - UI与GameEngine的桥接
"""
import pygame
import sys
import os
from typing import Dict, Any, Optional, Set

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.game_session import HTTPNetworkSession, LocalGameSession, NetworkGameSession
from src.http_multiplayer import HTTPMultiplayerClient
from src.models import GameAction, ActionType, HexCoord, UnitType, Player
from src.multiplayer_server import MultiplayerServer
from src.systems.ai_system import AIManager
from src.systems.save_system import GameSaveSystem
from ui.systems.render_system import RenderSystem
from ui.systems.input_system import InputSystem, InputMode
from ui.systems.ui_system import UISystem
from ui.systems.camera_system import CameraSystem
from ui.hex_renderer import HexRenderer
from ui.ui_config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT, FPS, OFFSET_X, OFFSET_Y
from ui.font_manager import get_font_manager


class UIClient:
    """UI客户端 - 连接UI和游戏引擎"""
    
    def __init__(self):
        # 初始化pygame
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("六边形策略游戏")
        self.clock = pygame.time.Clock()
        
        # 游戏会话
        self.session = LocalGameSession()
        self.ai_manager = AIManager()
        self.save_system = GameSaveSystem()
        self.save_slots = [f"slot_{index}" for index in range(1, 6)]
        
        # UI系统
        self.render_system = RenderSystem()
        self.input_system = InputSystem()
        self.ui_system = UISystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.camera_system = CameraSystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # 状态
        self.running = True
        self.game_started = False
        self.move_mode_active = False
        self.local_player_id = None
        self.multiplayer_server = None
        self.multiplayer_room_id = None
        self.multiplayer_sessions = {}
        self.active_multiplayer_client_id = None
        self.notified_multiplayer_event_sequences = set()
        self.last_http_room_info = {}
        
        # 设置输入回调
        self._setup_input_callbacks()
        
        # 设置UI回调
        self._setup_ui_callbacks()        # 字体管理器
        self.font_manager = get_font_manager()
    
    @property
    def game_engine(self):
        """兼容旧调用的引擎访问入口。"""
        return self.session.engine
    
    @game_engine.setter
    def game_engine(self, engine):
        """兼容测试和存档加载流程的引擎替换入口。"""
        self.session = LocalGameSession(engine)
        self._clear_multiplayer_context()
    
    def _clear_multiplayer_context(self):
        """清理进程内多人房间上下文。"""
        self.multiplayer_server = None
        self.multiplayer_room_id = None
        self.multiplayer_sessions = {}
        self.active_multiplayer_client_id = None
        self.notified_multiplayer_event_sequences = set()
    
    def _setup_input_callbacks(self):
        """设置输入系统回调"""
        self.input_system.on_tile_clicked = self._handle_tile_click
        self.input_system.on_tile_right_clicked = self._handle_tile_right_click
        self.input_system.on_camera_move = self._handle_camera_move
        self.input_system.on_zoom = self._handle_zoom
        self.input_system.on_key_pressed = self._handle_key_press
        self.input_system.on_mouse_down = self.ui_system.handle_mouse_down
        self.input_system.on_mouse_drag = self.ui_system.handle_mouse_drag
        self.input_system.on_mouse_up = self.ui_system.handle_mouse_up
        self.input_system.on_text_input = self.ui_system.handle_text_input
    
    def _setup_ui_callbacks(self):
        """设置UI系统回调"""
        self.ui_system.set_callbacks(
            on_build_unit=self._handle_build_unit,
            on_end_turn=self._handle_end_turn,
            on_save_game=self._handle_save_game,
            on_load_game=self._handle_load_game,
            on_build_city=self._handle_build_city,
            on_return_to_menu=self._show_return_to_menu_modal
        )
    
    def _clear_ui_selection_state(self):
        """清理 UI 选中状态、城市面板和可达高亮。"""
        self.move_mode_active = False
        self.input_system.set_mode(InputMode.NORMAL)
        self.ui_system._close_city_panel()
        self.render_system.selected_tile = None
        self.render_system.clear_selected_unit()
        self.render_system.clear_reachable_tiles()
        self.render_system.clear_attention_tiles()
        self.render_system.clear_selected_city_economic_tiles()
    
    def _notify(self, message: str):
        """同时输出控制台和界面消息。"""
        print(message)
        self.ui_system.add_message(message)
    
    def _get_controlled_player(self) -> Optional[Player]:
        """获取当前 UI 视角下可操作/查看的玩家。"""
        return self.session.get_controlled_player(self.local_player_id)
    
    def _can_controlled_player_act(self) -> bool:
        """当前 UI 玩家是否还能在本回合行动。"""
        player = self._get_controlled_player()
        return bool(player and self.session.can_player_act(player.id))
    
    def _execute_action_and_notify(self, action: GameAction):
        """执行行动并显示引擎返回的结构化结果。"""
        result = self.session.submit_action(action)
        self._notify_action_result(result)
        return result
    
    def _notify_action_result(self, result, actor_name: str = None):
        """展示结构化行动结果，优先显示战斗/攻城等关键事件。"""
        priority_types = {"combat_resolved", "city_captured", "game_over"}
        has_priority_event = any(event.event_type in priority_types for event in result.events)
        messages = []
        
        if not has_priority_event and result.message:
            messages.append(result.message)
        
        has_combat_summary = False
        for event in result.events:
            if has_priority_event and event.event_type == "unit_moved":
                continue
            message = self._format_action_event(event)
            if not message:
                continue
            if event.event_type == "combat_resolved":
                has_combat_summary = True
            if event.event_type == "unit_destroyed" and has_combat_summary:
                continue
            if message not in messages:
                messages.append(message)
        
        if not messages and result.message:
            messages.append(result.message)
        
        for index, message in enumerate(messages):
            if actor_name and index == 0:
                self._notify(f"{actor_name}: {message}")
            else:
                self._notify(message)
    
    def _format_action_event(self, event) -> Optional[str]:
        """将行动事件格式化为更友好的 UI 文案。"""
        if event.event_type == "combat_resolved":
            destroyed_count = len(event.data.get("destroyed_unit_ids", []))
            return f"战斗结束：消灭 {destroyed_count} 个单位"
        if event.event_type == "unit_destroyed":
            return "单位被消灭"
        if event.event_type == "city_captured":
            return event.message or "城市被占领"
        if event.event_type == "game_over":
            return event.message or "游戏结束"
        if event.event_type == "unit_moved":
            from_terrain = event.data.get("from_terrain")
            to_terrain = event.data.get("to_terrain")
            if from_terrain == "land" and to_terrain == "ocean":
                return "单位下海，移动力已耗尽"
            if from_terrain == "ocean" and to_terrain == "ocean":
                return "单位在海上移动"
            if from_terrain == "ocean" and to_terrain == "land":
                return "单位登陆"
            return "单位移动成功"
        if event.event_type == "city_built":
            return event.message or "城市建立成功"
        if event.event_type == "unit_produced":
            return event.message or "单位生产成功"
        if event.event_type == "turn_ended":
            return event.message or "回合结束"
        return event.message
    
    def start_game(self, player_names: list, map_seed: int = None, turn_mode: str = "sequential"):
        """开始游戏"""
        new_session = LocalGameSession()
        if new_session.start_game(player_names, map_seed, turn_mode=turn_mode):
            self.session = new_session
            self._clear_multiplayer_context()
            self.game_started = True
            self.local_player_id = self.game_engine.player_system.players[0].id if self.game_engine.player_system.players else None
            self._clear_ui_selection_state()
            self.ui_system.close_modal()
            self._setup_ai_players()
            
            # 将摄像机移动到地图中心
            self._center_camera_on_map()
            
            self._notify(f"游戏开始！玩家: {', '.join(player_names)}")
            self._notify("新手提示：左键选中单位或城市，右键移动选中单位。")
            self._notify("移动到合适陆地后，按 B 或点击建城按钮建立第一座城市。")
            self._notify("目标：建城、生产士兵，探索并占领对手城市。")
            return True
        return False
    
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
    
    def _setup_ai_players(self):
        """将第一个玩家之外的玩家设为 AI。"""
        self.ai_manager = AIManager()
        self.game_engine.ai_player_configs = {}
        for player in self.game_engine.player_system.players[1:]:
            self.ai_manager.add_ai_player(player, "simple", "easy")
            self.game_engine.ai_player_configs[player.id] = {
                "ai_type": "simple",
                "difficulty": "easy"
            }
    
    def _restore_ai_players_from_engine(self):
        """根据引擎中的 AI 配置重建 AI 管理器。"""
        self.ai_manager = AIManager()
        for player_id, config in getattr(self.game_engine, 'ai_player_configs', {}).items():
            player = self.game_engine.player_system.get_player_by_id(player_id)
            if player:
                self.ai_manager.add_ai_player(
                    player,
                    config.get("ai_type", "simple"),
                    config.get("difficulty", "easy")
                )
    
    def _process_ai_turns(self):
        """自动处理连续 AI 回合，直到轮回人类玩家或游戏结束。"""
        safety_limit = 200
        per_ai_turn_limit = 20
        actions_taken = 0
        actions_this_turn = 0
        active_ai_player_id = None
        while not self.game_engine.game_over and actions_taken < safety_limit:
            current_player = self.game_engine.get_current_player()
            if not current_player or not self.ai_manager.is_ai_player(current_player.id):
                break
            if active_ai_player_id != current_player.id:
                active_ai_player_id = current_player.id
                actions_this_turn = 0
            
            if actions_this_turn >= per_ai_turn_limit:
                result = self.session.submit_action(GameAction(
                    player_id=current_player.id,
                    action_type=ActionType.END_TURN,
                    params={}
                ))
                actions_taken += 1
                actions_this_turn = 0
                self._notify_action_result(result, current_player.name)
                continue
            
            action = self.ai_manager.get_ai_action(current_player.id, self.game_engine)
            if not action:
                action = GameAction(
                    player_id=current_player.id,
                    action_type=ActionType.END_TURN,
                    params={}
                )
            
            result = self.session.submit_action(action)
            actions_taken += 1
            actions_this_turn += 1
            self._notify_action_result(result, current_player.name)
            if action.action_type == ActionType.END_TURN:
                actions_this_turn = 0
            elif not result.success:
                result = self.session.submit_action(GameAction(
                    player_id=current_player.id,
                    action_type=ActionType.END_TURN,
                    params={}
                ))
                actions_taken += 1
                actions_this_turn = 0
                self._notify_action_result(result, current_player.name)
        
        current_player = self.game_engine.get_current_player()
        if (not self.game_engine.game_over and current_player and
                self.ai_manager.is_ai_player(current_player.id)):
            result = self.session.submit_action(GameAction(
                player_id=current_player.id,
                action_type=ActionType.END_TURN,
                params={}
            ))
            self._notify_action_result(result, current_player.name)
    
    def _process_simultaneous_ai_turns(self):
        """同时回合模式下处理所有仍可行动的 AI，直到 AI 全部结束本回合。"""
        safety_limit = 200
        per_ai_turn_limit = 20
        actions_taken = 0
        actions_by_player = {}
        starting_turn = self.game_engine.turn_system.current_turn
        while (not self.game_engine.game_over and actions_taken < safety_limit and
               self.game_engine.turn_system.current_turn == starting_turn):
            ai_players = [
                player for player in self.game_engine.player_system.players
                if self.ai_manager.is_ai_player(player.id)
                and self.game_engine.turn_system.can_player_act(player.id)
            ]
            if not ai_players:
                break
            for current_player in ai_players:
                actions_this_turn = actions_by_player.get(current_player.id, 0)
                if actions_this_turn >= per_ai_turn_limit:
                    action = GameAction(
                        player_id=current_player.id,
                        action_type=ActionType.END_TURN,
                        params={}
                    )
                else:
                    action = self.ai_manager.get_ai_action(current_player.id, self.game_engine)
                    if not action:
                        action = GameAction(
                            player_id=current_player.id,
                            action_type=ActionType.END_TURN,
                            params={}
                        )
                
                result = self.session.submit_action(action)
                actions_taken += 1
                self._notify_action_result(result, current_player.name)
                if self.game_engine.turn_system.current_turn != starting_turn:
                    break
                if action.action_type == ActionType.END_TURN:
                    actions_by_player[current_player.id] = 0
                    continue
                if not result.success:
                    if self.game_engine.turn_system.can_player_act(current_player.id):
                        end_result = self.session.submit_action(GameAction(
                            player_id=current_player.id,
                            action_type=ActionType.END_TURN,
                            params={}
                        ))
                        actions_taken += 1
                        self._notify_action_result(end_result, current_player.name)
                    actions_by_player[current_player.id] = 0
                else:
                    actions_by_player[current_player.id] = actions_this_turn + 1
            
    def _center_camera_on_map(self):
        """将摄像机居中到地图"""
        if not self.game_engine.map_tiles:
            return
        
        # 计算地图边界
        min_q = min(coord.q for coord in self.game_engine.map_tiles.keys())
        max_q = max(coord.q for coord in self.game_engine.map_tiles.keys())
        min_r = min(coord.r for coord in self.game_engine.map_tiles.keys())
        max_r = max(coord.r for coord in self.game_engine.map_tiles.keys())
        
        # 计算地图中心
        center_q = (min_q + max_q) / 2
        center_r = (min_r + max_r) / 2
        center_x, center_y = HexRenderer.hex_to_pixel(center_q, center_r, OFFSET_X, OFFSET_Y)
        
        self.camera_system.set_position(center_x, center_y)
    
    def run(self):
        """运行主循环"""
        while self.running:
            # 处理事件
            events = pygame.event.get()
            if not self.input_system.handle_events(events):
                self.running = False
                break
            
            # 更新输入系统
            self.input_system.update()
            
            # 渲染
            self._render()
            
            # 控制帧率
            self.clock.tick(FPS)
        
        pygame.quit()
    
    def _render(self):
        """渲染游戏画面"""
        # 清屏
        self.screen.fill(COLORS['MAP_BACKGROUND'] if self.game_started else COLORS['BLACK'])
        
        if self.game_started:
            # 获取游戏状态
            game_state = self._get_game_state()
            
            # 更新渲染系统摄像机
            self.render_system.camera_x, self.render_system.camera_y = self.camera_system.get_position()
            self.render_system.zoom = self.camera_system.get_zoom()
            
            # 渲染地图
            view_player = self._get_controlled_player()
            visible_tiles = self.session.get_visible_tiles(view_player.id) if view_player else set()
            explored_tiles = self.session.get_explored_tiles(view_player.id) if view_player else set()
            
            self._update_hover_path_preview(visible_tiles)
            self.render_system.render_map(
                self.screen,
                self.game_engine.map_tiles,
                visible_tiles,
                explored_tiles,
                view_player
            )
            
            # 渲染UI
            self.ui_system.render(self.screen, game_state)
            self.render_system.render_minimap(
                self.screen,
                self.game_engine.map_tiles,
                visible_tiles,
                explored_tiles
            )
            self.ui_system.render_modal(self.screen)
        else:
            # 显示开始界面
            self._render_start_screen()
            self.ui_system.render_modal(self.screen)
        
        pygame.display.flip()
    def _render_start_screen(self):
        """渲染开始界面"""
        title = self.font_manager.render_text("六边形策略游戏", 'large', COLORS['WHITE'])
        title_rect = title.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 120))
        self.screen.blit(title, title_rect)
        
        instructions = [
            "SPACE 单人轮流回合",
            "T 单人同时回合",
            "M 本机多人原型",
            "H 连接HTTP多人(本机)",
            "L 加载游戏",
            "ESC 退出",
        ]
        for index, text in enumerate(instructions):
            instruction = self.font_manager.render_text(text, 'medium', COLORS['WHITE'])
            instruction_rect = instruction.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 55 + index * 34))
            self.screen.blit(instruction, instruction_rect)
        
        if self.ui_system.messages:
            message = self.font_manager.render_text(self.ui_system.messages[-1], 'small', COLORS['LIGHT_GRAY'])
            message_rect = message.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 75))
            self.screen.blit(message, message_rect)
        if self.last_http_room_info:
            room_id = self.last_http_room_info.get("room_id", "")
            client_id = self.last_http_room_info.get("client_id", "")
            lines = [
                f"最近HTTP房间: {room_id}",
                f"最近客户端ID: {client_id}",
            ]
            for index, line in enumerate(lines):
                info = self.font_manager.render_text(line, 'small', COLORS['LIGHT_GRAY'])
                info_rect = info.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 105 + index * 22))
                self.screen.blit(info, info_rect)
    
    def _update_hover_path_preview(self, visible_tiles: Set[HexCoord]):
        """根据鼠标悬停位置更新移动路径预览。"""
        mouse_pos = self.input_system.mouse_pos
        hovered_coord = self._get_tile_at_screen_pos(mouse_pos[0], mouse_pos[1])
        self.render_system.hovered_tile = hovered_coord
        self.render_system.clear_path_preview()
        if not hovered_coord or hovered_coord not in visible_tiles:
            return
        if not self.input_system.is_unit_selected():
            return
        if hovered_coord not in self.render_system.reachable_tiles:
            return
        unit = self._find_unit_by_id(self.input_system.get_selected_unit_id())
        if not unit or hovered_coord == unit.position:
            return
        path = self.game_engine.unit_system.find_movement_path(
            unit,
            hovered_coord,
            self.game_engine.map_tiles
        )
        if path:
            self.render_system.set_path_preview(path)
    
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
    
    def _get_multiplayer_status(self) -> Optional[Dict[str, Any]]:
        """获取多人房间状态摘要。"""
        if not self.multiplayer_room_id:
            return None
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
    
    def _get_game_state(self) -> Dict[str, Any]:
        """获取游戏状态快照"""
        controlled_player = self._get_controlled_player()
        current_income = self.game_engine.player_system.calculate_income(controlled_player, self.game_engine.map_tiles) if controlled_player else 0
        selected_coord = self.render_system.selected_tile
        selected_tile = self.game_engine.map_tiles.get(selected_coord) if selected_coord else None
        selected_unit = self._find_unit_by_id(self.input_system.get_selected_unit_id()) if self.input_system.is_unit_selected() else None
        selected_city = self.ui_system.selected_city if self.ui_system.show_city_panel else None
        turn_status = self.session.get_turn_status()
        multiplayer_status = self._get_multiplayer_status()
        can_act = self._can_controlled_player_act()
        if multiplayer_status and multiplayer_status.get("closed"):
            can_act = False
        
        return {
            'current_player': controlled_player,
            'current_income': current_income,
            'turn_number': self.game_engine.turn_system.turn_number,
            'turn_mode': self.game_engine.turn_system.mode,
            'turn_status': turn_status,
            'can_act': can_act,
            'game_over': self.game_engine.game_over,
            'winner': self.game_engine.winner,
            'selected_coord': selected_coord,
            'selected_tile': selected_tile,
            'selected_unit': selected_unit,
            'selected_city': selected_city,
            'move_mode_active': self.move_mode_active,
            'multiplayer_status': multiplayer_status
        }
    
    def _get_tile_at_screen_pos(self, screen_x: int, screen_y: int) -> Optional[HexCoord]:
        """获取屏幕位置对应的地块"""
        world_x, world_y = self.camera_system.screen_to_world(screen_x, screen_y)
        q, r = HexRenderer.pixel_to_hex(world_x, world_y, OFFSET_X, OFFSET_Y)
        coord = HexCoord(q, r)
        
        # 检查坐标是否在地图范围内
        if coord in self.game_engine.map_tiles:
            return coord
        return None
    
    def _handle_tile_click(self, screen_pos):
        """处理地块点击"""
        # 先检查UI是否处理了点击
        if self.ui_system.handle_click(screen_pos):
            return
        if self.render_system.is_minimap_pos(screen_pos):
            return
        
        coord = self._get_tile_at_screen_pos(screen_pos[0], screen_pos[1])
        if not coord:
            if self._has_cancelable_ui_state():
                self._clear_ui_selection_state()
            return
        
        tile = self.game_engine.map_tiles.get(coord)
        if not tile:
            return
        
        current_player = self._get_controlled_player()
        
        # 根据当前模式处理点击；左键只负责选择/切换，空地取消选中
        if self.input_system.mode == InputMode.NORMAL:
            self._handle_normal_click(tile, current_player)
        elif self.input_system.mode == InputMode.UNIT_SELECTED:
            self._handle_unit_selected_click(tile, current_player)
        elif self.input_system.mode == InputMode.CITY_SELECTED:
            self._handle_city_selected_click(tile, current_player)
        
        if self.input_system.mode != InputMode.NORMAL or self.ui_system.show_city_panel or self.render_system.selected_unit_id:
            self.render_system.selected_tile = coord
    def _handle_normal_click(self, tile, current_player):
        """处理普通模式点击"""
        if not self._cycle_selectable_on_tile(tile, current_player):
            self._clear_ui_selection_state()
    
    def _get_selectables_on_tile(self, tile, current_player):
        """获取当前地块上可循环选择的己方对象。"""
        selectables = []
        for unit in tile.units:
            if unit.owner == current_player:
                selectables.append(("unit", unit.id, unit))
        if tile.city and tile.city.owner == current_player:
            selectables.append(("city", tile.city.id, tile.city))
        return selectables
    
    def _get_current_selection_key(self) -> Optional[tuple]:
        """获取当前选中对象标识。"""
        if self.input_system.is_unit_selected():
            return ("unit", self.input_system.get_selected_unit_id())
        if self.input_system.is_city_selected():
            return ("city", self.input_system.get_selected_city_id())
        return None
    
    def _cycle_selectable_on_tile(self, tile, current_player) -> bool:
        """在同一地块的多个单位/城市之间循环选择。"""
        selectables = self._get_selectables_on_tile(tile, current_player)
        if not selectables:
            return False
        
        current_key = self._get_current_selection_key()
        selected_index = 0
        if current_key:
            keys = [(item_type, item_id) for item_type, item_id, _ in selectables]
            if current_key in keys:
                selected_index = (keys.index(current_key) + 1) % len(selectables)
        
        item_type, _, item = selectables[selected_index]
        if item_type == "unit":
            self._select_unit(item)
        else:
            self._select_city(item, current_player)
        return True
    
    def _select_unit(self, unit):
        """选中单位并刷新右键移动范围。"""
        self.move_mode_active = False
        self.input_system.set_mode(InputMode.UNIT_SELECTED, unit.id)
        self.ui_system._close_city_panel()
        self.render_system.set_selected_unit(unit.id)
        self.render_system.clear_attention_tiles()
        self.render_system.clear_path_preview()
        self.render_system.clear_selected_city_economic_tiles()
        reachable_tiles = self.game_engine.unit_system.get_reachable_tiles(unit, self.game_engine.map_tiles)
        self.render_system.set_reachable_tiles(set(reachable_tiles))
        if unit.unit_type == UnitType.SETTLER:
            self._notify(f"选中移民：移动力 {unit.movement_points}。右键移动，按 B 或点击建城按钮建城。")
        elif unit.unit_type == UnitType.SOLDIER:
            self._notify(f"选中士兵：{unit.quantity} 名，移动力 {unit.movement_points}。右键移动/攻击，按 M 全选，按 1-9 设置移动人数。")
        else:
            self._notify(f"选中单位: {unit.unit_type.value} (移动力: {unit.movement_points})，右键移动。")
        if unit.movement_points <= 0:
            self._notify("该单位本回合移动力已用完，请点击结束回合恢复。")
    
    def _select_city(self, city, current_player):
        """选中城市并打开城市面板。"""
        self.move_mode_active = False
        self.input_system.set_mode(InputMode.CITY_SELECTED, city.id)
        self.ui_system.show_city_panel_for(city)
        self.render_system.selected_tile = city.center_tile
        self.render_system.clear_selected_unit()
        self.render_system.clear_reachable_tiles()
        self.render_system.clear_attention_tiles()
        economic_tiles = self.game_engine.city_system.get_city_economic_tiles(city, self.game_engine.map_tiles)
        self.render_system.set_selected_city_economic_tiles(economic_tiles)
        self._notify(f"选中城市：当前金币 {current_player.gold}。可在城市面板生产移民或士兵。")
    
    def _handle_unit_selected_click(self, tile, current_player):
        """处理选中单位时的左键选择。"""
        if not self._cycle_selectable_on_tile(tile, current_player):
            self._clear_ui_selection_state()
    
    def _handle_unit_move_click(self, tile, current_player):
        """处理移动模式下的单位移动点击。"""
        unit_id = self.input_system.get_selected_unit_id()
        unit = self._find_unit_by_id(unit_id)
        
        if not unit:
            self._clear_ui_selection_state()
            return
        
        if tile.coord == unit.position:
            self._notify("已在当前位置，选择黄色范围内的目标地块移动。")
            return
        
        move_quantity = 1
        if unit.unit_type == UnitType.SOLDIER:
            move_quantity = max(1, min(self.ui_system.move_soldier_quantity, unit.quantity))
        
        move_failure = self.game_engine.unit_system.get_move_failure_reason(unit, tile.coord, self.game_engine.map_tiles)
        if move_failure:
            self._notify(move_failure)
            return
        
        self.render_system.clear_attention_tiles()
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.MOVE_UNIT,
            params={
                'unit_id': unit_id,
                'move_quantity': move_quantity,
                'target': [tile.coord.q, tile.coord.r]
            }
        )
        
        result = self._execute_action_and_notify(action)
        if result.success:
            moved_unit_id = action.params.get('unit_id', unit_id)
            if move_quantity > 1 and unit.unit_type == UnitType.SOLDIER:
                self._notify(f"已移动 {move_quantity} 名士兵")
            unit = self._find_unit_by_id(moved_unit_id)
            if unit:
                self.input_system.set_mode(InputMode.UNIT_SELECTED, unit.id)
                self.render_system.set_selected_unit(unit.id)
                if unit.movement_points <= 0:
                    self._notify("移动力已耗尽，已取消选中。")
                    self._clear_ui_selection_state()
                else:
                    reachable_tiles = self.game_engine.unit_system.get_reachable_tiles(unit, self.game_engine.map_tiles)
                    self.render_system.set_reachable_tiles(set(reachable_tiles))
            else:
                self._clear_ui_selection_state()
    
    def _handle_city_selected_click(self, tile, current_player):
        """处理选中城市时的点击"""
        # 点击当前城市所在格时，在同格单位/城市之间循环选择
        if tile.city == self.ui_system.selected_city:
            self._cycle_selectable_on_tile(tile, current_player)
            return
        
        self.ui_system._close_city_panel()
        self.input_system.set_mode(InputMode.NORMAL)
        
        # 如果点击了其他对象，递归处理
        self._handle_normal_click(tile, current_player)
    
    def _handle_tile_right_click(self, screen_pos):
        """处理右键：选中单位时移动。"""
        if self.ui_system.has_active_modal():
            self.ui_system.close_modal()
            return
        coord = self._get_tile_at_screen_pos(screen_pos[0], screen_pos[1])
        if not coord:
            return
        tile = self.game_engine.map_tiles.get(coord)
        current_player = self._get_controlled_player()
        if tile and self.input_system.is_unit_selected():
            self._handle_unit_move_click(tile, current_player)
    
    def _has_cancelable_ui_state(self) -> bool:
        """是否存在可先取消的 UI 状态。"""
        return bool(
            self.input_system.mode != InputMode.NORMAL
            or self.ui_system.show_city_panel
            or self.render_system.selected_tile
            or self.render_system.selected_unit_id
            or self.render_system.reachable_tiles
            or self.render_system.selected_city_economic_tiles
            or self.render_system.path_preview
            or self.move_mode_active
        )
    
    def _show_return_to_menu_modal(self):
        """显示返回主菜单确认弹窗。"""
        lines = ["确定要返回主菜单吗？", "未保存的进度会丢失。"]
        if self.multiplayer_room_id:
            lines.append("多人房间会先执行离开；房主退出会关闭房间。")
        self.ui_system.show_modal(
            "返回主菜单",
            lines,
            [
                {
                    'text': "继续游戏",
                    'callback': self.ui_system.close_modal,
                    'color': COLORS['LIGHT_GRAY'],
                    'text_color': COLORS['BLACK']
                },
                {
                    'text': "返回主菜单",
                    'callback': self._confirm_return_to_main_menu,
                    'color': COLORS['ORANGE'],
                    'text_color': COLORS['BLACK']
                }
            ]
        )
    
    def _confirm_return_to_main_menu(self):
        """确认返回主菜单。"""
        if self.multiplayer_room_id:
            if hasattr(self.session, 'leave_room'):
                response = self.session.leave_room()
                if not response.get("success"):
                    self._notify(f"离开房间失败，已返回主菜单：{response.get('message', '未知错误')}")
            elif self.multiplayer_server and self.active_multiplayer_client_id:
                self.multiplayer_server.leave_room(self.multiplayer_room_id, self.active_multiplayer_client_id)
        self._clear_multiplayer_context()
        self.session = LocalGameSession()
        self.ai_manager = AIManager()
        self.game_started = False
        self.local_player_id = None
        self._clear_ui_selection_state()
        self.ui_system.close_modal()
        self._notify("已返回主菜单。")
        return True
    
    def _show_exit_confirmation(self):
        """显示退出确认弹窗。"""
        actions = [
            {
                'text': "取消",
                'callback': self.ui_system.close_modal,
                'color': COLORS['LIGHT_GRAY'],
                'text_color': COLORS['BLACK']
            }
        ]
        if self.game_started:
            actions.append({
                'text': "返回主菜单",
                'callback': self._confirm_return_to_main_menu,
                'color': COLORS['ORANGE'],
                'text_color': COLORS['BLACK']
            })
        actions.append({
            'text': "退出游戏",
            'callback': self._confirm_exit_game,
            'color': COLORS['RED'],
            'text_color': COLORS['WHITE']
        })
        self.ui_system.show_modal(
            "确认退出",
            ["确定要退出游戏吗？", "未保存的进度会丢失。"],
            actions
        )
    
    def _confirm_exit_game(self):
        """确认退出游戏。"""
        self.ui_system.close_modal()
        self.running = False
    
    def _handle_camera_move(self, dx: int, dy: int):
        """处理摄像机移动"""
        self.camera_system.move(dx, dy)
    
    def _handle_zoom(self, zoom_factor: float):
        """处理缩放"""
        mouse_x, mouse_y = self.input_system.mouse_pos
        self.camera_system.zoom_at(zoom_factor, mouse_x, mouse_y)
    
    def _handle_soldier_quantity_hotkey(self, key: int) -> bool:
        """处理选中士兵时的移动数量快捷键。"""
        if not self.input_system.is_unit_selected():
            return False
        unit = self._find_unit_by_id(self.input_system.get_selected_unit_id())
        current_player = self._get_controlled_player()
        if not unit or not current_player:
            return False
        if unit.owner != current_player or unit.unit_type != UnitType.SOLDIER:
            return False
        
        quantity_by_key = {
            pygame.K_1: 1,
            pygame.K_2: 2,
            pygame.K_3: 3,
            pygame.K_4: 4,
            pygame.K_5: 5,
            pygame.K_6: 6,
            pygame.K_7: 7,
            pygame.K_8: 8,
            pygame.K_9: 9,
            pygame.K_KP1: 1,
            pygame.K_KP2: 2,
            pygame.K_KP3: 3,
            pygame.K_KP4: 4,
            pygame.K_KP5: 5,
            pygame.K_KP6: 6,
            pygame.K_KP7: 7,
            pygame.K_KP8: 8,
            pygame.K_KP9: 9,
        }
        max_quantity = max(1, unit.quantity)
        if key == pygame.K_m:
            quantity = max_quantity
        elif key in quantity_by_key:
            quantity = min(quantity_by_key[key], max_quantity)
        else:
            return False
        
        self.ui_system.move_soldier_quantity = quantity
        self._notify(f"移动士兵数量已设为 {quantity}/{max_quantity}")
        return True
    
    def _handle_key_press(self, key: int, pressed: bool):
        """处理按键"""
        if not pressed:  # 只处理按下事件
            return
        
        if key == pygame.K_ESCAPE:
            if self.ui_system.has_active_modal():
                self.ui_system.close_modal()
            elif self.game_started and not self.game_engine.game_over and self._has_cancelable_ui_state():
                self._clear_ui_selection_state()
            else:
                self._show_exit_confirmation()
            return
        
        if self.ui_system.has_active_modal():
            if self.ui_system.handle_key_press(key):
                return
            return
        
        if not self.game_started:
            if key == pygame.K_SPACE:
                self.start_game(["玩家1", "AI玩家"], turn_mode="sequential")
            elif key == pygame.K_t:
                self.start_game(["玩家1", "AI玩家"], turn_mode="simultaneous")
            elif key == pygame.K_m:
                self._show_local_multiplayer_modal()
            elif key == pygame.K_h:
                self._show_http_multiplayer_modal()
            elif key == pygame.K_l:
                self._handle_load_game()
            return
        
        if key == pygame.K_TAB and self._switch_multiplayer_client():
            return
        if key == pygame.K_q and self.multiplayer_room_id:
            self._show_leave_multiplayer_modal()
            return
        
        if self.game_engine.game_over:
            if key == pygame.K_r:
                self.start_game(["玩家1", "AI玩家"], turn_mode=self.game_engine.turn_system.mode)
            return
        
        if self._handle_soldier_quantity_hotkey(key):
            return
        
        if key == pygame.K_b:
            self._handle_build_city()
            return
    
    def _handle_build_city(self):
        """处理移民建城。"""
        unit_id = self.input_system.get_selected_unit_id()
        unit = self._find_unit_by_id(unit_id) if unit_id else None
        current_player = self._get_controlled_player()
        if not unit:
            self._notify("请先选中一个移民，再建城。")
            return
        if unit.owner != current_player:
            self._notify("只能使用自己的移民建城。")
            return
        if unit.unit_type != UnitType.SETTLER:
            self._notify("只有移民可以建城。")
            return
        
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.BUILD_CITY,
            params={'unit_id': unit_id}
        )
        result = self._execute_action_and_notify(action)
        if result.success:
            self._clear_ui_selection_state()
    
    def _handle_build_unit(self, city_id: str, unit_type: UnitType, quantity: int = 1):
        """处理建造单位。"""
        current_player = self._get_controlled_player()
        if not current_player:
            return
        quantity = 1 if unit_type == UnitType.SETTLER else max(1, quantity)
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.BUILD_UNIT,
            params={
                'city_id': city_id,
                'unit_type': unit_type.value,
                'quantity': quantity
            }
        )
        result = self.session.submit_action(action)
        if result.success and quantity > 1 and unit_type == UnitType.SOLDIER:
            self._notify(f"生产士兵 {quantity} 名")
        else:
            self._notify_action_result(result)
    
    def _handle_end_turn(self, force: bool = False):
        """处理结束回合；有单位仍可移动时先确认。"""
        current_player = self._get_controlled_player()
        if not current_player:
            return
        if not force:
            movable_units = [
                unit for unit in current_player.units
                if unit.movement_points > 0
            ]
            if movable_units:
                self.render_system.set_attention_tiles({unit.position for unit in movable_units})
                self.ui_system.show_modal(
                    "仍有单位可移动",
                    [f"还有 {len(movable_units)} 个单位/士兵栈保留移动力。", "橙色轮廓已在地图上标出。", "确定要结束回合吗？"],
                    [
                        {
                            'text': "继续操作",
                            'callback': self.ui_system.close_modal,
                            'color': COLORS['LIGHT_GRAY'],
                            'text_color': COLORS['BLACK']
                        },
                        {
                            'text': "仍然结束回合",
                            'callback': lambda: self._handle_end_turn(force=True),
                            'color': COLORS['GREEN'],
                            'text_color': COLORS['WHITE']
                        }
                    ]
                )
                return
        
        self.ui_system.close_modal()
        self.render_system.clear_attention_tiles()
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.END_TURN,
            params={}
        )
        
        result = self._execute_action_and_notify(action)
        if result.success:
            self._clear_ui_selection_state()
            turn_advanced = any(
                event.event_type == "turn_advanced"
                or event.data.get("turn_advanced")
                for event in result.events
            )
            if self.multiplayer_room_id and not turn_advanced:
                self._notify("等待其他玩家结束本回合。")
            if self.game_engine.turn_system.mode == "sequential":
                self._process_ai_turns()
            else:
                self._process_simultaneous_ai_turns()
    
    def _format_save_summary(self, save_info: Dict[str, Any]) -> str:
        """格式化存档列表项。"""
        timestamp = str(save_info.get('timestamp', '未知'))[:16].replace('T', ' ')
        return f"{save_info.get('name', '未知')} | 回合 {save_info.get('turn', 0)} | {timestamp}"
    
    def _handle_save_game(self, save_name: str = None):
        """处理保存游戏。无存档名时打开多存档槽位面板。"""
        if save_name is None:
            self._show_save_slots_modal()
            return
        try:
            success = self.save_system.save_game(self.game_engine, save_name)
            self.ui_system.close_modal()
            if success:
                self._notify(f"游戏已保存到 {save_name}.json")
            else:
                self._notify("保存失败")
        except Exception as e:
            self._notify(f"保存游戏时出错: {e}")
    
    def _show_save_slots_modal(self):
        """显示固定多存档槽位。"""
        saves_by_name = {save['name']: save for save in self.save_system.list_saves()}
        actions = []
        for index, save_name in enumerate(self.save_slots, start=1):
            existing = saves_by_name.get(save_name)
            label = f"保存槽 {index}：空"
            if existing:
                label = f"覆盖槽 {index}：{self._format_save_summary(existing)}"
            actions.append({
                'text': label,
                'callback': lambda name=save_name: self._handle_save_game(name),
                'color': COLORS['BLUE'],
                'text_color': COLORS['WHITE']
            })
        actions.append({
            'text': "取消",
            'callback': self.ui_system.close_modal,
            'color': COLORS['LIGHT_GRAY'],
            'text_color': COLORS['BLACK']
        })
        self.ui_system.show_modal("保存游戏", ["选择一个槽位保存；已有存档会被覆盖。"], actions)
    
    def _handle_load_game(self, save_name: str = None):
        """处理加载游戏。无存档名时打开存档列表。"""
        if save_name is None:
            self._show_load_saves_modal()
            return
        self._load_save(save_name)
    
    def _show_load_saves_modal(self):
        """显示可加载存档列表。"""
        saves = self.save_system.list_saves()
        if not saves:
            self.ui_system.show_modal(
                "加载游戏",
                ["没有找到任何存档。"],
                [{
                    'text': "关闭",
                    'callback': self.ui_system.close_modal,
                    'color': COLORS['LIGHT_GRAY'],
                    'text_color': COLORS['BLACK']
                }]
            )
            return
        actions = []
        for save in saves[:8]:
            save_name = save['name']
            actions.append({
                'text': self._format_save_summary(save),
                'callback': lambda name=save_name: self._load_save(name),
                'color': COLORS['ORANGE'],
                'text_color': COLORS['BLACK']
            })
        actions.append({
            'text': "取消",
            'callback': self.ui_system.close_modal,
            'color': COLORS['LIGHT_GRAY'],
            'text_color': COLORS['BLACK']
        })
        self.ui_system.show_modal("加载游戏", ["选择要读取的存档。"], actions)
    
    def _load_save(self, save_name: str):
        """按名称读取指定存档。"""
        try:
            loaded_engine = self.save_system.load_game(save_name)
            if not loaded_engine:
                self._notify(f"加载失败：未找到 {save_name}.json")
                return
            
            self.session = LocalGameSession(loaded_engine)
            self._clear_multiplayer_context()
            self.game_started = True
            if not self.game_engine.player_system.get_player_by_id(self.local_player_id):
                self.local_player_id = self.game_engine.player_system.players[0].id if self.game_engine.player_system.players else None
            self._restore_ai_players_from_engine()
            self._clear_ui_selection_state()
            self.ui_system.close_modal()
            self._center_camera_on_map()
            self._notify(f"已加载 {save_name}.json")
            self._process_ai_turns()
        except Exception as e:
            self._notify(f"加载游戏时出错: {e}")
    
    def _find_unit_by_id(self, unit_id: str):
        """根据ID查找单位"""
        for player in self.game_engine.player_system.players:
            for unit in player.units:
                if unit.id == unit_id:
                    return unit
        return None
