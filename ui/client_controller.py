"""
UI客户端控制器 - UI与GameEngine的桥接
"""
import pygame
import sys
import os
from typing import Dict, Any, Optional, Set

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.game_engine import GameEngine
from src.models import GameAction, ActionType, HexCoord, UnitType, Player
from src.systems.ai_system import AIManager
from src.systems.save_system import GameSaveSystem
from ui.systems.render_system import RenderSystem
from ui.systems.input_system import InputSystem, InputMode
from ui.systems.ui_system import UISystem
from ui.systems.camera_system import CameraSystem
from ui.hex_renderer import HexRenderer
from ui.ui_config import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT, FPS, OFFSET_X, OFFSET_Y
from ui.font_manager import get_font_manager


class UIClient:
    """UI客户端 - 连接UI和游戏引擎"""
    
    def __init__(self):
        # 初始化pygame
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("六边形策略游戏")
        self.clock = pygame.time.Clock()
        
        # 游戏引擎
        self.game_engine = GameEngine()
        self.ai_manager = AIManager()
        self.save_system = GameSaveSystem()
        
        # UI系统
        self.render_system = RenderSystem()
        self.input_system = InputSystem()
        self.ui_system = UISystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.camera_system = CameraSystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        
        # 状态
        self.running = True
        self.game_started = False
        
        # 设置输入回调
        self._setup_input_callbacks()
        
        # 设置UI回调
        self._setup_ui_callbacks()        # 字体管理器
        self.font_manager = get_font_manager()
    
    def _setup_input_callbacks(self):
        """设置输入系统回调"""
        self.input_system.on_tile_clicked = self._handle_tile_click
        self.input_system.on_tile_right_clicked = self._handle_tile_right_click
        self.input_system.on_camera_move = self._handle_camera_move
        self.input_system.on_zoom = self._handle_zoom
        self.input_system.on_key_pressed = self._handle_key_press
    
    def _setup_ui_callbacks(self):
        """设置UI系统回调"""
        self.ui_system.set_callbacks(
            on_build_unit=self._handle_build_unit,
            on_end_turn=self._handle_end_turn,
            on_save_game=self._handle_save_game,
            on_load_game=self._handle_load_game
        )
    
    def _notify(self, message: str):
        """同时输出控制台和界面消息。"""
        print(message)
        self.ui_system.add_message(message)
    
    def _execute_action_and_notify(self, action: GameAction):
        """执行行动并显示引擎返回的结构化结果。"""
        result = self.game_engine.execute_action_with_result(action)
        self._notify(result.message)
        for event in result.events:
            if event.message and event.message != result.message:
                self._notify(event.message)
        return result
    
    def start_game(self, player_names: list, map_seed: int = None):
        """开始游戏"""
        if self.game_engine.initialize_game(player_names, map_seed):
            self.game_started = True
            self._setup_ai_players()
            
            # 将摄像机移动到地图中心
            self._center_camera_on_map()
            
            self._notify(f"游戏开始！玩家: {', '.join(player_names)}")
            return True
        return False
    
    def _setup_ai_players(self):
        """将第一个玩家之外的玩家设为 AI。"""
        self.ai_manager = AIManager()
        self.game_engine.ai_player_configs = {}
        for player in self.game_engine.player_system.players[1:]:
            self.ai_manager.add_ai_player(player, "simple", "easy")
            self.game_engine.ai_player_configs[player.id] = {
                "ai_type": "simple",
                "difficulty": "easy"
            }
    
    def _restore_ai_players_from_engine(self):
        """根据引擎中的 AI 配置重建 AI 管理器。"""
        self.ai_manager = AIManager()
        for player_id, config in getattr(self.game_engine, 'ai_player_configs', {}).items():
            player = self.game_engine.player_system.get_player_by_id(player_id)
            if player:
                self.ai_manager.add_ai_player(
                    player,
                    config.get("ai_type", "simple"),
                    config.get("difficulty", "easy")
                )
    
    def _process_ai_turns(self):
        """自动处理连续 AI 回合，直到轮回人类玩家或游戏结束。"""
        safety_limit = 30
        actions_taken = 0
        while not self.game_engine.game_over and actions_taken < safety_limit:
            current_player = self.game_engine.get_current_player()
            if not current_player or not self.ai_manager.is_ai_player(current_player.id):
                break
            
            action = self.ai_manager.get_ai_action(current_player.id, self.game_engine)
            if not action:
                action = GameAction(
                    player_id=current_player.id,
                    action_type=ActionType.END_TURN,
                    params={}
                )
            
            result = self.game_engine.execute_action_with_result(action)
            actions_taken += 1
            if result.message:
                self._notify(f"{current_player.name}: {result.message}")
            for event in result.events:
                if event.message and event.message != result.message:
                    self._notify(event.message)
            if not result.success and action.action_type != ActionType.END_TURN:
                self.game_engine.execute_action(GameAction(
                    player_id=current_player.id,
                    action_type=ActionType.END_TURN,
                    params={}
                ))
                actions_taken += 1
            
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
        center_x, center_y = HexRenderer.hex_to_pixel(center_q, center_r)
        
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
        self.screen.fill(COLORS['BLACK'])
        
        if self.game_started:
            # 获取游戏状态
            game_state = self._get_game_state()
            
            # 更新渲染系统摄像机
            self.render_system.camera_x, self.render_system.camera_y = self.camera_system.get_position()
            self.render_system.zoom = self.camera_system.get_zoom()
            
            # 渲染地图
            current_player = self.game_engine.get_current_player()
            visible_tiles = self.game_engine.vision_system.get_visible_tiles(current_player.id)
            explored_tiles = self.game_engine.vision_system.get_explored_tiles(current_player.id)
            
            self.render_system.render_map(
                self.screen,
                self.game_engine.map_tiles,
                visible_tiles,
                explored_tiles,
                current_player
            )
            
            # 更新悬停地块
            mouse_pos = self.input_system.mouse_pos
            hovered_coord = self._get_tile_at_screen_pos(mouse_pos[0], mouse_pos[1])
            self.render_system.hovered_tile = hovered_coord
            
            # 渲染UI
            self.ui_system.render(self.screen, game_state)
        else:
            # 显示开始界面
            self._render_start_screen()
        
        pygame.display.flip()
    def _render_start_screen(self):
        """渲染开始界面"""
        title = self.font_manager.render_text("六边形策略游戏", 'large', COLORS['WHITE'])
        title_rect = title.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 100))
        self.screen.blit(title, title_rect)
        
        instruction = self.font_manager.render_text("按 SPACE 开始游戏", 'medium', COLORS['WHITE'])
        instruction_rect = instruction.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50))
        self.screen.blit(instruction, instruction_rect)
    
    def _get_game_state(self) -> Dict[str, Any]:
        """获取游戏状态快照"""
        current_player = self.game_engine.get_current_player()
        return {
            'current_player': current_player,
            'turn_number': self.game_engine.turn_system.turn_number,
            'game_over': self.game_engine.game_over,
            'winner': self.game_engine.winner
        }
    
    def _get_tile_at_screen_pos(self, screen_x: int, screen_y: int) -> Optional[HexCoord]:
        """获取屏幕位置对应的地块"""
        world_x, world_y = self.camera_system.screen_to_world(screen_x, screen_y)
        world_x += OFFSET_X
        world_y += OFFSET_Y
        q, r = HexRenderer.pixel_to_hex(world_x, world_y)
        coord = HexCoord(q, r)
        
        # 检查坐标是否在地图范围内
        if coord in self.game_engine.map_tiles:
            return coord
        return None
    
    def _handle_tile_click(self, screen_pos):
        """处理地块点击"""
        # 先检查UI是否处理了点击
        if self.ui_system.handle_click(screen_pos):
            return
        
        coord = self._get_tile_at_screen_pos(screen_pos[0], screen_pos[1])
        if not coord:
            return
        
        tile = self.game_engine.map_tiles.get(coord)
        if not tile:
            return
        
        current_player = self.game_engine.get_current_player()
        
        # 根据当前模式处理点击
        if self.input_system.mode == InputMode.NORMAL:
            self._handle_normal_click(tile, current_player)
        elif self.input_system.mode == InputMode.UNIT_SELECTED:
            self._handle_unit_selected_click(tile, current_player)
        elif self.input_system.mode == InputMode.CITY_SELECTED:
            self._handle_city_selected_click(tile, current_player)
        
        # 更新选中地块
        self.render_system.selected_tile = coord
    def _handle_normal_click(self, tile, current_player):
        """处理普通模式点击"""
        # 检查是否点击了自己的单位
        player_units = [unit for unit in tile.units if unit.owner == current_player]
        if player_units:
            unit = player_units[0]  # 选择第一个单位
            self.input_system.set_mode(InputMode.UNIT_SELECTED, unit.id)
            self.render_system.set_selected_unit(unit.id)
            self._notify(f"选中单位: {unit.unit_type.value} (移动力: {unit.movement_points})")
        
        # 检查是否点击了自己的城市
        elif tile.city and tile.city.owner == current_player:
            self.input_system.set_mode(InputMode.CITY_SELECTED, tile.city.id)
            self.ui_system.show_city_panel_for(tile.city)
            self.render_system.clear_selected_unit()
            self._notify("选中城市")
        
        else:
            # 取消选择
            self.input_system.set_mode(InputMode.NORMAL)
            self.ui_system._close_city_panel()
            self.render_system.clear_selected_unit()
    def _handle_unit_selected_click(self, tile, current_player):
        """处理选中单位时的点击"""
        unit_id = self.input_system.get_selected_unit_id()
        unit = self._find_unit_by_id(unit_id)
        
        if not unit:
            self.input_system.set_mode(InputMode.NORMAL)
            return
        
        # 检查是否点击了同一个位置
        if tile.coord == unit.position:
            self._notify("单位已在该位置")
            return
        
        # 检查移动距离
        distance = unit.position.distance_to(tile.coord)
        if distance > unit.movement_points:
            self._notify(f"移动距离({distance})超过移动力({unit.movement_points})")
            return
        
        # 移动单位到目标地块
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.MOVE_UNIT,
            params={'unit_id': unit_id, 'target': [tile.coord.q, tile.coord.r]}
        )
        
        result = self._execute_action_and_notify(action)
        if result.success:
            self._notify(f"单位移动到 ({tile.coord.q}, {tile.coord.r})")
        
        # 保持单位选中状态，允许连续移动
    
    def _handle_city_selected_click(self, tile, current_player):
        """处理选中城市时的点击"""
        # 点击其他地方关闭城市面板
        if tile.city != self.ui_system.selected_city:
            self.ui_system._close_city_panel()
            self.input_system.set_mode(InputMode.NORMAL)
            
            # 如果点击了其他对象，递归处理
            self._handle_normal_click(tile, current_player)
    
    def _handle_tile_right_click(self, screen_pos):
        """处理地块右键点击"""
        coord = self._get_tile_at_screen_pos(screen_pos[0], screen_pos[1])
        if not coord:
            return
        
        tile = self.game_engine.map_tiles.get(coord)
        if not tile:
            return
        
        current_player = self.game_engine.get_current_player()
          # 如果选中了移民，右键建城
        if self.input_system.is_unit_selected():
            unit_id = self.input_system.get_selected_unit_id()
            unit = self._find_unit_by_id(unit_id)
            
            if not unit:
                self._notify("未找到选中的单位")
                return
                
            if unit.unit_type != UnitType.SETTLER:
                self._notify(f"只有移民可以建城，当前单位类型: {unit.unit_type.value}")
                return
            
            # 检查单位是否在目标位置
            if unit.position != coord:
                self._notify(f"移民不在目标位置。移民位置: ({unit.position.q}, {unit.position.r}), 点击位置: ({coord.q}, {coord.r})")
                return
                
            action = GameAction(
                player_id=current_player.id,
                action_type=ActionType.BUILD_CITY,
                params={'unit_id': unit_id}
            )
            
            self._notify(f"尝试在 ({coord.q}, {coord.r}) 建立城市...")
            result = self._execute_action_and_notify(action)
            if result.success:
                self.input_system.set_mode(InputMode.NORMAL)
                self.render_system.clear_selected_unit()
    
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
        
        if key == pygame.K_SPACE and not self.game_started:
            # 开始游戏
            self.start_game(["玩家1", "AI玩家"])
        
        elif key == pygame.K_ESCAPE:
            # 取消选择或退出
            if self.input_system.mode != InputMode.NORMAL:
                self.input_system.set_mode(InputMode.NORMAL)
                self.ui_system._close_city_panel()
            else:
                self.running = False
    
    def _handle_build_unit(self, city_id: str, unit_type: UnitType):
        """处理建造单位"""
        current_player = self.game_engine.get_current_player()
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.BUILD_UNIT,
            params={'city_id': city_id, 'unit_type': unit_type.value}
        )
        
        self._execute_action_and_notify(action)
    
    def _handle_end_turn(self):
        """处理结束回合"""
        current_player = self.game_engine.get_current_player()
        
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.END_TURN,
            params={}
        )
        
        result = self._execute_action_and_notify(action)
        if result.success:
            # 清除选择状态
            self.input_system.set_mode(InputMode.NORMAL)
            self.ui_system._close_city_panel()
            self._process_ai_turns()
    
    def _handle_save_game(self):
        """处理保存游戏"""
        try:
            save_name = "ui_save"
            success = self.save_system.save_game(self.game_engine, save_name)
            if success:
                self._notify(f"游戏已保存到 {save_name}.json")
            else:
                self._notify("保存失败")
        except Exception as e:
            self._notify(f"保存游戏时出错: {e}")
    
    def _handle_load_game(self):
        """处理加载游戏。"""
        try:
            save_name = "ui_save"
            loaded_engine = self.save_system.load_game(save_name)
            if not loaded_engine:
                self._notify(f"加载失败：未找到 {save_name}.json")
                return
            
            self.game_engine = loaded_engine
            self.game_started = True
            self._restore_ai_players_from_engine()
            self.input_system.set_mode(InputMode.NORMAL)
            self.ui_system._close_city_panel()
            self.render_system.clear_selected_unit()
            self._center_camera_on_map()
            self._notify(f"已加载 {save_name}.json")
            self._process_ai_turns()
        except Exception as e:
            self._notify(f"加载游戏时出错: {e}")
    
    def _find_unit_by_id(self, unit_id: str):
        """根据ID查找单位"""
        for player in self.game_engine.player_system.players:
            for unit in player.units:
                if unit.id == unit_id:
                    return unit
        return None
