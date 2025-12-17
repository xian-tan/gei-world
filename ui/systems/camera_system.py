"""
摄像机系统 - 地图缩放、平移
"""
import pygame
from typing import Tuple


class CameraSystem:
    """摄像机系统"""
    
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = 0
        self.y = 0
        self.zoom = 1.0
        self.min_zoom = 0.3
        self.max_zoom = 3.0
        self.move_speed = 5
        
    def move(self, dx: int, dy: int):
        """移动摄像机"""
        self.x += dx / self.zoom
        self.y += dy / self.zoom
    
    def zoom_at(self, zoom_factor: float, screen_x: int = None, screen_y: int = None):
        """在指定位置缩放"""
        if screen_x is None:
            screen_x = self.screen_width // 2
        if screen_y is None:
            screen_y = self.screen_height // 2
        
        # 计算缩放前的世界坐标
        world_x_before = (screen_x - self.screen_width // 2) / self.zoom + self.x
        world_y_before = (screen_y - self.screen_height // 2) / self.zoom + self.y
        
        # 更新缩放级别
        old_zoom = self.zoom
        self.zoom *= zoom_factor
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom))
        
        # 计算缩放后的世界坐标，调整摄像机位置使缩放点保持不变
        world_x_after = (screen_x - self.screen_width // 2) / self.zoom + self.x
        world_y_after = (screen_y - self.screen_height // 2) / self.zoom + self.y
        
        # 调整摄像机位置
        self.x += world_x_before - world_x_after
        self.y += world_y_before - world_y_after
    
    def set_position(self, x: int, y: int):
        """设置摄像机位置"""
        self.x = x
        self.y = y
    
    def get_position(self) -> Tuple[int, int]:
        """获取摄像机位置"""
        return int(self.x), int(self.y)
    
    def get_zoom(self) -> float:
        """获取缩放级别"""
        return self.zoom
    
    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """世界坐标转屏幕坐标"""
        screen_x = (world_x - self.x) * self.zoom + self.screen_width // 2
        screen_y = (world_y - self.y) * self.zoom + self.screen_height // 2
        return int(screen_x), int(screen_y)
    
    def screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """屏幕坐标转世界坐标"""
        world_x = (screen_x - self.screen_width // 2) / self.zoom + self.x
        world_y = (screen_y - self.screen_height // 2) / self.zoom + self.y
        return world_x, world_y
    
    def is_visible(self, world_x: float, world_y: float, margin: float = 100) -> bool:
        """检查世界坐标点是否在屏幕可见范围内"""
        screen_x, screen_y = self.world_to_screen(world_x, world_y)
        return (-margin <= screen_x <= self.screen_width + margin and
                -margin <= screen_y <= self.screen_height + margin)
    
    def get_visible_world_bounds(self) -> Tuple[float, float, float, float]:
        """获取屏幕可见的世界坐标边界"""
        top_left_world = self.screen_to_world(0, 0)
        bottom_right_world = self.screen_to_world(self.screen_width, self.screen_height)
        
        return (
            top_left_world[0],      # left
            top_left_world[1],      # top  
            bottom_right_world[0],  # right
            bottom_right_world[1]   # bottom
        )
