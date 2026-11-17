"""
地图渲染系统：地形着色、海岸、领土国境线、城市/单位图标、高亮、路径预览、小地图与战斗浮字。
"""
import math
import time
from typing import Dict, List, Optional, Set, Tuple

import pygame

from src.models import HexCoord, Player, TerrainType, Tile, UnitType
from ui.font_manager import get_font_manager
from ui.hex_renderer import HexRenderer
from ui.ui_config import (COLORS, HEX_RADIUS, MINIMAP_HEIGHT, MINIMAP_MARGIN, MINIMAP_WIDTH, OFFSET_X, OFFSET_Y,
                          SCREEN_HEIGHT, SCREEN_WIDTH)

PLAYER_COLOR_KEYS = ['PLAYER_1', 'PLAYER_2', 'PLAYER_3', 'PLAYER_4']


def _mix(a: Tuple[int, int, int], b: Tuple[int, int, int], ratio: float) -> Tuple[int, int, int]:
    return tuple(int(a[i] * (1 - ratio) + b[i] * ratio) for i in range(3))


def _shade(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in color)


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
        self.selected_unit_id = None
        self.reachable_tiles: Set[HexCoord] = set()
        self.attention_tiles: Set[HexCoord] = set()
        self.selected_city_economic_tiles: Set[HexCoord] = set()
        self.path_preview: List[HexCoord] = []
        self.minimap_rect: Optional[pygame.Rect] = None
        self.floating_texts: List[Dict] = []
        self._fonts: Dict[int, pygame.font.Font] = {}
        self._terrain_cache_key = None
        self._terrain_colors: Dict[HexCoord, Tuple[int, int, int]] = {}

    def _font(self, size: int) -> pygame.font.Font:
        """缓存字体对象，避免每帧重复创建。"""
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    # ------------------------------------------------------------------ 状态设置
    def set_selected_unit(self, unit_id: str):
        self.selected_unit_id = unit_id

    def clear_selected_unit(self):
        self.selected_unit_id = None
        self.clear_reachable_tiles()
        self.clear_path_preview()

    def set_path_preview(self, path: List[HexCoord]):
        self.path_preview = list(path or [])

    def clear_path_preview(self):
        self.path_preview.clear()

    def set_reachable_tiles(self, reachable_tiles: Set[HexCoord]):
        self.reachable_tiles = set(reachable_tiles)

    def clear_reachable_tiles(self):
        self.reachable_tiles.clear()

    def set_attention_tiles(self, tiles: Set[HexCoord]):
        self.attention_tiles = set(tiles or set())

    def clear_attention_tiles(self):
        self.attention_tiles.clear()

    def set_selected_city_economic_tiles(self, tiles: Set[HexCoord]):
        self.selected_city_economic_tiles = set(tiles or set())

    def clear_selected_city_economic_tiles(self):
        self.selected_city_economic_tiles.clear()

    def add_floating_text(self, coord: HexCoord, text: str, color=None, duration: float = 1.4):
        """在地块上方显示上浮文字（战斗、攻城结果）。"""
        self.floating_texts.append({
            "coord": coord, "text": text, "color": color or COLORS['WARNING'],
            "start": time.monotonic(), "duration": duration,
        })

    # ------------------------------------------------------------------ 坐标
    def set_camera(self, x: int, y: int):
        self.camera_x, self.camera_y = x, y

    def move_camera(self, dx: int, dy: int):
        self.camera_x += dx
        self.camera_y += dy

    def set_zoom(self, zoom: float):
        self.zoom = max(0.5, min(2.0, zoom))

    def world_to_screen(self, world_x: int, world_y: int) -> Tuple[int, int]:
        """世界坐标转屏幕坐标，与 CameraSystem 使用相同原点约定。"""
        screen_x = (world_x - self.camera_x) * self.zoom + self.screen_width // 2
        screen_y = (world_y - self.camera_y) * self.zoom + self.screen_height // 2
        return int(screen_x), int(screen_y)

    def screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        world_x = (screen_x - self.screen_width // 2) / self.zoom + self.camera_x
        world_y = (screen_y - self.screen_height // 2) / self.zoom + self.camera_y
        return world_x, world_y

    def _screen_pos(self, coord: HexCoord) -> Tuple[int, int]:
        return self.world_to_screen(*HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y))

    # ------------------------------------------------------------------ 地形色
    def _terrain_palette(self, tiles: Dict[HexCoord, Tile]) -> Dict[HexCoord, Tuple[int, int, int]]:
        """按地形、海岸、坐标噪声预计算基础色；地形变化时自动重建。"""
        key = (id(tiles), len(tiles), sum(1 for t in tiles.values() if t.terrain_type == TerrainType.LAND))
        if key == self._terrain_cache_key:
            return self._terrain_colors
        colors = {}
        for coord, tile in tiles.items():
            noise = (((coord.q * 73856093) ^ (coord.r * 19349663)) & 0xFF) / 255.0
            if tile.terrain_type == TerrainType.LAND:
                base = _mix(COLORS['LAND'], COLORS['LAND_DARK'], noise * 0.6)
            else:
                near_land = any(
                    tiles.get(n) is not None and tiles[n].terrain_type == TerrainType.LAND
                    for n in coord.neighbors()
                )
                base = COLORS['COAST'] if near_land else _mix(COLORS['OCEAN'], COLORS['DEEP_OCEAN'], 0.4 + noise * 0.4)
            colors[coord] = base
        self._terrain_cache_key = key
        self._terrain_colors = colors
        return colors

    # ------------------------------------------------------------------ 地图
    def render_map(self, surface: pygame.Surface, tiles: Dict[HexCoord, Tile],
                   visible_tiles: Set[HexCoord], explored_tiles: Set[HexCoord],
                   current_player: Player):
        """渲染地图：地形 → 国境线 → 高亮 → 城市/单位 → 路径与浮字。"""
        self.screen_width, self.screen_height = surface.get_width(), surface.get_height()
        radius = max(4, int(HEX_RADIUS * self.zoom))
        palette = self._terrain_palette(tiles)
        on_screen = []
        for coord, tile in tiles.items():
            x, y = self._screen_pos(coord)
            if -radius <= x <= self.screen_width + radius and -radius <= y <= self.screen_height + radius:
                on_screen.append((coord, tile, x, y))

        for coord, tile, x, y in on_screen:
            self._render_tile(surface, tile, x, y, coord in visible_tiles, coord in explored_tiles,
                              palette.get(coord, COLORS['LAND']), radius)
        for coord, tile, x, y in on_screen:
            if coord in explored_tiles and tile.owner:
                self._render_borders(surface, tiles, tile, x, y, radius, coord in visible_tiles, explored_tiles)
        for coord, tile, x, y in on_screen:
            self._render_highlight(surface, coord, x, y, radius, coord in visible_tiles)
        for coord, tile, x, y in on_screen:
            if coord in visible_tiles:
                self._render_tile_contents(surface, tile, x, y, radius)
        self._render_path_preview(surface, visible_tiles)
        self._render_floating_texts(surface)

    def _render_tile(self, surface, tile: Tile, x: int, y: int, is_visible: bool, is_explored: bool,
                     base_color=None, radius: int = None):
        radius = radius or max(4, int(HEX_RADIUS * self.zoom))
        base_color = base_color or (COLORS['LAND'] if tile.terrain_type == TerrainType.LAND else COLORS['OCEAN'])
        if not is_explored:
            color = (12, 14, 20)
        else:
            color = base_color
            if tile.owner and tile.terrain_type == TerrainType.LAND:
                color = _mix(color, self._get_player_color(tile.owner), 0.45)
            if not is_visible:
                gray = sum(color) // 3
                color = _shade(_mix(color, (gray, gray, gray), 0.6), 0.55)
        corners = HexRenderer.get_hex_corners(x, y, radius)
        pygame.draw.polygon(surface, color, corners)
        if is_explored and radius >= 8:
            pygame.draw.polygon(surface, _shade(color, 0.75), corners, 1)

    def _render_borders(self, surface, tiles, tile: Tile, x: int, y: int, radius: int, visible: bool,
                        explored_tiles: Set[HexCoord]):
        """只在领土与非同一所有者的邻格之间绘制国境线。"""
        color = self._get_player_color(tile.owner)
        if not visible:
            color = _shade(color, 0.6)
        width = max(2, radius // 7)
        for neighbor in tile.coord.neighbors():
            other = tiles.get(neighbor)
            if other is not None and neighbor in explored_tiles and other.owner == tile.owner:
                continue
            nx, ny = self._screen_pos(neighbor)
            mx, my = (x + nx) / 2, (y + ny) / 2
            dx, dy = nx - x, ny - y
            length = math.hypot(dx, dy) or 1
            px, py = -dy / length * radius / 2, dx / length * radius / 2
            inset_x, inset_y = -dx / length * width / 2, -dy / length * width / 2
            start = (int(mx + px + inset_x), int(my + py + inset_y))
            end = (int(mx - px + inset_x), int(my - py + inset_y))
            pygame.draw.line(surface, color, start, end, width)

    def _render_highlight(self, surface, coord: HexCoord, x: int, y: int, radius: int, visible: bool):
        border_color, width = None, 2
        if coord == self.selected_tile:
            border_color, width = COLORS['WHITE'], 3
        elif visible and coord in self.reachable_tiles:
            border_color, width = COLORS['YELLOW'], 2
        elif visible and coord in self.attention_tiles:
            border_color, width = COLORS['ORANGE'], 3
        elif visible and coord in self.selected_city_economic_tiles:
            border_color, width = COLORS['ECONOMIC_RANGE'], 2
        elif coord == self.hovered_tile:
            border_color, width = COLORS['LIGHT_GRAY'], 1
        if border_color:
            pygame.draw.polygon(surface, border_color, HexRenderer.get_hex_corners(x, y, radius - 1), width)

    def _render_tile_contents(self, surface: pygame.Surface, tile: Tile, screen_x: int, screen_y: int, radius: int):
        if tile.city:
            self._render_city(surface, tile.city, screen_x, screen_y, radius)
        if tile.units:
            self._render_units(surface, tile.units, screen_x, screen_y, radius, below_city=bool(tile.city))

    def _render_city(self, surface: pygame.Surface, city, screen_x: int, screen_y: int, radius: int):
        """城市：城堡图标 + 防御值徽标。"""
        size = max(10, int(radius * 0.9))
        half = size // 2
        color = _shade(self._get_player_color(city.owner), 0.8)
        top = screen_y - half + size // 5
        body = pygame.Rect(screen_x - half, top, size, size - size // 5)
        merlon = max(2, size // 5)
        points = [(body.left, body.bottom), (body.left, body.top - merlon)]
        for index in range(5):
            x0 = body.left + index * size // 5
            x1 = body.left + (index + 1) * size // 5
            y_top = body.top - merlon if index % 2 == 0 else body.top
            points += [(x0, y_top), (x1, y_top)]
        points += [(body.right, body.top - merlon), (body.right, body.bottom)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, COLORS['WHITE'], points, 2)
        gate = pygame.Rect(0, 0, max(3, size // 4), max(4, size // 3))
        gate.midbottom = body.midbottom
        pygame.draw.rect(surface, (30, 24, 20), gate)
        if radius >= 12:
            badge = (body.right, body.top - merlon)
            pygame.draw.circle(surface, COLORS['PANEL_BG'], badge, max(6, radius // 3))
            text = self._font(max(14, radius // 2 + 6)).render(str(getattr(city, 'defense', 0)), True, COLORS['WHITE'])
            surface.blit(text, text.get_rect(center=badge))

    def _render_units(self, surface: pygame.Surface, units, screen_x: int, screen_y: int, radius: int,
                      below_city: bool = False):
        """移民和士兵同格时左右错开显示；有城市时下移避免遮挡城市图标。"""
        settlers = [unit for unit in units if unit.unit_type == UnitType.SETTLER]
        soldiers = [unit for unit in units if unit.unit_type == UnitType.SOLDIER]
        groups = [(UnitType.SETTLER, settlers)] if settlers else []
        if soldiers:
            groups.append((UnitType.SOLDIER, soldiers))
        if not groups:
            return
        offsets = [0] if len(groups) == 1 else [-max(7, radius // 3), max(7, radius // 3)]
        base_y = screen_y + (radius // 2 if below_city else 0)
        for (unit_type, group), offset_x in zip(groups, offsets):
            count = sum(unit.quantity for unit in group)
            selected = any(unit.id == self.selected_unit_id for unit in group)
            self._draw_unit_marker(surface, unit_type, self._get_unit_color(group[0]),
                                   (screen_x + offset_x, base_y), count, selected, radius)

    def _draw_unit_marker(self, surface: pygame.Surface, unit_type: UnitType, color: tuple,
                          center: tuple, count: int, selected: bool, radius: int):
        size = max(5, int(radius * 0.36))
        x, y = center
        if unit_type == UnitType.SETTLER:
            points = [(x - size, y + size), (x - size, y - size // 3), (x, y - size - size // 2),
                      (x + size, y - size // 3), (x + size, y + size)]
        else:
            points = [(x - size, y - size), (x + size, y - size), (x + size, y + size // 3),
                      (x, y + size + size // 2), (x - size, y + size // 3)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, COLORS['WHITE'] if selected else (20, 20, 20), points, 2 if selected else 1)
        if count > 1 or unit_type == UnitType.SOLDIER:
            text = self._font(max(14, size + 8)).render(str(count), True, COLORS['WHITE'])
            rect = text.get_rect(center=(x, y))
            shadow = self._font(max(14, size + 8)).render(str(count), True, (0, 0, 0))
            surface.blit(shadow, rect.move(1, 1))
            surface.blit(text, rect)

    def _get_player_color(self, player: Player) -> Tuple[int, int, int]:
        """玩家颜色按 player_N 序号稳定分配。"""
        try:
            index = int(str(player.id).split('_')[-1]) % len(PLAYER_COLOR_KEYS)
        except (TypeError, ValueError):
            index = sum(ord(char) for char in str(player.id)) % len(PLAYER_COLOR_KEYS)
        return COLORS[PLAYER_COLOR_KEYS[index]]

    def _get_unit_color(self, unit) -> Tuple[int, int, int]:
        return tuple(min(255, c + 30) for c in self._get_player_color(unit.owner))

    # ------------------------------------------------------------------ 叠加层
    def _render_path_preview(self, surface: pygame.Surface, visible_tiles: Set[HexCoord]):
        if len(self.path_preview) < 2:
            return
        if any(coord not in visible_tiles for coord in self.path_preview):
            return
        points = [self._screen_pos(coord) for coord in self.path_preview]
        for start, end in zip(points, points[1:]):
            self._draw_dashed_line(surface, COLORS['YELLOW'], start, end, width=3)
        pygame.draw.circle(surface, COLORS['YELLOW'], points[-1], max(4, int(HEX_RADIUS * self.zoom) // 4))

    def _draw_dashed_line(self, surface: pygame.Surface, color: tuple, start: tuple,
                          end: tuple, width: int = 1, dash_length: int = 8, gap_length: int = 5):
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = math.hypot(dx, dy)
        if distance <= 0:
            return
        step_x, step_y = dx / distance, dy / distance
        current = 0
        while current < distance:
            segment_end = min(current + dash_length, distance)
            pygame.draw.line(surface, color,
                             (int(start[0] + step_x * current), int(start[1] + step_y * current)),
                             (int(start[0] + step_x * segment_end), int(start[1] + step_y * segment_end)), width)
            current += dash_length + gap_length

    def _render_floating_texts(self, surface):
        now = time.monotonic()
        alive = []
        fonts = get_font_manager()
        for item in self.floating_texts:
            progress = (now - item["start"]) / item["duration"]
            if progress >= 1:
                continue
            alive.append(item)
            x, y = self._screen_pos(item["coord"])
            rendered = fonts.render_text(item["text"], 'medium', item["color"])
            rendered.set_alpha(int(255 * (1 - progress)))
            surface.blit(rendered, rendered.get_rect(center=(x, y - 20 - int(progress * 30))))
        self.floating_texts = alive

    # ------------------------------------------------------------------ 小地图
    def render_minimap(self, surface: pygame.Surface, tiles: Dict[HexCoord, Tile],
                       visible_tiles: Set[HexCoord], explored_tiles: Set[HexCoord]):
        if not tiles:
            return
        minimap_x = surface.get_width() - MINIMAP_WIDTH - MINIMAP_MARGIN
        minimap_y = surface.get_height() - MINIMAP_HEIGHT - MINIMAP_MARGIN
        self.minimap_rect = pygame.Rect(minimap_x, minimap_y, MINIMAP_WIDTH, MINIMAP_HEIGHT)
        pygame.draw.rect(surface, COLORS['MINIMAP_BACKGROUND'], self.minimap_rect, border_radius=6)
        pygame.draw.rect(surface, COLORS['PANEL_BORDER'], self.minimap_rect, 1, border_radius=6)

        points = {coord: HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y) for coord in tiles}
        min_x = min(p[0] for p in points.values())
        max_x = max(p[0] for p in points.values())
        min_y = min(p[1] for p in points.values())
        max_y = max(p[1] for p in points.values())
        map_width, map_height = max(1, max_x - min_x), max(1, max_y - min_y)
        scale = min((MINIMAP_WIDTH - 12) / map_width, (MINIMAP_HEIGHT - 12) / map_height)
        offset_x = minimap_x + (MINIMAP_WIDTH - map_width * scale) / 2
        offset_y = minimap_y + (MINIMAP_HEIGHT - map_height * scale) / 2
        mini_radius = max(2, int(HEX_RADIUS * scale) + 1)
        palette = self._terrain_palette(tiles)
        for coord, tile in tiles.items():
            world_x, world_y = points[coord]
            mini = (int(offset_x + (world_x - min_x) * scale), int(offset_y + (world_y - min_y) * scale))
            if coord in visible_tiles:
                color = palette.get(coord, COLORS['LAND'])
                if tile.owner and tile.terrain_type == TerrainType.LAND:
                    color = self._get_player_color(tile.owner)
                if tile.city:
                    color = COLORS['WHITE']
            elif coord in explored_tiles:
                color = _shade(palette.get(coord, COLORS['LAND']), 0.45)
            else:
                color = (12, 14, 20)
            pygame.draw.polygon(surface, color, HexRenderer.get_hex_corners(*mini, mini_radius))

        left, top, right, bottom = self._get_visible_world_bounds()
        view = pygame.Rect(int(offset_x + (left - min_x) * scale), int(offset_y + (top - min_y) * scale),
                           max(3, int((right - left) * scale)), max(3, int((bottom - top) * scale)))
        pygame.draw.rect(surface, COLORS['MINIMAP_VIEWPORT'], view.clip(self.minimap_rect), 1)
        self._minimap_transform = (offset_x, offset_y, min_x, min_y, scale)

    def minimap_to_world(self, pos: tuple) -> Optional[Tuple[float, float]]:
        """小地图坐标转世界坐标，用于点击小地图跳转视角。"""
        if not self.minimap_rect or not getattr(self, '_minimap_transform', None):
            return None
        offset_x, offset_y, min_x, min_y, scale = self._minimap_transform
        return (pos[0] - offset_x) / scale + min_x, (pos[1] - offset_y) / scale + min_y

    def _get_visible_world_bounds(self) -> Tuple[float, float, float, float]:
        left, top = self.screen_to_world(0, 0)
        right, bottom = self.screen_to_world(self.screen_width, self.screen_height)
        return left, top, right, bottom

    def is_minimap_pos(self, pos: tuple) -> bool:
        return bool(self.minimap_rect and self.minimap_rect.collidepoint(pos))

    def get_tile_at_screen_pos(self, screen_x: int, screen_y: int) -> Optional[HexCoord]:
        world_x, world_y = self.screen_to_world(screen_x, screen_y)
        q, r = HexRenderer.pixel_to_hex(world_x, world_y, OFFSET_X, OFFSET_Y)
        return HexCoord(q, r)
