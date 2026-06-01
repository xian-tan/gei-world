"""
六边形渲染工具类
"""
import pygame
import math
from typing import Tuple, List

from ui.ui_config import HEX_RADIUS


class HexRenderer:
    """六边形渲染器"""
    @staticmethod
    def hex_to_pixel(q: int, r: int, center_x: int = 0, center_y: int = 0) -> Tuple[int, int]:
        """
        六边形轴向坐标转换为像素坐标
        使用平顶式六边形(Flat-top Hex)，支持紧密拼接
        """
        # 标准点顶式六边形坐标转换公式
        x = HEX_RADIUS * (3.0/2.0 * q) + center_x
        y = HEX_RADIUS * (math.sqrt(3.0)/2.0 * q + math.sqrt(3.0) * r) + center_y

        return int(x), int(y)
    @staticmethod
    def pixel_to_hex(x: float, y: float, center_x: float = 0, center_y: float = 0) -> Tuple[int, int]:
        """
        像素坐标转换为六边形轴向坐标
        平顶式六边形逆变换
        """
        # 先转换到相对坐标
        rel_x = x - center_x
        rel_y = y - center_y
        
        # 平顶式六边形的逆变换公式，与 hex_to_pixel 保持互逆
        q = (2.0 / 3.0 * rel_x) / HEX_RADIUS
        r = (-1.0 / 3.0 * rel_x + math.sqrt(3.0) / 3.0 * rel_y) / HEX_RADIUS
        
        return HexRenderer.cube_round(q, r, -q-r)
    
    @staticmethod
    def cube_round(frac_x: float, frac_y: float, frac_z: float) -> Tuple[int, int]:
        """
        立方坐标四舍五入
        """
        rx = round(frac_x)
        ry = round(frac_y)
        rz = round(frac_z)
        
        x_diff = abs(rx - frac_x)
        y_diff = abs(ry - frac_y)
        z_diff = abs(rz - frac_z)
        
        if x_diff > y_diff and x_diff > z_diff:
            rx = -ry - rz
        elif y_diff > z_diff:
            ry = -rx - rz
        else:
            rz = -rx - ry
        
        return rx, ry
    @staticmethod
    def get_hex_corners(center_x: int, center_y: int, radius: int = None) -> List[Tuple[int, int]]:
        """
        获取六边形的6个顶点坐标(平顶式)
        """
        if radius is None:
            radius = HEX_RADIUS
            
        corners = []
        for i in range(6):
            angle_deg = 60 * i  # 平顶式六边形，起始角度0度
            angle_rad = math.pi / 180 * angle_deg
            x = center_x + radius * math.cos(angle_rad)
            y = center_y + radius * math.sin(angle_rad)
            corners.append((int(x), int(y)))
        
        return corners
    
    @staticmethod
    def draw_hex(surface: pygame.Surface, center_x: int, center_y: int, 
                 color: Tuple[int, int, int], border_color: Tuple[int, int, int] = None,
                 radius: int = None, border_width: int = 1):
        """
        绘制六边形
        """
        if radius is None:
            radius = HEX_RADIUS
            
        corners = HexRenderer.get_hex_corners(center_x, center_y, radius)
        
        # 填充六边形
        pygame.draw.polygon(surface, color, corners)
        
        # 绘制边框
        if border_color:
            pygame.draw.polygon(surface, border_color, corners, border_width)
    
    @staticmethod
    def is_point_in_hex(point_x: int, point_y: int, hex_center_x: int, hex_center_y: int, 
                       radius: int = None) -> bool:
        """
        判断点是否在六边形内
        """
        if radius is None:
            radius = HEX_RADIUS
            
        # 简化计算：使用距离判断
        dx = point_x - hex_center_x
        dy = point_y - hex_center_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        return distance <= radius * 0.9  # 稍微缩小判定范围，避免边界问题
