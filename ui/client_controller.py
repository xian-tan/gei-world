"""
UI 客户端：pygame 主循环、渲染调度与按键分发。

具体职责拆分在 ui/controllers 下的各个 Mixin 中：
- MenuMixin：主菜单、新游戏设置
- FeedbackMixin：行动结果消息与地图浮字
- GameFlowMixin：开局/重开、AI 回合、热座、结束回合、菜单/退出
- SelectionMixin：地图选择、移动、建城、生产
- PersistenceMixin：存档/读档
- MultiplayerMixin：本机与 HTTP 多人房间
"""
from typing import Any, Dict, Optional

import pygame

from src.game_session import LocalGameSession
from src.models import GameAction, Player
from src.systems.ai_system import AIManager
from src.systems.save_system import GameSaveSystem
from ui.controllers.feedback import FeedbackMixin
from ui.controllers.game_flow import GameFlowMixin
from ui.controllers.menu import MenuMixin
from ui.controllers.multiplayer import MultiplayerMixin
from ui.controllers.persistence import PersistenceMixin
from ui.controllers.selection import SelectionMixin
from ui.font_manager import get_font_manager
from ui.hex_renderer import HexRenderer
from ui.systems.camera_system import CameraSystem
from ui.systems.input_system import InputSystem
from ui.systems.render_system import RenderSystem
from ui.systems.ui_system import UISystem
from ui.ui_config import COLORS, FPS, OFFSET_X, OFFSET_Y, SCREEN_HEIGHT, SCREEN_WIDTH


class UIClient(MenuMixin, FeedbackMixin, GameFlowMixin, SelectionMixin, PersistenceMixin, MultiplayerMixin):
    """UI客户端 - 连接UI和游戏引擎"""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Gei World · 六边形策略")
        self.clock = pygame.time.Clock()

        self.session = LocalGameSession()
        self.ai_manager = AIManager()
        self.save_system = GameSaveSystem()
        self.save_slots = [f"slot_{index}" for index in range(1, 6)]

        self.render_system = RenderSystem()
        self.input_system = InputSystem()
        self.ui_system = UISystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.camera_system = CameraSystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.font_manager = get_font_manager()

        self.running = True
        self.game_started = False
        self.move_mode_active = False
        self.local_player_id = None
        self.human_player_ids = []
        self.last_game_settings = {}
        self.multiplayer_server = None
        self.multiplayer_room_id = None
        self.multiplayer_sessions = {}
        self.active_multiplayer_client_id = None
        self.notified_multiplayer_event_sequences = set()
        self.last_http_room_info = {}
        self.pending_host_room = None
        self.multiplayer_poll_interval = 0.5
        self._multiplayer_status_cache = None
        self._multiplayer_status_time = 0.0
        self._pending_poll_time = 0.0

        self._setup_input_callbacks()
        self._setup_ui_callbacks()

    @property
    def game_engine(self):
        """当前会话引擎（多人时为服务端权威引擎或只读镜像）。"""
        return self.session.engine

    @game_engine.setter
    def game_engine(self, engine):
        """测试与读档使用的引擎替换入口。"""
        self.session = LocalGameSession(engine)
        self._clear_multiplayer_context()

    def _setup_input_callbacks(self):
        self.input_system.on_tile_clicked = self._handle_tile_click
        self.input_system.on_tile_right_clicked = self._handle_tile_right_click
        self.input_system.on_camera_move = self._handle_camera_move
        self.input_system.on_zoom = self._handle_zoom
        self.input_system.on_key_pressed = self._handle_key_press
        self.input_system.on_mouse_down = self._handle_mouse_down
        self.input_system.on_mouse_drag = self.ui_system.handle_mouse_drag
        self.input_system.on_mouse_up = self.ui_system.handle_mouse_up
        self.input_system.on_text_input = self.ui_system.handle_text_input
        self.input_system.on_resize = self._handle_resize

    def _setup_ui_callbacks(self):
        self.ui_system.set_callbacks(
            on_build_unit=self._handle_build_unit,
            on_end_turn=self._handle_end_turn,
            on_save_game=self._handle_save_game,
            on_load_game=self._handle_load_game,
            on_build_city=self._handle_build_city,
            on_return_to_menu=self._show_return_to_menu_modal,
            on_restart=self._restart_game,
        )

    def _handle_mouse_down(self, pos) -> bool:
        """左键按下：滑块拖动，或落在 UI 上时阻止地图拖拽。"""
        if self.ui_system.handle_mouse_down(pos):
            return True
        return self.ui_system.is_over_ui(pos) or self.render_system.is_minimap_pos(pos) \
            or bool(self.ui_system.menu_buttons) or not self.game_started

    def _handle_resize(self, width: int, height: int):
        width, height = max(960, width), max(640, height)
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self.ui_system.resize(width, height)
        self.camera_system.screen_width, self.camera_system.screen_height = width, height

    def _get_controlled_player(self) -> Optional[Player]:
        """获取当前 UI 视角下可操作/查看的玩家。"""
        return self.session.get_controlled_player(self.local_player_id)

    def _can_controlled_player_act(self) -> bool:
        player = self._get_controlled_player()
        return bool(player and self.session.can_player_act(player.id))

    def _execute_action_and_notify(self, action: GameAction):
        """执行行动并显示引擎返回的结构化结果。"""
        result = self.session.submit_action(action)
        self._invalidate_multiplayer_status()
        self._notify_action_result(result)
        return result

    def _center_camera_on_map(self):
        if not self.game_engine.map_tiles:
            return
        coords = self.game_engine.map_tiles.keys()
        center_q = (min(c.q for c in coords) + max(c.q for c in coords)) / 2
        center_r = (min(c.r for c in coords) + max(c.r for c in coords)) / 2
        self.camera_system.set_position(*HexRenderer.hex_to_pixel(center_q, center_r, OFFSET_X, OFFSET_Y))

    def run(self):
        """运行主循环"""
        while self.running:
            if not self.input_system.handle_events(pygame.event.get()):
                break
            self.input_system.update()
            self._poll_pending_host_room()
            self._render()
            self.clock.tick(FPS)
        pygame.quit()

    def _render(self):
        if self.game_started:
            self.screen.fill(COLORS['MAP_BACKGROUND'])
            game_state = self._get_game_state()
            self.render_system.camera_x, self.render_system.camera_y = self.camera_system.get_position()
            self.render_system.zoom = self.camera_system.get_zoom()
            view_player = self._get_controlled_player()
            visible_tiles = self.session.get_visible_tiles(view_player.id) if view_player else set()
            explored_tiles = self.session.get_explored_tiles(view_player.id) if view_player else set()
            self._update_hover_path_preview(visible_tiles)
            self.render_system.render_map(self.screen, self.game_engine.map_tiles, visible_tiles, explored_tiles,
                                          view_player)
            self.ui_system.render(self.screen, game_state)
            self.render_system.render_minimap(self.screen, self.game_engine.map_tiles, visible_tiles, explored_tiles)
        else:
            self.screen.fill(COLORS['PANEL_BG'])
            self._render_start_screen()
        self.ui_system.render_modal(self.screen)
        pygame.display.flip()

    def _get_game_state(self) -> Dict[str, Any]:
        """汇总 HUD 需要的状态。"""
        controlled_player = self._get_controlled_player()
        engine = self.game_engine
        current_income = engine.player_system.calculate_income(controlled_player, engine.map_tiles) if controlled_player else 0
        selected_coord = self.render_system.selected_tile
        selected_unit = self._find_unit_by_id(self.input_system.get_selected_unit_id()) \
            if self.input_system.is_unit_selected() else None
        multiplayer_status = self._get_multiplayer_status()
        if multiplayer_status is not None:
            multiplayer_status["can_switch"] = len(self.multiplayer_sessions) > 1
        can_act = self._can_controlled_player_act()
        if multiplayer_status and multiplayer_status.get("closed"):
            can_act = False
        return {
            'current_player': controlled_player,
            'player_color': self.render_system._get_player_color(controlled_player) if controlled_player else None,
            'current_income': current_income,
            'turn_number': engine.turn_system.turn_number,
            'turn_mode': engine.turn_system.mode,
            'turn_status': self.session.get_turn_status(),
            'can_act': can_act,
            'game_over': engine.game_over,
            'winner': engine.winner,
            'selected_coord': selected_coord,
            'selected_tile': engine.map_tiles.get(selected_coord) if selected_coord else None,
            'selected_unit': selected_unit,
            'selected_city': self.ui_system.selected_city if self.ui_system.show_city_panel else None,
            'move_mode_active': self.move_mode_active,
            'multiplayer_status': multiplayer_status,
        }

    def _handle_camera_move(self, dx: int, dy: int):
        self.camera_system.move(dx, dy)

    def _handle_zoom(self, zoom_factor: float):
        mouse_x, mouse_y = self.input_system.mouse_pos
        if self.ui_system.is_over_ui((mouse_x, mouse_y)):
            self.ui_system.scroll_log(1 if zoom_factor > 1 else -1)
            return
        self.camera_system.zoom_at(zoom_factor, mouse_x, mouse_y)

    def _handle_key_press(self, key: int, pressed: bool):
        """按键分发：弹窗 → 主菜单 → 游戏内。"""
        if not pressed:
            return
        if key == pygame.K_ESCAPE:
            if self.ui_system.has_active_modal():
                self.ui_system.close_modal()
            elif self.ui_system.show_help:
                self.ui_system.toggle_help()
            elif self.game_started and not self.game_engine.game_over and self._has_cancelable_ui_state():
                self._clear_ui_selection_state()
            else:
                self._show_exit_confirmation()
            return
        if self.ui_system.has_active_modal():
            self.ui_system.handle_key_press(key)
            return
        if key == pygame.K_F1:
            self.ui_system.toggle_help()
            return
        if not self.game_started:
            self._handle_menu_key(key)
            return
        self._handle_game_key(key)

    def _handle_menu_key(self, key: int):
        shortcuts = {
            pygame.K_SPACE: lambda: self.start_game(["玩家1", "电脑1"], turn_mode="sequential"),
            pygame.K_t: lambda: self.start_game(["玩家1", "电脑1"], turn_mode="simultaneous"),
            pygame.K_n: self._show_new_game_modal,
            pygame.K_h: self._show_http_multiplayer_modal,
            pygame.K_m: self._show_local_multiplayer_modal,
            pygame.K_l: self._handle_load_game,
        }
        if key in shortcuts:
            shortcuts[key]()

    def _handle_game_key(self, key: int):
        if key == pygame.K_TAB and (self._switch_multiplayer_client() or self._switch_hotseat_player()):
            return
        if key == pygame.K_q and self.multiplayer_room_id:
            self._show_leave_multiplayer_modal()
            return
        if key == pygame.K_f and self.multiplayer_room_id:
            self._force_skip_offline()
            return
        if key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.ui_system.scroll_log(3 if key == pygame.K_PAGEUP else -3)
            return
        if self.game_engine.game_over:
            if key == pygame.K_r:
                self._restart_game()
            return
        if self._handle_soldier_quantity_hotkey(key):
            return
        if key == pygame.K_b:
            self._handle_build_city()
        elif key == pygame.K_n:
            self._select_next_movable_unit()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self._can_controlled_player_act():
            self._handle_end_turn()
