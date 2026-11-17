"""
UI 界面系统：主菜单、HUD（顶部资源条 / 右侧上下文面板 / 左下事件日志）、城市面板、
通用弹窗（按钮 + 文本/选项输入）、横幅提示与快捷键帮助。

所有布局均由当前屏幕尺寸计算，支持窗口缩放。
"""
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import pygame

from src.config import CITY_CONFIG, UNIT_CONFIG
from src.models import City, UnitType
from ui.font_manager import get_font_manager
from ui.ui_config import (COLORS, LOG_HEIGHT, MINIMAP_HEIGHT, MINIMAP_MARGIN, PANEL_MARGIN,
                          SIDE_PANEL_WIDTH, TOP_BAR_HEIGHT)

MODE_LABELS = {"sequential": "轮流回合", "simultaneous": "同时回合"}
UNIT_LABELS = {UnitType.SETTLER: "移民", UnitType.SOLDIER: "士兵"}
HELP_LINES = [
    ("左键", "选择单位/城市，同格再次点击切换"),
    ("右键", "移动或攻击（选中单位后）"),
    ("拖拽 / WASD / 方向键", "平移地图"),
    ("滚轮", "缩放地图"),
    ("B", "选中移民后建城"),
    ("N", "选中下一个仍可移动的单位"),
    ("M / 1-9", "设置士兵移动人数"),
    ("Enter", "结束回合"),
    ("PageUp / PageDown", "翻看事件日志"),
    ("TAB", "热座/本机多人切换玩家"),
    ("Q", "离开多人房间"),
    ("F1", "显示/隐藏本帮助"),
    ("ESC", "取消选择 / 菜单"),
]


@dataclass
class Button:
    """按钮"""
    rect: pygame.Rect
    text: str
    callback: Callable
    enabled: bool = True
    color: tuple = COLORS['BUTTON']
    text_color: tuple = COLORS['TEXT']
    border_color: tuple = COLORS['PANEL_BORDER']
    disabled_message: str = ""


@dataclass
class Slider:
    """点击/拖动式滑块。"""
    rect: pygame.Rect
    min_value: int
    max_value: int
    value: int
    callback: Callable
    label: str = ""


class UISystem:
    """UI界面系统"""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.font_manager = get_font_manager()
        self.buttons: List[Button] = []
        self.menu_buttons: List[Button] = []
        self.sliders: List[Slider] = []
        self._temp_city_buttons: List[Button] = []
        self._panel_rects: List[pygame.Rect] = []
        self.show_city_panel = False
        self.selected_city = None
        self.messages: List[str] = []
        self.log_scroll = 0
        self.city_soldier_quantity = 1
        self.move_soldier_quantity = 1
        self.active_slider = None
        self.active_modal = None
        self.modal_buttons: List[Button] = []
        self.modal_inputs: List[Dict[str, Any]] = []
        self.active_input_index = 0
        self.modal_rect = None
        self.banner = None
        self.show_help = False
        self.on_build_city = None
        self.on_return_to_menu = None
        self.on_restart = None

    # ------------------------------------------------------------------ 基础
    def resize(self, width: int, height: int):
        self.screen_width = width
        self.screen_height = height

    def add_message(self, message: str):
        """添加事件日志；保留最近 80 条，新消息到来时回到最新位置。"""
        self.messages.append(message)
        self.messages = self.messages[-80:]
        self.log_scroll = 0

    def scroll_log(self, delta: int):
        self.log_scroll = max(0, min(len(self.messages) - 1, self.log_scroll + delta)) if self.messages else 0

    def show_banner(self, text: str, seconds: float = 1.6):
        self.banner = (text, time.monotonic() + seconds)

    def toggle_help(self):
        self.show_help = not self.show_help

    def set_callbacks(self, on_build_unit: Callable = None,
                      on_end_turn: Callable = None, on_save_game: Callable = None,
                      on_load_game: Callable = None, on_build_city: Callable = None,
                      on_return_to_menu: Callable = None, on_restart: Callable = None):
        """设置回调函数"""
        for name, callback in {
            "on_build_unit": on_build_unit, "on_end_turn": on_end_turn, "on_save_game": on_save_game,
            "on_load_game": on_load_game, "on_build_city": on_build_city,
            "on_return_to_menu": on_return_to_menu, "on_restart": on_restart,
        }.items():
            if callback:
                setattr(self, name, callback)

    # ------------------------------------------------------------------ 布局
    def top_bar_rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.screen_width, TOP_BAR_HEIGHT)

    def side_panel_rect(self) -> pygame.Rect:
        top = TOP_BAR_HEIGHT + PANEL_MARGIN
        bottom = self.screen_height - MINIMAP_HEIGHT - MINIMAP_MARGIN * 2
        return pygame.Rect(self.screen_width - SIDE_PANEL_WIDTH - PANEL_MARGIN, top,
                           SIDE_PANEL_WIDTH, max(120, bottom - top))

    def log_rect(self) -> pygame.Rect:
        width = min(620, self.screen_width - SIDE_PANEL_WIDTH - PANEL_MARGIN * 4)
        return pygame.Rect(PANEL_MARGIN, self.screen_height - LOG_HEIGHT - PANEL_MARGIN, max(240, width), LOG_HEIGHT)

    # ------------------------------------------------------------------ 绘制工具
    def _panel(self, surface, rect: pygame.Rect, alpha: int = 235, color=None):
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((*(color or COLORS['PANEL_BG']), alpha))
        surface.blit(panel, rect.topleft)
        pygame.draw.rect(surface, COLORS['PANEL_BORDER'], rect, 1, border_radius=6)

    def _text(self, surface, text: str, pos, size: str = 'small', color=None, center: bool = False):
        rendered = self.font_manager.render_text(text, size, color or COLORS['TEXT'])
        rect = rendered.get_rect(center=pos) if center else rendered.get_rect(topleft=pos)
        surface.blit(rendered, rect)
        return rect

    def _draw_button(self, surface: pygame.Surface, button: Button):
        hovered = button.enabled and button.rect.collidepoint(pygame.mouse.get_pos()) if pygame.display.get_init() else False
        if not button.enabled:
            color = COLORS['BUTTON_DISABLED']
        elif hovered:
            color = tuple(min(255, c + 25) for c in button.color)
        else:
            color = button.color
        pygame.draw.rect(surface, color, button.rect, border_radius=5)
        pygame.draw.rect(surface, button.border_color, button.rect, 1, border_radius=5)
        text_color = button.text_color if button.enabled else COLORS['TEXT_DIM']
        self._text(surface, button.text, button.rect.center, 'small', text_color, center=True)

    def _draw_slider(self, surface: pygame.Surface, slider: Slider):
        pygame.draw.rect(surface, COLORS['PANEL_BG_ALT'], slider.rect, border_radius=4)
        pygame.draw.rect(surface, COLORS['PANEL_BORDER'], slider.rect, 1, border_radius=4)
        ratio = 1.0 if slider.max_value <= slider.min_value else \
            (slider.value - slider.min_value) / (slider.max_value - slider.min_value)
        handle_x = slider.rect.x + int(max(0.0, min(1.0, ratio)) * slider.rect.width)
        fill = pygame.Rect(slider.rect.x, slider.rect.y, handle_x - slider.rect.x, slider.rect.height)
        pygame.draw.rect(surface, COLORS['ACCENT'], fill, border_radius=4)
        pygame.draw.circle(surface, COLORS['TEXT'], (handle_x, slider.rect.centery), slider.rect.height)

    # ------------------------------------------------------------------ 主菜单
    def render_main_menu(self, surface: pygame.Surface, actions: List[Dict[str, Any]],
                         info_lines: List[str] = None, subtitle: str = ""):
        """渲染按钮式主菜单。actions: [{text, callback, color?, enabled?}]。"""
        self.buttons, self.sliders, self._panel_rects = [], [], []
        center_x = self.screen_width // 2
        self._text(surface, "Gei World", (center_x, self.screen_height // 2 - 210), 'xlarge', COLORS['TEXT'], center=True)
        self._text(surface, subtitle or "六边形回合制策略", (center_x, self.screen_height // 2 - 165), 'medium',
                   COLORS['TEXT_DIM'], center=True)
        self.menu_buttons = []
        width, height, gap = 280, 44, 12
        top = self.screen_height // 2 - 120
        for index, action in enumerate(actions):
            button = Button(
                rect=pygame.Rect(center_x - width // 2, top + index * (height + gap), width, height),
                text=action['text'], callback=action['callback'], enabled=action.get('enabled', True),
                color=action.get('color', COLORS['BUTTON']), text_color=action.get('text_color', COLORS['TEXT']),
                disabled_message=action.get('disabled_message', '')
            )
            self._draw_button(surface, button)
            self.menu_buttons.append(button)
        y = top + len(actions) * (height + gap) + 16
        for line in info_lines or []:
            self._text(surface, line, (center_x, y), 'small', COLORS['TEXT_DIM'], center=True)
            y += 22

    def clear_menu(self):
        self.menu_buttons = []

    # ------------------------------------------------------------------ HUD
    def render(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        """渲染游戏内 HUD。"""
        self.menu_buttons = []
        self.sliders = []
        self._panel_rects = [self.top_bar_rect(), self.side_panel_rect(), self.log_rect()]
        self._render_top_bar(surface, game_state)
        if self.show_city_panel and self.selected_city:
            self._render_city_panel(surface, self.selected_city)
        else:
            self._temp_city_buttons = []
            self._render_context_panel(surface, game_state)
        self._render_message_log(surface)
        self._render_banner(surface)
        if game_state.get('game_over'):
            self._render_game_over_panel(surface, game_state)
        if self.show_help:
            self._render_help(surface)

    def _render_top_bar(self, surface, game_state: Dict[str, Any]):
        rect = self.top_bar_rect()
        self._panel(surface, rect, alpha=240)
        player = game_state.get('current_player')
        turn = game_state.get('turn_number', 1)
        mode_label = MODE_LABELS.get(game_state.get('turn_mode', 'sequential'), "轮流回合")
        x = 12
        x = self._text(surface, f"第 {turn} 回合 · {mode_label}", (x, 14), 'medium').right + 18
        if player:
            pygame.draw.circle(surface, game_state.get('player_color', COLORS['ACCENT']), (x + 8, 24), 8)
            x = self._text(surface, player.name, (x + 22, 14), 'medium').right + 8
            status = "可行动" if game_state.get('can_act', True) else "已结束 · 等待其他玩家"
            x = self._text(surface, status, (x, 17), 'small',
                           COLORS['SUCCESS'] if game_state.get('can_act', True) else COLORS['WARNING']).right + 22
            soldiers = sum(u.quantity for u in player.units if u.unit_type == UnitType.SOLDIER)
            settlers = sum(1 for u in player.units if u.unit_type == UnitType.SETTLER)
            stats = [
                f"金币 {player.gold} (+{game_state.get('current_income', 0)})",
                f"城市 {len(player.cities)}",
                f"士兵 {soldiers}",
                f"移民 {settlers}",
            ]
            for stat in stats:
                x = self._text(surface, stat, (x, 17), 'small', COLORS['TEXT']).right + 16

        can_act = game_state.get('can_act', True)
        specs = [
            ("菜单", self._return_to_menu, True, COLORS['BUTTON'], ""),
            ("读取", self._load_game, True, COLORS['BUTTON'], ""),
            ("保存", self._save_game, True, COLORS['BUTTON'], ""),
            ("结束回合" if can_act else "已结束", self._end_turn, can_act, COLORS['SUCCESS'],
             "本回合已结束，等待其他玩家。"),
        ]
        buttons = []
        right = self.screen_width - 10
        for text, callback, enabled, color, disabled in specs:
            width = 104 if text in ("结束回合", "已结束") else 64
            button = Button(pygame.Rect(right - width, 8, width, 32), text, callback, enabled, color,
                            disabled_message=disabled)
            right -= width + 8
            self._draw_button(surface, button)
            buttons.append(button)
        self.buttons = buttons

    def _render_context_panel(self, surface, game_state: Dict[str, Any]):
        rect = self.side_panel_rect()
        self._panel(surface, rect)
        x, y = rect.x + 14, rect.y + 12
        selected_unit = game_state.get('selected_unit')
        selected_tile = game_state.get('selected_tile')
        selected_coord = game_state.get('selected_coord')
        current_player = game_state.get('current_player')

        if selected_unit:
            label = UNIT_LABELS.get(selected_unit.unit_type, selected_unit.unit_type.value)
            title = f"{label} x{selected_unit.quantity}" if selected_unit.unit_type == UnitType.SOLDIER else label
            y = self._text(surface, title, (x, y), 'large').bottom + 6
            for line in [
                f"所属：{selected_unit.owner.name}",
                f"移动力：{selected_unit.movement_points}/{selected_unit.max_movement_points}",
                f"视野：{selected_unit.vision_range}",
            ]:
                y = self._text(surface, line, (x, y), 'small', COLORS['TEXT_DIM']).bottom + 4
            if selected_tile:
                terrain = "海洋" if selected_tile.terrain_type.value == "ocean" else "陆地"
                y = self._text(surface, f"地形：{terrain}", (x, y), 'small', COLORS['TEXT_DIM']).bottom + 4
            y += 6
            y = self._render_move_quantity_slider(surface, game_state, x, y)
            if selected_unit.unit_type == UnitType.SETTLER and selected_unit.owner == current_player:
                button = Button(pygame.Rect(x, y + 4, rect.width - 28, 34), "建城 (B)", self._build_city,
                                game_state.get('can_act', True), COLORS['ACCENT'],
                                disabled_message="本回合已结束，无法继续建城。")
                self._draw_button(surface, button)
                self.buttons.append(button)
                y += 46
            hint = "右键黄色范围移动；进入敌方格发起战斗/攻城。" if selected_unit.unit_type == UnitType.SOLDIER \
                else "右键移动；在合适陆地上建城。"
            for line in self.font_manager.wrap_text(hint, rect.width - 28):
                y = self._text(surface, line, (x, y), 'small', COLORS['TEXT_DIM']).bottom + 2
        elif selected_coord and selected_tile:
            terrain = "海洋" if selected_tile.terrain_type.value == "ocean" else "陆地"
            y = self._text(surface, f"地块 ({selected_coord.q}, {selected_coord.r})", (x, y), 'large').bottom + 6
            owner = selected_tile.owner.name if selected_tile.owner else "无"
            for line in [f"地形：{terrain}", f"归属：{owner}"]:
                y = self._text(surface, line, (x, y), 'small', COLORS['TEXT_DIM']).bottom + 4
            if selected_tile.city:
                city = selected_tile.city
                y = self._text(surface, f"城市：{city.owner.name} · 防御 {city.defense}", (x, y), 'small').bottom + 4
        else:
            y = self._text(surface, "未选择", (x, y), 'large', COLORS['TEXT_DIM']).bottom + 8
            for line in ["左键选择单位或城市", "按 N 选择下一个可移动单位", "按 F1 查看全部快捷键"]:
                y = self._text(surface, line, (x, y), 'small', COLORS['TEXT_DIM']).bottom + 4

        self._render_multiplayer_info(surface, game_state, rect.x, y + 14)

    def _render_multiplayer_info(self, surface, game_state: Dict[str, Any], panel_x: int, y_offset: int) -> int:
        """多人房间卡片：房间码、客户端、席位状态、最近事件。"""
        status = game_state.get('multiplayer_status')
        if not status:
            return y_offset
        rect = self.side_panel_rect()
        card = pygame.Rect(rect.x + 8, y_offset, rect.width - 16, rect.bottom - y_offset - 8)
        if card.height < 60:
            return y_offset
        pygame.draw.rect(surface, COLORS['PANEL_BG_ALT'], card, border_radius=5)
        x, y = card.x + 8, card.y + 6
        y = self._text(surface, f"房间 {status.get('room_id')}", (x, y), 'medium').bottom + 2
        y = self._text(surface, f"本机身份：{status.get('active_client_id')}", (x, y), 'small', COLORS['TEXT_DIM']).bottom + 4
        if status.get('closed'):
            for line in self.font_manager.wrap_text(f"已关闭：{status.get('close_reason') or '房间已关闭'}", card.width - 16):
                y = self._text(surface, line, (x, y), 'small', COLORS['DANGER']).bottom + 2
        elif status.get('offline_seats'):
            names = "、".join(seat.get('player_name', '对手') for seat in status.get('offline_seats', []))
            for line in self.font_manager.wrap_text(f"离线：{names}", card.width - 16):
                y = self._text(surface, line, (x, y), 'small', COLORS['WARNING']).bottom + 2
        active_player_id = status.get('active_player_id')
        for seat in status.get('seats', []):
            marker = "▶ " if seat.get('player_id') == active_player_id else "  "
            role = "房主" if seat.get('is_host') else "玩家"
            if not seat.get('connected'):
                state, color = "离线", COLORS['WARNING']
            elif seat.get('ended_turn'):
                state, color = "已结束", COLORS['TEXT_DIM']
            else:
                state, color = "行动中", COLORS['SUCCESS']
            y = self._text(surface, f"{marker}{seat.get('player_name')}（{role}）：{state}", (x, y), 'small', color).bottom + 2
        for event in status.get('recent_events', [])[-3:]:
            message = event.get('message') or event.get('event_type')
            if not message or y > card.bottom - 18:
                break
            for line in self.font_manager.wrap_text(f"· {message}", card.width - 16)[:2]:
                y = self._text(surface, line, (x, y), 'small', COLORS['TEXT_DIM']).bottom + 1
        hint = "TAB 切换视角 · Q 离开" if status.get('can_switch') else "Q 离开房间"
        if y < card.bottom - 18:
            self._text(surface, hint, (x, card.bottom - 18), 'small', COLORS['TEXT_DIM'])
        return card.bottom

    def _render_move_quantity_slider(self, surface, game_state: Dict[str, Any], panel_x: int, y_offset: int) -> int:
        """选中士兵时渲染批量移动数量滑块。"""
        current_player = game_state.get('current_player')
        selected_unit = game_state.get('selected_unit')
        if not current_player or not selected_unit or not game_state.get('selected_tile'):
            return y_offset
        if selected_unit.unit_type != UnitType.SOLDIER or selected_unit.owner != current_player:
            return y_offset
        if selected_unit.movement_points <= 0:
            return y_offset
        max_count = selected_unit.quantity
        if max_count <= 1:
            self.move_soldier_quantity = 1
            return y_offset
        self.move_soldier_quantity = max(1, min(self.move_soldier_quantity, max_count))
        y_offset = self._text(surface, f"移动人数：{self.move_soldier_quantity}/{max_count}（M 全部 / 1-9）",
                              (panel_x, y_offset), 'small').bottom + 8
        slider = Slider(pygame.Rect(panel_x, y_offset, SIDE_PANEL_WIDTH - 40, 8), 1, max_count,
                        self.move_soldier_quantity, self._set_move_soldier_quantity, "move_soldier_quantity")
        self._draw_slider(surface, slider)
        self.sliders.append(slider)
        return y_offset + 22

    def _render_city_panel(self, surface: pygame.Surface, city: City):
        """城市面板（停靠在右侧）：防御、生产状态、生产按钮。"""
        rect = self.side_panel_rect()
        self._panel(surface, rect)
        x, y = rect.x + 14, rect.y + 12
        y = self._text(surface, f"城市 · {city.owner.name}", (x, y), 'large').bottom + 6
        can_produce = city.productions_this_turn < CITY_CONFIG["productions_per_turn"]
        y = self._text(surface, f"防御 {city.defense}/{CITY_CONFIG['max_defense']}（每回合 +{CITY_CONFIG['defense_growth']}）",
                       (x, y), 'small', COLORS['TEXT_DIM']).bottom + 4
        y = self._text(surface, "本回合可生产" if can_produce else "本回合已生产",
                       (x, y), 'small', COLORS['SUCCESS'] if can_produce else COLORS['WARNING']).bottom + 4
        y = self._text(surface, f"金币 {city.owner.gold}", (x, y), 'small', COLORS['TEXT_DIM']).bottom + 12
        produced_message = "该城市本回合已生产过，下回合再来。"
        width = rect.width - 28

        settler_cost = UNIT_CONFIG["settler_cost"]
        settler_button = Button(
            pygame.Rect(x, y, width, 34), f"生产移民（{settler_cost} 金币）",
            lambda: self._build_unit(city, UnitType.SETTLER),
            can_produce and city.owner.gold >= settler_cost, COLORS['ACCENT'],
            disabled_message=produced_message if not can_produce else
            f"金币不足：生产移民需要 {settler_cost} 金币，当前 {city.owner.gold}"
        )
        self._draw_button(surface, settler_button)
        y += 48

        soldier_cost = UNIT_CONFIG["soldier_cost"]
        max_soldiers = city.owner.gold // soldier_cost if soldier_cost > 0 else 0
        soldier_quantity = 0 if max_soldiers <= 0 else max(1, min(self.city_soldier_quantity, max_soldiers))
        self.city_soldier_quantity = max(1, soldier_quantity) if max_soldiers > 0 else 1
        y = self._text(surface, f"士兵数量：{soldier_quantity}/{max_soldiers}", (x, y), 'small').bottom + 8
        slider = Slider(pygame.Rect(x, y, width, 8), 1, max(1, max_soldiers), max(1, soldier_quantity),
                        self._set_city_soldier_quantity, "city_soldier_quantity")
        self._draw_slider(surface, slider)
        if max_soldiers > 0:
            self.sliders.append(slider)
        y += 20
        soldier_button = Button(
            pygame.Rect(x, y, width, 34), f"生产士兵 x{soldier_quantity}（{soldier_quantity * soldier_cost} 金币）",
            lambda: self._build_unit(city, UnitType.SOLDIER, soldier_quantity),
            can_produce and max_soldiers > 0, COLORS['SUCCESS'],
            disabled_message=produced_message if not can_produce else
            f"金币不足：生产士兵需要 {soldier_cost} 金币，当前 {city.owner.gold}"
        )
        self._draw_button(surface, soldier_button)
        y += 48
        for line in self.font_manager.wrap_text("青色轮廓为城市经济范围：范围内己方陆地每回合提供收入。", width):
            y = self._text(surface, line, (x, y), 'small', COLORS['TEXT_DIM']).bottom + 2
        close_button = Button(pygame.Rect(rect.right - 84, rect.bottom - 44, 70, 32), "关闭",
                              self._close_city_panel, color=COLORS['BUTTON'])
        self._draw_button(surface, close_button)
        self._temp_city_buttons = [settler_button, soldier_button, close_button]

    def _render_message_log(self, surface: pygame.Surface):
        """左下事件日志：自动折行，可用 PageUp/PageDown 翻页。"""
        rect = self.log_rect()
        self._panel(surface, rect, alpha=215)
        title = "事件日志" + (f"（向上 {self.log_scroll} 条）" if self.log_scroll else "")
        self._text(surface, title, (rect.x + 10, rect.y + 6), 'small', COLORS['TEXT_DIM'])
        max_lines = (rect.height - 30) // 17
        end = len(self.messages) - self.log_scroll
        wrapped: List[tuple] = []
        for index, message in enumerate(self.messages[:max(0, end)]):
            color = COLORS['TEXT'] if index == end - 1 else COLORS['TEXT_DIM']
            for line in self.font_manager.wrap_text(message, rect.width - 20):
                wrapped.append((line, color))
        y = rect.y + 26
        for line, color in wrapped[-max_lines:]:
            self._text(surface, line, (rect.x + 10, y), 'small', color)
            y += 17

    def _render_banner(self, surface):
        if not self.banner:
            return
        text, expires = self.banner
        if time.monotonic() > expires:
            self.banner = None
            return
        rendered = self.font_manager.render_text(text, 'large', COLORS['TEXT'])
        rect = rendered.get_rect(center=(self.screen_width // 2, TOP_BAR_HEIGHT + 60))
        backdrop = rect.inflate(60, 24)
        self._panel(surface, backdrop, alpha=225, color=COLORS['PANEL_BG_ALT'])
        surface.blit(rendered, rect)

    def _render_game_over_panel(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        rect = pygame.Rect(0, 0, 400, 200)
        rect.center = (self.screen_width // 2, self.screen_height // 2 - 40)
        self._panel(surface, rect, alpha=245)
        self._text(surface, "游戏结束", (rect.centerx, rect.y + 36), 'large', center=True)
        winner = game_state.get('winner')
        self._text(surface, f"获胜者：{winner.name if winner else '平局'}", (rect.centerx, rect.y + 80), 'medium',
                   COLORS['WARNING'], center=True)
        restart = Button(pygame.Rect(rect.x + 40, rect.bottom - 64, 150, 38), "再来一局 (R)", self._restart,
                         color=COLORS['SUCCESS'])
        menu = Button(pygame.Rect(rect.right - 190, rect.bottom - 64, 150, 38), "返回主菜单", self._return_to_menu)
        for button in (restart, menu):
            self._draw_button(surface, button)
            self.buttons.append(button)

    def _render_help(self, surface):
        rect = pygame.Rect(0, 0, 520, 60 + len(HELP_LINES) * 26)
        rect.center = (self.screen_width // 2, self.screen_height // 2)
        self._panel(surface, rect, alpha=245)
        self._text(surface, "快捷键", (rect.centerx, rect.y + 24), 'large', center=True)
        y = rect.y + 52
        for key, desc in HELP_LINES:
            self._text(surface, key, (rect.x + 30, y), 'small', COLORS['ACCENT'])
            self._text(surface, desc, (rect.x + 210, y), 'small')
            y += 26

    # ------------------------------------------------------------------ 弹窗
    def show_modal(self, title: str, lines: List[str] = None, actions: List[Dict[str, Any]] = None,
                   inputs: List[Dict[str, Any]] = None):
        """显示通用弹窗。actions: [{text, callback, color?, text_color?, enabled?}]；
        inputs: [{key, label, value, options?}]，带 options 的为选项输入（点击或左右键切换）。"""
        self.active_modal = {'title': title, 'lines': lines or [], 'actions': actions or [], 'inputs': inputs or []}
        self.modal_buttons = []
        self.modal_inputs = []
        self.active_input_index = next(
            (index for index, item in enumerate(self.active_modal['inputs']) if not item.get('options')), 0)
        self.active_slider = None

    def close_modal(self):
        self.active_modal = None
        self.modal_buttons = []
        self.modal_inputs = []
        self.active_input_index = 0
        self.modal_rect = None

    def has_active_modal(self) -> bool:
        return self.active_modal is not None

    def render_modal(self, surface: pygame.Surface):
        """渲染顶层通用弹窗。"""
        if not self.active_modal:
            return
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surface.blit(overlay, (0, 0))

        lines = self.active_modal.get('lines', [])
        actions = self.active_modal.get('actions', [])
        inputs = self.active_modal.get('inputs', [])
        panel_width = 560 if inputs else 480
        columns = 2 if len(actions) > 4 else 1
        wrapped_lines = [w for line in lines for w in self.font_manager.wrap_text(line, panel_width - 48)]
        action_rows = (len(actions) + columns - 1) // columns
        panel_height = 90 + len(wrapped_lines) * 22 + len(inputs) * 40 + max(1, action_rows) * 44
        panel_height = min(panel_height, self.screen_height - 40)
        self.modal_rect = pygame.Rect(0, 0, panel_width, panel_height)
        self.modal_rect.center = (self.screen_width // 2, self.screen_height // 2)
        self._panel(surface, self.modal_rect, alpha=250)
        x, y = self.modal_rect.x + 24, self.modal_rect.y + 18
        self._text(surface, self.active_modal.get('title', ''), (self.modal_rect.centerx, y + 12), 'large', center=True)
        y += 44
        for line in wrapped_lines:
            self._text(surface, line, (x, y), 'small', COLORS['TEXT_DIM'])
            y += 22

        self.modal_inputs = []
        for index, item in enumerate(inputs):
            self._text(surface, item.get('label', item.get('key', '')), (x, y + 6), 'small')
            box = pygame.Rect(self.modal_rect.x + 170, y, panel_width - 194, 30)
            active = index == self.active_input_index
            pygame.draw.rect(surface, COLORS['PANEL_BG_ALT'], box, border_radius=4)
            pygame.draw.rect(surface, COLORS['ACCENT'] if active else COLORS['PANEL_BORDER'], box, 2 if active else 1,
                             border_radius=4)
            if item.get('options'):
                label = self._option_label(item)
                self._text(surface, f"◀  {label}  ▶", box.center, 'small', center=True)
            else:
                value = str(item.get('value', ''))
                shown = value
                while shown and self.font_manager.get_text_size(shown, 'small')[0] > box.width - 16:
                    shown = shown[1:]
                caret = "|" if active and int(time.monotonic() * 2) % 2 == 0 else ""
                self._text(surface, shown + caret, (box.x + 8, box.y + 7), 'small')
            self.modal_inputs.append({'rect': box, 'index': index})
            y += 40

        self.modal_buttons = []
        y += 6
        button_width = (panel_width - 48 - (columns - 1) * 12) // columns
        for index, action in enumerate(actions):
            row, col = divmod(index, columns)
            button = Button(
                rect=pygame.Rect(x + col * (button_width + 12), y + row * 44, button_width, 36),
                text=action.get('text', ''), callback=action.get('callback'),
                enabled=action.get('enabled', True), color=action.get('color', COLORS['BUTTON']),
                text_color=action.get('text_color', COLORS['TEXT']),
                disabled_message=action.get('disabled_message', '')
            )
            self._draw_button(surface, button)
            self.modal_buttons.append(button)

    @staticmethod
    def _option_label(item: Dict[str, Any]) -> str:
        for value, label in item.get('options', []):
            if value == item.get('value'):
                return label
        return str(item.get('value', ''))

    def _cycle_option(self, item: Dict[str, Any], step: int = 1):
        options = item.get('options') or []
        if not options:
            return
        values = [value for value, _label in options]
        index = values.index(item.get('value')) if item.get('value') in values else -1
        item['value'] = values[(index + step) % len(values)]

    def handle_text_input(self, text: str) -> bool:
        inputs = self.active_modal.get('inputs', []) if self.active_modal else []
        if not inputs:
            return False
        current = inputs[self.active_input_index]
        if current.get('options'):
            return False
        current['value'] = str(current.get('value', '')) + text
        return True

    def handle_key_press(self, key: int) -> bool:
        """处理弹窗快捷键：退格、TAB 切换输入框、左右键切换选项、回车触发首个按钮。"""
        if not self.active_modal:
            return False
        inputs = self.active_modal.get('inputs', [])
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            first = next((a for a in self.active_modal.get('actions', []) if a.get('enabled', True)), None)
            if first and first.get('callback'):
                first['callback']()
                return True
            return False
        if not inputs:
            return False
        current = inputs[self.active_input_index]
        if key == pygame.K_TAB:
            self.active_input_index = (self.active_input_index + 1) % len(inputs)
            return True
        if current.get('options') and key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._cycle_option(current, -1 if key == pygame.K_LEFT else 1)
            return True
        if key == pygame.K_BACKSPACE and not current.get('options'):
            current['value'] = str(current.get('value', ''))[:-1]
            return True
        return False

    def get_modal_input_values(self) -> Dict[str, str]:
        inputs = self.active_modal.get('inputs', []) if self.active_modal else []
        return {item.get('key', str(index)): (item.get('value') if item.get('options') else str(item.get('value', '')))
                for index, item in enumerate(inputs)}

    def set_modal_input_value(self, key: str, value):
        inputs = self.active_modal.get('inputs', []) if self.active_modal else []
        for item in inputs:
            if item.get('key') == key:
                item['value'] = value
                return True
        return False

    def set_modal_lines(self, lines: List[str]):
        if self.active_modal:
            self.active_modal['lines'] = lines

    # ------------------------------------------------------------------ 点击
    def _press(self, button: Button) -> bool:
        if button.enabled and button.callback:
            button.callback()
        elif not button.enabled and button.disabled_message:
            self.add_message(button.disabled_message)
        return True

    def handle_click(self, pos: tuple) -> bool:
        """处理UI点击；返回 True 表示点击被 UI 消费（不再传给地图）。"""
        if self.active_modal:
            for item in self.modal_inputs:
                if item['rect'].collidepoint(pos):
                    self.active_input_index = item['index']
                    current = self.active_modal['inputs'][item['index']]
                    if current.get('options'):
                        self._cycle_option(current, -1 if pos[0] < item['rect'].centerx - item['rect'].width // 4 else 1)
                    return True
            for button in self.modal_buttons:
                if button.rect.collidepoint(pos):
                    return self._press(button)
            return True
        if self.show_help:
            self.show_help = False
            return True
        for button in self.menu_buttons:
            if button.rect.collidepoint(pos):
                return self._press(button)
        if self.handle_mouse_down(pos):
            self.handle_mouse_up(pos)
            return True
        for button in list(self.buttons) + list(self._temp_city_buttons):
            if button.rect.collidepoint(pos):
                return self._press(button)
        return any(rect.collidepoint(pos) for rect in self._panel_rects)

    # ------------------------------------------------------------------ 滑块
    def _set_city_soldier_quantity(self, value: int):
        self.city_soldier_quantity = value

    def _set_move_soldier_quantity(self, value: int):
        self.move_soldier_quantity = value

    def _slider_value_from_pos(self, slider: Slider, pos: tuple) -> int:
        if slider.max_value <= slider.min_value:
            return slider.min_value
        ratio = max(0.0, min(1.0, (pos[0] - slider.rect.x) / max(1, slider.rect.width)))
        return int(round(slider.min_value + ratio * (slider.max_value - slider.min_value)))

    def _update_slider_from_pos(self, slider: Slider, pos: tuple):
        value = self._slider_value_from_pos(slider, pos)
        slider.value = value
        slider.callback(value)

    def handle_mouse_down(self, pos: tuple) -> bool:
        for slider in reversed(self.sliders):
            if slider.rect.inflate(8, 16).collidepoint(pos):
                self.active_slider = slider
                self._update_slider_from_pos(slider, pos)
                return True
        return False

    def handle_mouse_drag(self, pos: tuple) -> bool:
        if not self.active_slider:
            return False
        self._update_slider_from_pos(self.active_slider, pos)
        return True

    def handle_mouse_up(self, pos: tuple) -> bool:
        if not self.active_slider:
            return False
        self._update_slider_from_pos(self.active_slider, pos)
        self.active_slider = None
        return True

    def is_over_ui(self, pos: tuple) -> bool:
        """坐标是否落在 HUD 面板或弹窗上（用于阻止地图拖拽/点击穿透）。"""
        if self.active_modal:
            return True
        return any(rect.collidepoint(pos) for rect in self._panel_rects)

    # ------------------------------------------------------------------ 城市面板与回调
    def show_city_panel_for(self, city: City):
        self.show_city_panel = True
        self.selected_city = city

    def _close_city_panel(self):
        self.show_city_panel = False
        self.selected_city = None
        self._temp_city_buttons = []

    def _build_unit(self, city: City, unit_type: UnitType, quantity: int = 1):
        if getattr(self, 'on_build_unit', None):
            self.on_build_unit(city.id, unit_type, quantity)

    def _build_city(self):
        if self.on_build_city:
            self.on_build_city()

    def _end_turn(self):
        if getattr(self, 'on_end_turn', None):
            self.on_end_turn()

    def _save_game(self):
        if getattr(self, 'on_save_game', None):
            self.on_save_game()

    def _load_game(self):
        if getattr(self, 'on_load_game', None):
            self.on_load_game()

    def _return_to_menu(self):
        if self.on_return_to_menu:
            self.on_return_to_menu()

    def _restart(self):
        if self.on_restart:
            self.on_restart()
