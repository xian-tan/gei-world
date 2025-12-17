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


class UISystem:
    """UI界面系统"""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.buttons = []
        self.panels = {}
        self.font_manager = get_font_manager()
        self.show_city_panel = False
        self.selected_city = None
        
    def render(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        """渲染UI界面"""
        # 渲染右侧信息面板
        self._render_info_panel(surface, game_state)
        
        # 渲染按钮
        self._render_buttons(surface)
        
        # 渲染城市面板
        if self.show_city_panel and self.selected_city:
            self._render_city_panel(surface, self.selected_city)
        
        # 渲染回合信息
        self._render_turn_info(surface, game_state)
    
    def _render_info_panel(self, surface: pygame.Surface, game_state: Dict[str, Any]):
        """渲染信息面板"""
        panel_x = self.screen_width - 250
        panel_y = 10
        panel_width = 240
        panel_height = 300  # 增加高度以显示更多信息
        
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
            text = self.font_manager.render_text(f"💰 金币: {current_player.gold}", 
                                                'small', COLORS['BLACK'])
            surface.blit(text, (panel_x + 10, y_offset))
            y_offset += 20
            
            # 城市数量
            city_count = len(current_player.cities)
            text = self.font_manager.render_text(f"🏙️ 城市: {city_count}", 
                                                'small', COLORS['BLACK'])
            surface.blit(text, (panel_x + 10, y_offset))
            y_offset += 20
            
            # 单位统计
            unit_counts = {}
            for unit in current_player.units:
                unit_type = unit.unit_type.value
                unit_counts[unit_type] = unit_counts.get(unit_type, 0) + 1
            
            for unit_type, count in unit_counts.items():
                text = self.font_manager.render_text(f"👥 {unit_type}: {count}", 
                                                    'small', COLORS['BLACK'])
                surface.blit(text, (panel_x + 10, y_offset))
                y_offset += 20
            
            # 添加控制提示
            y_offset += 10
            help_texts = [
                "=== 控制说明 ===",
                "左键: 选择单位/城市",
                "右键: 移民建城",
                "WASD: 移动地图",
                "滚轮: 缩放",
                "ESC: 取消选择"
            ]
            
            for help_text in help_texts:
                text = self.font_manager.render_text(help_text, 'small', COLORS['DARK_GRAY'])
                surface.blit(text, (panel_x + 10, y_offset))
                y_offset += 16
    
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
        panel_width = 300
        panel_height = 250
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
        settler_cost = 50  # 假设成本
        settler_text = f"移民 ({settler_cost}金币)"
        settler_enabled = city.owner.gold >= settler_cost
        settler_button = Button(
            rect=pygame.Rect(panel_x + 20, y_offset, 120, 30),
            text=settler_text,
            callback=lambda: self._build_unit(city, UnitType.SETTLER),
            enabled=settler_enabled
        )
        self._draw_button(surface, settler_button)
        
        # 士兵按钮
        soldier_cost = 30  # 假设成本
        soldier_text = f"士兵 ({soldier_cost}金币)"
        soldier_enabled = city.owner.gold >= soldier_cost
        soldier_button = Button(
            rect=pygame.Rect(panel_x + 150, y_offset, 120, 30),
            text=soldier_text,
            callback=lambda: self._build_unit(city, UnitType.SOLDIER),
            enabled=soldier_enabled
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
        
        # 更新按钮列表
        self.buttons = [end_turn_button, save_button]
    
    def handle_click(self, pos: tuple) -> bool:
        """处理UI点击事件"""
        # 检查常规按钮
        for button in self.buttons:
            if button.rect.collidepoint(pos) and button.enabled:
                button.callback()
                return True
        
        # 检查城市面板按钮
        if hasattr(self, '_temp_city_buttons'):
            for button in self._temp_city_buttons:
                if button.rect.collidepoint(pos) and button.enabled:
                    button.callback()
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
    
    def _build_unit(self, city: City, unit_type: UnitType):
        """建造单位(需要回调到主系统)"""
        if hasattr(self, 'on_build_unit'):
            self.on_build_unit(city.id, unit_type)
    
    def _end_turn(self):
        """结束回合"""
        if hasattr(self, 'on_end_turn'):
            self.on_end_turn()
    
    def _save_game(self):
        """保存游戏"""
        if hasattr(self, 'on_save_game'):
            self.on_save_game()
    
    def set_callbacks(self, on_build_unit: Callable = None, 
                     on_end_turn: Callable = None, on_save_game: Callable = None):
        """设置回调函数"""
        if on_build_unit:
            self.on_build_unit = on_build_unit
        if on_end_turn:
            self.on_end_turn = on_end_turn
        if on_save_game:
            self.on_save_game = on_save_game
