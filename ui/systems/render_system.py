"""
地图渲染系统
"""
import math
import pygame
from typing import Dict, List, Optional, Tuple, Set

import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from src.models import HexCoord, Tile, TerrainType, Player
from ui.hex_renderer import HexRenderer
from ui.ui_config import (
    COLORS, HEX_RADIUS, OFFSET_X, OFFSET_Y, SCREEN_WIDTH, SCREEN_HEIGHT,
    MINIMAP_WIDTH, MINIMAP_HEIGHT, MINIMAP_MARGIN
)


class RenderSystem:
    """地图渲染系统"""
    
    def __init__(self):
        self.camera_x = 0
        self.camera_y = 0
        self.zoom = 1.0
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT
        self.selected_tile = None
        self.hovered_tile = None
        self.selected_unit_id = None  # 添加选中单位ID
        self.reachable_tiles: Set[HexCoord] = set()
        self.selected_city_economic_tiles: Set[HexCoord] = set()
        self.path_preview: List[HexCoord] = []
        self.minimap_rect: Optional[pygame.Rect] = None
        
    def set_selected_unit(self, unit_id: str):
        """设置选中的单位ID"""
        self.selected_unit_id = unit_id
    
    def clear_selected_unit(self):
        """清除选中的单位"""
        self.selected_unit_id = None
        self.clear_reachable_tiles()
        self.clear_path_preview()
    
    def set_path_preview(self, path: List[HexCoord]):
        """设置移动路径预览。"""
        self.path_preview = list(path or [])
    
    def clear_path_preview(self):
        """清除移动路径预览。"""
        self.path_preview.clear()
    
    def set_reachable_tiles(self, reachable_tiles: Set[HexCoord]):
        """设置当前选中单位的可达地块高亮。"""
        self.reachable_tiles = set(reachable_tiles)
    
    def clear_reachable_tiles(self):
        """清除可达地块高亮。"""
        self.reachable_tiles.clear()
    
    def set_selected_city_economic_tiles(self, tiles: Set[HexCoord]):
        """设置选中城市的经济范围轮廓。"""
        self.selected_city_economic_tiles = set(tiles or set())
    
    def clear_selected_city_economic_tiles(self):
        """清除选中城市的经济范围轮廓。"""
        self.selected_city_economic_tiles.clear()
        
    def set_camera(self, x: int, y: int):
        """设置摄像机位置"""
        self.camera_x = x
        self.camera_y = y
    
    def move_camera(self, dx: int, dy: int):
        """移动摄像机"""
        self.camera_x += dx
        self.camera_y += dy
    
    def set_zoom(self, zoom: float):
        """设置缩放级别"""
        self.zoom = max(0.5, min(2.0, zoom))
    
    def world_to_screen(self, world_x: int, world_y: int) -> Tuple[int, int]:
        """世界坐标转屏幕坐标，与 CameraSystem 使用相同原点约定。"""
        screen_x = (world_x - self.camera_x) * self.zoom + self.screen_width // 2
        screen_y = (world_y - self.camera_y) * self.zoom + self.screen_height // 2
        return int(screen_x), int(screen_y)
    
    def screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """屏幕坐标转世界坐标，与 CameraSystem 使用相同原点约定。"""
        world_x = (screen_x - self.screen_width // 2) / self.zoom + self.camera_x
        world_y = (screen_y - self.screen_height // 2) / self.zoom + self.camera_y
        return world_x, world_y
    
    def render_map(self, surface: pygame.Surface, tiles: Dict[HexCoord, Tile], 
                   visible_tiles: Set[HexCoord], explored_tiles: Set[HexCoord],
                   current_player: Player):
        """渲染地图"""
        screen_width = surface.get_width()
        screen_height = surface.get_height()
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # 计算需要渲染的地块范围
        visible_range = self._get_visible_tile_range(screen_width, screen_height)
        
        for coord, tile in tiles.items():
            # 跳过不在屏幕范围内的地块
            if not self._is_tile_in_range(coord, visible_range):
                continue
                
            world_x, world_y = HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y)
            screen_x, screen_y = self.world_to_screen(world_x, world_y)
            
            # 跳过不在屏幕上的地块
            if (screen_x < -HEX_RADIUS or screen_x > screen_width + HEX_RADIUS or
                screen_y < -HEX_RADIUS or screen_y > screen_height + HEX_RADIUS):
                continue
            
            self._render_tile(surface, tile, screen_x, screen_y, 
                            coord in visible_tiles, coord in explored_tiles)
        
        self._render_path_preview(surface, visible_tiles)
    
    def _render_path_preview(self, surface: pygame.Surface, visible_tiles: Set[HexCoord]):
        """用虚线绘制当前移动路径预览。"""
        if len(self.path_preview) < 2:
            return
        points = []
        for coord in self.path_preview:
            if coord not in visible_tiles:
                return
            world_x, world_y = HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y)
            points.append(self.world_to_screen(world_x, world_y))
        for start, end in zip(points, points[1:]):
            self._draw_dashed_line(surface, COLORS['YELLOW'], start, end, width=2)
    
    def _draw_dashed_line(self, surface: pygame.Surface, color: tuple, start: tuple,
                          end: tuple, width: int = 1, dash_length: int = 8, gap_length: int = 5):
        """绘制虚线。"""
        start_x, start_y = start
        end_x, end_y = end
        dx = end_x - start_x
        dy = end_y - start_y
        distance = math.hypot(dx, dy)
        if distance <= 0:
            return
        step_x = dx / distance
        step_y = dy / distance
        current = 0
        while current < distance:
            segment_end = min(current + dash_length, distance)
            segment_start_point = (int(start_x + step_x * current), int(start_y + step_y * current))
            segment_end_point = (int(start_x + step_x * segment_end), int(start_y + step_y * segment_end))
            pygame.draw.line(surface, color, segment_start_point, segment_end_point, width)
            current += dash_length + gap_length
    
    def _render_tile(self, surface: pygame.Surface, tile: Tile, 
                    screen_x: int, screen_y: int, is_visible: bool, is_explored: bool):
        """渲染单个地块"""
        # 确定地块颜色
        if not is_explored:
            # 未探索 - 完全黑
            color = COLORS['BLACK']
        elif not is_visible:
            # 已探索但不可见 - 灰色
            if tile.terrain_type == TerrainType.LAND:
                color = COLORS['EXPLORED']
            else:
                color = COLORS['DARK_GRAY']
        else:
            # 当前可见 - 正常颜色
            if tile.terrain_type == TerrainType.LAND:
                if tile.owner:
                    # 有主人的陆地显示玩家颜色
                    color = self._get_player_color(tile.owner)
                else:
                    color = COLORS['LAND']
            else:
                color = COLORS['OCEAN']
        
        # 特殊状态颜色
        border_color = None
        if tile.coord == self.selected_tile:
            border_color = COLORS['WHITE']
        elif is_visible and tile.coord in self.reachable_tiles:
            border_color = COLORS['YELLOW']
        elif is_visible and tile.coord in self.selected_city_economic_tiles:
            border_color = COLORS['ECONOMIC_RANGE']
        elif tile.coord == self.hovered_tile:
            border_color = COLORS['LIGHT_GRAY']
        
        # 绘制六边形
        radius = int(HEX_RADIUS * self.zoom)
        border_width = 3 if (tile.coord in self.reachable_tiles or tile.coord in self.selected_city_economic_tiles) else (2 if border_color else 1)
        HexRenderer.draw_hex(surface, screen_x, screen_y, color, border_color, 
                           radius, border_width)
        
        # 只在可见时渲染其他元素
        if is_visible:
            self._render_tile_contents(surface, tile, screen_x, screen_y, radius)
    
    def _render_tile_contents(self, surface: pygame.Surface, tile: Tile,
                             screen_x: int, screen_y: int, radius: int):
        """渲染地块内容(城市、单位等)"""
        # 渲染城市
        if tile.city:
            self._render_city(surface, tile.city, screen_x, screen_y, radius)
        
        # 渲染单位
        if tile.units:
            self._render_units(surface, tile.units, screen_x, screen_y, radius)
    
    def _render_city(self, surface: pygame.Surface, city, screen_x: int, screen_y: int, radius: int):
        """渲染城市"""
        # 城市用更大的菱形表示，和单位圆点区分
        city_size = max(14, int(radius * 0.75))
        half_size = city_size // 2
        city_points = [
            (screen_x, screen_y - half_size),
            (screen_x + half_size, screen_y),
            (screen_x, screen_y + half_size),
            (screen_x - half_size, screen_y),
        ]
        
        # 城市颜色为玩家颜色的深色版本
        city_color = self._get_player_color(city.owner)
        city_color = tuple(max(0, c - 50) for c in city_color)
        
        pygame.draw.polygon(surface, city_color, city_points)
        pygame.draw.polygon(surface, COLORS['WHITE'], city_points, 2)
        pygame.draw.polygon(surface, COLORS['BLACK'], city_points, 1)
    def _render_units(self, surface: pygame.Surface, units, screen_x: int, screen_y: int, radius: int):
        """渲染单位"""
        if not units:
            return
        
        unit_size = max(6, int(radius * 0.3))
        
        has_selected_unit = any(unit.id == self.selected_unit_id for unit in units)
        total_count = sum(unit.quantity for unit in units)
        color = self._get_unit_color(units[0])
        pygame.draw.circle(surface, color, (screen_x, screen_y - radius//3), unit_size)
        
        if has_selected_unit:
            pygame.draw.circle(surface, COLORS['WHITE'], (screen_x, screen_y - radius//3), unit_size + 2, 2)
        
        pygame.draw.circle(surface, COLORS['BLACK'], (screen_x, screen_y - radius//3), unit_size, 1)
        
        if total_count > 1:
            font = pygame.font.Font(None, 16)
            text = font.render(str(total_count), True, COLORS['WHITE'])
            text_rect = text.get_rect(center=(screen_x, screen_y - radius//3))
            surface.blit(text, text_rect)
    
    def _get_player_color(self, player: Player) -> Tuple[int, int, int]:
        """获取玩家颜色"""
        player_colors = [
            COLORS['PLAYER_1'],
            COLORS['PLAYER_2'], 
            COLORS['PLAYER_3'],
            COLORS['PLAYER_4']
        ]
        
        try:
            player_index = int(str(player.id).split('_')[-1]) % len(player_colors)
        except (TypeError, ValueError):
            player_index = sum(ord(char) for char in str(player.id)) % len(player_colors)
        return player_colors[player_index]
    
    def _get_unit_color(self, unit) -> Tuple[int, int, int]:
        """获取单位颜色"""
        base_color = self._get_player_color(unit.owner)
        # 单位颜色稍微亮一些
        return tuple(min(255, c + 30) for c in base_color)
    
    def render_minimap(self, surface: pygame.Surface, tiles: Dict[HexCoord, Tile],
                       visible_tiles: Set[HexCoord], explored_tiles: Set[HexCoord]):
        """渲染右下角小地图。"""
        if not tiles:
            return
        
        minimap_x = surface.get_width() - MINIMAP_WIDTH - MINIMAP_MARGIN
        minimap_y = surface.get_height() - MINIMAP_HEIGHT - MINIMAP_MARGIN
        self.minimap_rect = pygame.Rect(minimap_x, minimap_y, MINIMAP_WIDTH, MINIMAP_HEIGHT)
        pygame.draw.rect(surface, COLORS['MINIMAP_BACKGROUND'], self.minimap_rect)
        pygame.draw.rect(surface, COLORS['MINIMAP_BORDER'], self.minimap_rect, 2)
        
        points = {
            coord: HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y)
            for coord in tiles.keys()
        }
        min_x = min(point[0] for point in points.values())
        max_x = max(point[0] for point in points.values())
        min_y = min(point[1] for point in points.values())
        max_y = max(point[1] for point in points.values())
        map_width = max(1, max_x - min_x)
        map_height = max(1, max_y - min_y)
        scale = min((MINIMAP_WIDTH - 12) / map_width, (MINIMAP_HEIGHT - 12) / map_height)
        offset_x = minimap_x + (MINIMAP_WIDTH - map_width * scale) / 2
        offset_y = minimap_y + (MINIMAP_HEIGHT - map_height * scale) / 2
        
        for coord, tile in tiles.items():
            world_x, world_y = points[coord]
            mini_x = int(offset_x + (world_x - min_x) * scale)
            mini_y = int(offset_y + (world_y - min_y) * scale)
            if coord in visible_tiles:
                if tile.terrain_type == TerrainType.OCEAN:
                    color = COLORS['OCEAN']
                elif tile.owner:
                    color = self._get_player_color(tile.owner)
                else:
                    color = COLORS['LAND']
            elif coord in explored_tiles:
                color = COLORS['EXPLORED'] if tile.terrain_type == TerrainType.LAND else COLORS['DARK_GRAY']
            else:
                color = COLORS['BLACK']
            pygame.draw.rect(surface, color, pygame.Rect(mini_x, mini_y, 3, 3))
        
        left, top, right, bottom = self._get_visible_world_bounds()
        view_x = int(offset_x + (left - min_x) * scale)
        view_y = int(offset_y + (top - min_y) * scale)
        view_w = max(3, int((right - left) * scale))
        view_h = max(3, int((bottom - top) * scale))
        pygame.draw.rect(surface, COLORS['MINIMAP_VIEWPORT'], pygame.Rect(view_x, view_y, view_w, view_h), 1)
    
    def _get_visible_world_bounds(self) -> Tuple[float, float, float, float]:
        """获取当前屏幕对应的世界坐标范围。"""
        left, top = self.screen_to_world(0, 0)
        right, bottom = self.screen_to_world(self.screen_width, self.screen_height)
        return left, top, right, bottom
    
    def is_minimap_pos(self, pos: tuple) -> bool:
        """判断屏幕坐标是否落在小地图内。"""
        return bool(self.minimap_rect and self.minimap_rect.collidepoint(pos))
    
    def _get_visible_tile_range(self, screen_width: int, screen_height: int) -> Dict:
        """计算屏幕可见的地块范围"""
        # 简化实现：返回一个大致的范围
        world_left, world_top = self.screen_to_world(0, 0)
        world_right, world_bottom = self.screen_to_world(screen_width, screen_height)
        
        return {
            'left': world_left - HEX_RADIUS,
            'right': world_right + HEX_RADIUS,
            'top': world_top - HEX_RADIUS,
            'bottom': world_bottom + HEX_RADIUS
        }
    
    def _is_tile_in_range(self, coord: HexCoord, visible_range: Dict) -> bool:
        """检查地块是否在可见范围内"""
        world_x, world_y = HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y)
        return (visible_range['left'] <= world_x <= visible_range['right'] and
                visible_range['top'] <= world_y <= visible_range['bottom'])
    
    def get_tile_at_screen_pos(self, screen_x: int, screen_y: int) -> Optional[HexCoord]:
        """获取屏幕位置对应的地块坐标"""
        world_x, world_y = self.screen_to_world(screen_x, screen_y)
        q, r = HexRenderer.pixel_to_hex(world_x, world_y, OFFSET_X, OFFSET_Y)
        return HexCoord(q, r)
