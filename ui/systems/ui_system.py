"""
UI界面系统 - 面板、按钮等
"""
import pygame
import sys
import os
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.config import UNIT_CONFIG
from src.models import Player, City, Unit, UnitType
from ui.ui_config import COLORS, FONT_SIZE_SMALL, FONT_SIZE_MEDIUM, FONT_SIZE_LARGE
from ui.font_manager import get_font_manager


@dataclass
class Button:
    """按钮类"""
    rect: pygame.Rect
    text: str
    callback: Callable
    enabled: bool = True
    color: tuple = COLORS['LIGHT_GRAY']
    text_color: tuple = COLORS['BLACK']
    border_color: tuple = COLORS['BLACK']
    disabled_message: str = ""


@dataclass
class Slider:
    """简单点击式滑块。"""
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
        self.buttons = []
        self.sliders = []
        self.panels = {}
        self.font_manager = get_font_manager()
        self.show_city_panel = False
        self.selected_city = None
        self.messages: List[str] = []
        self.city_soldier_quantity = 1
        self.move_soldier_quantity = 1
        self.active_slider = None
        self.on_build_city = None
        
    def add_message(self, message: str):
        """添加界面消息。"""
        self.messages.append(message)
        self.messages = self.messages[-5:]
        
    def render(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        """渲染UI界面"""
        self.sliders = []
        # 渲染右侧信息面板
        self._render_info_panel(surface, game_state)
        
        # 渲染按钮
        self._render_buttons(surface)
        
        # 渲染城市面板
        if self.show_city_panel and self.selected_city:
            self._render_city_panel(surface, self.selected_city)
        
        # 渲染回合信息
        self._render_turn_info(surface, game_state)
        self._render_message_log(surface)
        
        if game_state.get('game_over'):
            self._render_game_over_panel(surface, game_state)
    
    def _render_info_panel(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        """渲染信息面板"""
        panel_x = self.screen_width - 250
        panel_y = 10
        panel_width = 240
        panel_height = 430  # 增加高度以显示更多信息和选择详情
        
        # 背景
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(surface, COLORS['LIGHT_GRAY'], panel_rect)
        pygame.draw.rect(surface, COLORS['BLACK'], panel_rect, 2)
        
        # 当前玩家信息
        current_player = game_state.get('current_player')
        if current_player:
            y_offset = panel_y + 10
            
            # 玩家名称
            text = self.font_manager.render_text(f"当前玩家: {current_player.name}", 
                                                'medium', COLORS['BLACK'])
            surface.blit(text, (panel_x + 10, y_offset))
            y_offset += 25
            
            # 金币
            text = self.font_manager.render_text(f"金币: {current_player.gold}", 
                                                'small', COLORS['BLACK'])
            surface.blit(text, (panel_x + 10, y_offset))
            y_offset += 20
            
            # 城市数量
            city_count = len(current_player.cities)
            text = self.font_manager.render_text(f"城市: {city_count}", 
                                                'small', COLORS['BLACK'])
            surface.blit(text, (panel_x + 10, y_offset))
            y_offset += 20
            
            # 单位统计
            unit_counts = {}
            for unit in current_player.units:
                unit_type = unit.unit_type.value
                unit_counts[unit_type] = unit_counts.get(unit_type, 0) + 1
            
            for unit_type, count in unit_counts.items():
                text = self.font_manager.render_text(f"单位 {unit_type}: {count}", 
                                                    'small', COLORS['BLACK'])
                surface.blit(text, (panel_x + 10, y_offset))
                y_offset += 20
            
            y_offset = self._render_selection_info(surface, game_state, panel_x, y_offset + 8)
            y_offset = self._render_move_quantity_slider(surface, game_state, panel_x, y_offset + 8)
            
            # 添加控制提示
            y_offset += 10
            help_texts = [
                "=== 控制说明 ===",
                "左键: 选择/移动/切换",
                "黄框: 可移动范围",
                "B/建城按钮: 移民建城",
                "右键: 取消选择",
                "城市: 生产单位"
            ]
            
            for help_text in help_texts:
                text = self.font_manager.render_text(help_text, 'small', COLORS['DARK_GRAY'])
                surface.blit(text, (panel_x + 10, y_offset))
                y_offset += 16
    
    def _render_selection_info(self, surface: pygame.Surface, game_state: Dict[str, Any],
                               panel_x: int, y_offset: int) -> int:
        """渲染当前选中对象详情。"""
        selected_coord = game_state.get('selected_coord')
        selected_tile = game_state.get('selected_tile')
        selected_unit = game_state.get('selected_unit')
        selected_city = game_state.get('selected_city')
        
        if not selected_coord and not selected_unit and not selected_city:
            return y_offset
        
        lines = ["=== 选择详情 ==="]
        if selected_coord:
            lines.append(f"坐标: ({selected_coord.q}, {selected_coord.r})")
        if selected_tile:
            lines.append(f"地形: {selected_tile.terrain_type.value}")
            owner_name = selected_tile.owner.name if selected_tile.owner else "无"
            lines.append(f"归属: {owner_name}")
        if selected_unit:
            if selected_tile:
                lines.append(f"所在地形: {selected_tile.terrain_type.value}")
            lines.append(f"单位: {selected_unit.unit_type.value}")
            lines.append(f"移动力: {selected_unit.movement_points}/{selected_unit.max_movement_points}")
            lines.append(f"视野: {selected_unit.vision_range}")
        if selected_city:
            lines.append(f"城市: {selected_city.owner.name}")
            lines.append(f"中心: ({selected_city.center_tile.q}, {selected_city.center_tile.r})")
            lines.append(f"领土: {len(selected_city.territory_tiles)}")
            lines.append("生产: 移民/士兵")
        
        for line in lines[:9]:
            text = self.font_manager.render_text(line, 'small', COLORS['BLACK'])
            surface.blit(text, (panel_x + 10, y_offset))
            y_offset += 16
        return y_offset
    
    def _render_move_quantity_slider(self, surface: pygame.Surface, game_state: Dict[str, Any],
                                      panel_x: int, y_offset: int) -> int:
        """选中士兵时渲染批量移动数量滑块。"""
        current_player = game_state.get('current_player')
        selected_unit = game_state.get('selected_unit')
        selected_tile = game_state.get('selected_tile')
        if not current_player or not selected_unit or not selected_tile:
            return y_offset
        if selected_unit.unit_type != UnitType.SOLDIER:
            return y_offset
        movable_soldiers = [
            unit for unit in selected_tile.units
            if unit.owner == current_player
            and unit.unit_type == UnitType.SOLDIER
            and unit.movement_points > 0
        ]
        max_count = len(movable_soldiers)
        if max_count <= 1:
            self.move_soldier_quantity = 1
            return y_offset
        self.move_soldier_quantity = max(1, min(self.move_soldier_quantity, max_count))
        label = self.font_manager.render_text(
            f"移动士兵数量: {self.move_soldier_quantity}/{max_count}", 'small', COLORS['BLACK']
        )
        surface.blit(label, (panel_x + 10, y_offset))
        y_offset += 18
        slider = Slider(
            rect=pygame.Rect(panel_x + 10, y_offset, 210, 12),
            min_value=1,
            max_value=max_count,
            value=self.move_soldier_quantity,
            callback=self._set_move_soldier_quantity,
            label="move_soldier_quantity"
        )
        self._draw_slider(surface, slider)
        self.sliders.append(slider)
        return y_offset + 20
    
    def _render_buttons(self, surface: pygame.Surface):
        """渲染按钮"""
        for button in self.buttons:
            # 按钮背景
            color = button.color if button.enabled else COLORS['GRAY']
            pygame.draw.rect(surface, color, button.rect)
            pygame.draw.rect(surface, button.border_color, button.rect, 2)
            
            # 按钮文本
            text_color = button.text_color if button.enabled else COLORS['DARK_GRAY']
            text = self.font_manager.render_text(button.text, 'small', text_color)
            text_rect = text.get_rect(center=button.rect.center)
            surface.blit(text, text_rect)
    
    def _render_city_panel(self, surface: pygame.Surface, city: City):
        """渲染城市面板"""
        panel_width = 320
        panel_height = 300
        panel_x = (self.screen_width - panel_width) // 2
        panel_y = (self.screen_height - panel_height) // 2
        
        # 面板背景
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(surface, COLORS['WHITE'], panel_rect)
        pygame.draw.rect(surface, COLORS['BLACK'], panel_rect, 3)
        
        y_offset = panel_y + 20
        
        # 城市标题
        title = self.font_manager.render_text(f"城市 - {city.owner.name}", 'large', COLORS['BLACK'])
        title_rect = title.get_rect(centerx=panel_x + panel_width//2, y=y_offset)
        surface.blit(title, title_rect)
        y_offset += 40
        
        # 生产选项
        text = self.font_manager.render_text("生产单位:", 'medium', COLORS['BLACK'])
        surface.blit(text, (panel_x + 20, y_offset))
        y_offset += 30
        
        # 移民按钮
        settler_cost = UNIT_CONFIG["settler_cost"]
        settler_text = f"移民 ({settler_cost}金币)"
        settler_enabled = city.owner.gold >= settler_cost
        settler_button = Button(
            rect=pygame.Rect(panel_x + 20, y_offset, 120, 30),
            text=settler_text,
            callback=lambda: self._build_unit(city, UnitType.SETTLER),
            enabled=settler_enabled,
            disabled_message=f"金币不足：生产移民需要 {settler_cost} 金币，当前 {city.owner.gold}"
        )
        self._draw_button(surface, settler_button)
        
        y_offset += 45
        
        # 士兵数量滑块和按钮
        soldier_cost = UNIT_CONFIG["soldier_cost"]
        max_soldiers = city.owner.gold // soldier_cost if soldier_cost > 0 else 0
        soldier_quantity = 0 if max_soldiers <= 0 else max(1, min(self.city_soldier_quantity, max_soldiers))
        self.city_soldier_quantity = max(1, soldier_quantity) if max_soldiers > 0 else 1
        quantity_label = self.font_manager.render_text(
            f"士兵数量: {soldier_quantity}/{max_soldiers}", 'small', COLORS['BLACK']
        )
        surface.blit(quantity_label, (panel_x + 20, y_offset))
        y_offset += 20
        soldier_slider = Slider(
            rect=pygame.Rect(panel_x + 20, y_offset, 250, 12),
            min_value=1,
            max_value=max(1, max_soldiers),
            value=max(1, soldier_quantity),
            callback=self._set_city_soldier_quantity,
            label="city_soldier_quantity"
        )
        self._draw_slider(surface, soldier_slider)
        if max_soldiers > 0:
            self.sliders.append(soldier_slider)
        y_offset += 24
        
        soldier_text = f"生产士兵 x{soldier_quantity} ({soldier_quantity * soldier_cost}金币)"
        soldier_enabled = max_soldiers > 0
        soldier_button = Button(
            rect=pygame.Rect(panel_x + 20, y_offset, 250, 30),
            text=soldier_text,
            callback=lambda: self._build_unit(city, UnitType.SOLDIER, soldier_quantity),
            enabled=soldier_enabled,
            disabled_message=f"金币不足：生产士兵需要 {soldier_cost} 金币，当前 {city.owner.gold}"
        )
        self._draw_button(surface, soldier_button)
        y_offset += 50
        
        # 关闭按钮
        close_button = Button(
            rect=pygame.Rect(panel_x + panel_width - 80, panel_y + panel_height - 40, 60, 30),
            text="关闭",
            callback=self._close_city_panel,
            color=COLORS['RED'],
            text_color=COLORS['WHITE']
        )
        self._draw_button(surface, close_button)
        
        # 更新按钮列表(临时存储用于点击检测)
        self._temp_city_buttons = [settler_button, soldier_button, close_button]
    
    def _draw_button(self, surface: pygame.Surface, button: Button):
        """绘制单个按钮"""
        color = button.color if button.enabled else COLORS['GRAY']
        pygame.draw.rect(surface, color, button.rect)
        pygame.draw.rect(surface, button.border_color, button.rect, 2)
        
        text_color = button.text_color if button.enabled else COLORS['DARK_GRAY']
        text = self.font_manager.render_text(button.text, 'small', text_color)
        text_rect = text.get_rect(center=button.rect.center)
        surface.blit(text, text_rect)
    
    def _draw_slider(self, surface: pygame.Surface, slider: Slider):
        """绘制点击式滑块。"""
        pygame.draw.rect(surface, COLORS['DARK_GRAY'], slider.rect)
        pygame.draw.rect(surface, COLORS['BLACK'], slider.rect, 1)
        if slider.max_value <= slider.min_value:
            ratio = 1.0
        else:
            ratio = (slider.value - slider.min_value) / (slider.max_value - slider.min_value)
        handle_x = slider.rect.x + int(max(0.0, min(1.0, ratio)) * slider.rect.width)
        handle_rect = pygame.Rect(handle_x - 4, slider.rect.y - 4, 8, slider.rect.height + 8)
        pygame.draw.rect(surface, COLORS['YELLOW'], handle_rect)
        pygame.draw.rect(surface, COLORS['BLACK'], handle_rect, 1)
    
    def _set_city_soldier_quantity(self, value: int):
        self.city_soldier_quantity = value
    
    def _set_move_soldier_quantity(self, value: int):
        self.move_soldier_quantity = value
    
    def _slider_value_from_pos(self, slider: Slider, pos: tuple) -> int:
        if slider.max_value <= slider.min_value:
            return slider.min_value
        ratio = (pos[0] - slider.rect.x) / max(1, slider.rect.width)
        ratio = max(0.0, min(1.0, ratio))
        return int(round(slider.min_value + ratio * (slider.max_value - slider.min_value)))
    
    def _update_slider_from_pos(self, slider: Slider, pos: tuple):
        value = self._slider_value_from_pos(slider, pos)
        slider.value = value
        slider.callback(value)
    
    def handle_mouse_down(self, pos: tuple) -> bool:
        """左键按下时尝试捕获滑块。"""
        for slider in reversed(self.sliders):
            if slider.rect.inflate(8, 12).collidepoint(pos):
                self.active_slider = slider
                self._update_slider_from_pos(slider, pos)
                return True
        return False
    
    def handle_mouse_drag(self, pos: tuple) -> bool:
        """拖动当前捕获的滑块。"""
        if not self.active_slider:
            return False
        self._update_slider_from_pos(self.active_slider, pos)
        return True
    
    def handle_mouse_up(self, pos: tuple) -> bool:
        """释放当前捕获的滑块。"""
        if not self.active_slider:
            return False
        self._update_slider_from_pos(self.active_slider, pos)
        self.active_slider = None
        return True
    
    def _render_message_log(self, surface: pygame.Surface):
        """渲染底部消息栏。"""
        if not self.messages:
            return
        
        panel_x = 10
        panel_y = self.screen_height - 120
        panel_width = min(620, self.screen_width - 280)
        panel_height = 105
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(surface, COLORS['WHITE'], panel_rect)
        pygame.draw.rect(surface, COLORS['BLACK'], panel_rect, 2)
        
        title = self.font_manager.render_text("消息", 'small', COLORS['BLACK'])
        surface.blit(title, (panel_x + 10, panel_y + 8))
        
        y_offset = panel_y + 28
        for message in self.messages[-4:]:
            text = self.font_manager.render_text(message, 'small', COLORS['DARK_GRAY'])
            surface.blit(text, (panel_x + 10, y_offset))
            y_offset += 18
    
    def _render_game_over_panel(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        """渲染游戏结束面板。"""
        panel_width = 360
        panel_height = 160
        panel_x = (self.screen_width - panel_width) // 2
        panel_y = 80
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(surface, COLORS['WHITE'], panel_rect)
        pygame.draw.rect(surface, COLORS['BLACK'], panel_rect, 3)
        
        title = self.font_manager.render_text("游戏结束", 'large', COLORS['BLACK'])
        title_rect = title.get_rect(center=(panel_x + panel_width // 2, panel_y + 40))
        surface.blit(title, title_rect)
        
        winner = game_state.get('winner')
        winner_name = winner.name if winner else "无"
        winner_text = self.font_manager.render_text(f"获胜者：{winner_name}", 'medium', COLORS['BLACK'])
        winner_rect = winner_text.get_rect(center=(panel_x + panel_width // 2, panel_y + 85))
        surface.blit(winner_text, winner_rect)
        
        hint = self.font_manager.render_text("按 R 重新开始 / ESC 退出", 'small', COLORS['DARK_GRAY'])
        hint_rect = hint.get_rect(center=(panel_x + panel_width // 2, panel_y + 125))
        surface.blit(hint, hint_rect)
    
    def _render_turn_info(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        """渲染回合信息"""
        turn_number = game_state.get('turn_number', 1)
        text = self.font_manager.render_text(f"回合 {turn_number}", 'medium', COLORS['BLACK'])
        surface.blit(text, (10, 10))
        
        # 结束回合按钮
        end_turn_button = Button(
            rect=pygame.Rect(10, 50, 100, 30),
            text="结束回合",
            callback=self._end_turn,
            color=COLORS['GREEN'],
            text_color=COLORS['WHITE']
        )
        self._draw_button(surface, end_turn_button)
        
        # 保存按钮
        save_button = Button(
            rect=pygame.Rect(120, 50, 80, 30),
            text="保存",
            callback=self._save_game,
            color=COLORS['BLUE'],
            text_color=COLORS['WHITE']
        )
        self._draw_button(surface, save_button)
        
        # 加载按钮
        load_button = Button(
            rect=pygame.Rect(210, 50, 80, 30),
            text="加载",
            callback=self._load_game,
            color=COLORS['ORANGE'],
            text_color=COLORS['WHITE']
        )
        self._draw_button(surface, load_button)
        
        buttons = [end_turn_button, save_button, load_button]
        selected_unit = game_state.get('selected_unit')
        if selected_unit and selected_unit.unit_type == UnitType.SETTLER:
            build_city_button = Button(
                rect=pygame.Rect(300, 50, 90, 30),
                text="建城(B)",
                callback=self._build_city,
                color=COLORS['PURPLE'],
                text_color=COLORS['WHITE']
            )
            self._draw_button(surface, build_city_button)
            buttons.append(build_city_button)
        
        # 更新按钮列表
        self.buttons = buttons
    
    def handle_click(self, pos: tuple) -> bool:
        """处理UI点击事件"""
        # 检查滑块
        if self.handle_mouse_down(pos):
            self.handle_mouse_up(pos)
            return True
        
        # 检查常规按钮
        for button in self.buttons:
            if button.rect.collidepoint(pos):
                if button.enabled:
                    button.callback()
                elif button.disabled_message:
                    self.add_message(button.disabled_message)
                return True
        
        # 检查城市面板按钮
        if hasattr(self, '_temp_city_buttons'):
            for button in self._temp_city_buttons:
                if button.rect.collidepoint(pos):
                    if button.enabled:
                        button.callback()
                    elif button.disabled_message:
                        self.add_message(button.disabled_message)
                    return True
        
        return False
    
    def show_city_panel_for(self, city: City):
        """显示城市面板"""
        self.show_city_panel = True
        self.selected_city = city
    
    def _close_city_panel(self):
        """关闭城市面板"""
        self.show_city_panel = False
        self.selected_city = None
        if hasattr(self, '_temp_city_buttons'):
            self._temp_city_buttons = []
    
    def _build_unit(self, city: City, unit_type: UnitType, quantity: int = 1):
        """建造单位(需要回调到主系统)"""
        if hasattr(self, 'on_build_unit'):
            self.on_build_unit(city.id, unit_type, quantity)
    
    def _build_city(self):
        """建立城市(需要回调到主系统)"""
        if self.on_build_city:
            self.on_build_city()
    
    def _end_turn(self):
        """结束回合"""
        if hasattr(self, 'on_end_turn'):
            self.on_end_turn()
    
    def _save_game(self):
        """保存游戏"""
        if hasattr(self, 'on_save_game'):
            self.on_save_game()
    
    def _load_game(self):
        """加载游戏"""
        if hasattr(self, 'on_load_game'):
            self.on_load_game()
    
    def set_callbacks(self, on_build_unit: Callable = None, 
                     on_end_turn: Callable = None, on_save_game: Callable = None,
                     on_load_game: Callable = None, on_build_city: Callable = None):
        """设置回调函数"""
        if on_build_unit:
            self.on_build_unit = on_build_unit
        if on_end_turn:
            self.on_end_turn = on_end_turn
        if on_save_game:
            self.on_save_game = on_save_game
        if on_load_game:
            self.on_load_game = on_load_game
        if on_build_city:
            self.on_build_city = on_build_city
