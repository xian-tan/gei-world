"""
六边形几何、坐标转换与屏幕拾取一致性测试。
"""
import math

import pygame

from src.models import HexCoord
from ui.hex_renderer import HexRenderer
from ui.systems.camera_system import CameraSystem
from ui.systems.render_system import RenderSystem
from ui.ui_config import HEX_RADIUS, OFFSET_X, OFFSET_Y, SCREEN_HEIGHT, SCREEN_WIDTH


def test_hex_distance_and_neighbors():
    origin = HexCoord(0, 0)
    assert origin.distance_to(HexCoord(1, 0)) == 1
    assert origin.distance_to(HexCoord(2, -1)) == 2
    assert len(origin.neighbors()) == 6
    assert all(origin.distance_to(n) == 1 for n in origin.neighbors())


def test_within_returns_hexagonal_area():
    for radius in range(0, 5):
        coords = HexCoord(3, -2).within(radius)
        assert len(coords) == 3 * radius * (radius + 1) + 1
        assert all(HexCoord(3, -2).distance_to(c) <= radius for c in coords)


def test_neighbor_centers_are_equidistant():
    center = HexRenderer.hex_to_pixel(0, 0)
    expected = HEX_RADIUS * math.sqrt(3)
    for neighbor in HexCoord(0, 0).neighbors():
        x, y = HexRenderer.hex_to_pixel(neighbor.q, neighbor.r)
        assert abs(math.hypot(x - center[0], y - center[1]) - expected) < 2


def test_pixel_round_trip_with_and_without_offset():
    for q, r in [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, -1), (-1, 1), (2, -3), (-4, 5)]:
        assert HexRenderer.pixel_to_hex(*HexRenderer.hex_to_pixel(q, r)) == (q, r)
        x, y = HexRenderer.hex_to_pixel(q, r, OFFSET_X, OFFSET_Y)
        assert HexRenderer.pixel_to_hex(x, y, OFFSET_X, OFFSET_Y) == (q, r)


def test_render_and_camera_share_coordinate_system():
    camera = CameraSystem(SCREEN_WIDTH, SCREEN_HEIGHT)
    render = RenderSystem()
    points = [HexRenderer.hex_to_pixel(q, r, OFFSET_X, OFFSET_Y) for q, r in [(0, 0), (1, 0), (-2, 3)]]
    for camera_x, camera_y, zoom in [(0, 0, 1.0), (120, -80, 0.75), (320, 240, 1.6)]:
        camera.set_position(camera_x, camera_y)
        camera.zoom = zoom
        render.camera_x, render.camera_y = camera.get_position()
        render.zoom = camera.get_zoom()
        for world_x, world_y in points:
            assert render.world_to_screen(world_x, world_y) == camera.world_to_screen(world_x, world_y)


def test_screen_click_picks_rendered_tile():
    from ui.client_controller import UIClient

    pygame.init()
    client = UIClient()
    assert client.start_game(["测试玩家1", "测试玩家2"], 12345)
    assert client._get_game_state()["current_player"] is not None
    sample = list(client.game_engine.map_tiles.keys())[:8]
    for zoom in (1.0, 1.7):
        client.camera_system.zoom = zoom
        for coord in sample:
            world = HexRenderer.hex_to_pixel(coord.q, coord.r, OFFSET_X, OFFSET_Y)
            screen = client.camera_system.world_to_screen(*world)
            assert client._get_tile_at_screen_pos(*screen) == coord
