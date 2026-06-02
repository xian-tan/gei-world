"""
输入处理系统
"""
import pygame
from typing import Optional, Tuple, Callable
from enum import Enum

import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.models import HexCoord


class InputMode(Enum):
    NORMAL = "normal"
    UNIT_SELECTED = "unit_selected"
    CITY_SELECTED = "city_selected"


class InputSystem:
    """输入处理系统"""
    
    def __init__(self):
        self.mode = InputMode.NORMAL
        self.selected_unit_id = None
        self.selected_city_id = None
        self.mouse_pos = (0, 0)
        self.mouse_pressed = False
        self.keys_pressed = set()
        
        # 事件回调
        self.on_tile_clicked = None
        self.on_tile_right_clicked = None
        self.on_camera_move = None
        self.on_zoom = None
        self.on_key_pressed = None
        self.on_mouse_down = None
        self.on_mouse_drag = None
        self.on_mouse_up = None
    
    def handle_events(self, events):
        """处理pygame事件"""
        for event in events:
            if event.type == pygame.QUIT:
                return False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_down(event)
            
            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouse_up(event)
            
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event)
            
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_mouse_wheel(event)
            
            elif event.type == pygame.KEYDOWN:
                self._handle_key_down(event)
            
            elif event.type == pygame.KEYUP:
                self._handle_key_up(event)
        
        return True
    
    def _handle_mouse_down(self, event):
        """处理鼠标按下"""
        self.mouse_pos = event.pos
        
        if event.button == 1:  # 左键
            self.mouse_pressed = True
            self.mouse_captured_by_ui = bool(self.on_mouse_down and self.on_mouse_down(event.pos))
        elif event.button == 3:  # 右键
            if self.on_tile_right_clicked:
                self.on_tile_right_clicked(event.pos)
    
    def _handle_mouse_up(self, event):
        """处理鼠标抬起"""
        if event.button == 1:  # 左键
            was_captured = self.mouse_captured_by_ui
            self.mouse_pressed = False
            self.mouse_captured_by_ui = False
            if was_captured:
                if self.on_mouse_up:
                    self.on_mouse_up(event.pos)
                return
            if self.on_tile_clicked:
                self.on_tile_clicked(event.pos)
    
    def _handle_mouse_motion(self, event):
        """处理鼠标移动"""
        old_pos = self.mouse_pos
        self.mouse_pos = event.pos
        
        # 如果 UI 捕获了鼠标，优先交给 UI 拖动逻辑
        if self.mouse_pressed and self.mouse_captured_by_ui:
            if self.on_mouse_drag:
                self.on_mouse_drag(event.pos)
            return
        
        # 如果按住鼠标，进行摄像机拖拽
        if self.mouse_pressed and self.on_camera_move:
            dx = event.pos[0] - old_pos[0]
            dy = event.pos[1] - old_pos[1]
            self.on_camera_move(-dx, -dy)  # 反向移动摄像机
    
    def _handle_mouse_wheel(self, event):
        """处理鼠标滚轮"""
        if self.on_zoom:
            zoom_factor = 1.1 if event.y > 0 else 0.9
            self.on_zoom(zoom_factor)
    
    def _handle_key_down(self, event):
        """处理按键按下"""
        self.keys_pressed.add(event.key)
        
        if self.on_key_pressed:
            self.on_key_pressed(event.key, True)
    
    def _handle_key_up(self, event):
        """处理按键抬起"""
        self.keys_pressed.discard(event.key)
        
        if self.on_key_pressed:
            self.on_key_pressed(event.key, False)
    
    def update(self):
        """更新输入状态"""
        # 处理持续按键(如WASD移动摄像机)
        if self.on_camera_move:
            dx, dy = 0, 0
            speed = 5
            
            if pygame.K_a in self.keys_pressed or pygame.K_LEFT in self.keys_pressed:
                dx -= speed
            if pygame.K_d in self.keys_pressed or pygame.K_RIGHT in self.keys_pressed:
                dx += speed
            if pygame.K_w in self.keys_pressed or pygame.K_UP in self.keys_pressed:
                dy -= speed
            if pygame.K_s in self.keys_pressed or pygame.K_DOWN in self.keys_pressed:
                dy += speed
            
            if dx != 0 or dy != 0:
                self.on_camera_move(dx, dy)
    
    def set_mode(self, mode: InputMode, selected_id: str = None):
        """设置输入模式"""
        self.mode = mode
        if mode == InputMode.UNIT_SELECTED:
            self.selected_unit_id = selected_id
            self.selected_city_id = None
        elif mode == InputMode.CITY_SELECTED:
            self.selected_city_id = selected_id
            self.selected_unit_id = None
        else:
            self.selected_unit_id = None
            self.selected_city_id = None
    
    def get_selected_unit_id(self) -> Optional[str]:
        """获取选中的单位ID"""
        return self.selected_unit_id
    
    def get_selected_city_id(self) -> Optional[str]:
        """获取选中的城市ID"""
        return self.selected_city_id
    
    def is_unit_selected(self) -> bool:
        """是否选中了单位"""
        return self.mode == InputMode.UNIT_SELECTED and self.selected_unit_id is not None
    
    def is_city_selected(self) -> bool:
        """是否选中了城市"""
        return self.mode == InputMode.CITY_SELECTED and self.selected_city_id is not None
