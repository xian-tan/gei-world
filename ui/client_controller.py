"""
UI 客户端：pygame 主循环、渲染调度与按键分发。

具体职责拆分在 ui/controllers 下的各个 Mixin 中：
- FeedbackMixin：行动结果消息
- GameFlowMixin：开局、AI 回合、结束回合、菜单/退出
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


class UIClient(FeedbackMixin, GameFlowMixin, SelectionMixin, PersistenceMixin, MultiplayerMixin):
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
        self.multiplayer_poll_interval = 0.5
        self._multiplayer_status_cache = None
        self._multiplayer_status_time = 0.0
        
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
        self._invalidate_multiplayer_status()
        self._notify_action_result(result)
        return result

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

    def _handle_camera_move(self, dx: int, dy: int):
        """处理摄像机移动"""
        self.camera_system.move(dx, dy)

    def _handle_zoom(self, zoom_factor: float):
        """处理缩放"""
        mouse_x, mouse_y = self.input_system.mouse_pos
        self.camera_system.zoom_at(zoom_factor, mouse_x, mouse_y)

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
