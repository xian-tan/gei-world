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
        self.input_system.on_mouse_down = self.ui_system.handle_mouse_down
        self.input_system.on_mouse_drag = self.ui_system.handle_mouse_drag
        self.input_system.on_mouse_up = self.ui_system.handle_mouse_up
    
    def _setup_ui_callbacks(self):
        """设置UI系统回调"""
        self.ui_system.set_callbacks(
            on_build_unit=self._handle_build_unit,
            on_end_turn=self._handle_end_turn,
            on_save_game=self._handle_save_game,
            on_load_game=self._handle_load_game,
            on_build_city=self._handle_build_city
        )
    
    def _clear_ui_selection_state(self):
        """清理 UI 选中状态、城市面板和可达高亮。"""
        self.input_system.set_mode(InputMode.NORMAL)
        self.ui_system._close_city_panel()
        self.render_system.selected_tile = None
        self.render_system.clear_selected_unit()
        self.render_system.clear_reachable_tiles()
    
    def _notify(self, message: str):
        """同时输出控制台和界面消息。"""
        print(message)
        self.ui_system.add_message(message)
    
    def _execute_action_and_notify(self, action: GameAction):
        """执行行动并显示引擎返回的结构化结果。"""
        result = self.game_engine.execute_action_with_result(action)
        self._notify_action_result(result)
        return result
    
    def _notify_action_result(self, result, actor_name: str = None):
        """展示结构化行动结果，优先显示战斗/攻城等关键事件。"""
        priority_types = {"combat_resolved", "city_captured", "game_over"}
        has_priority_event = any(event.event_type in priority_types for event in result.events)
        messages = []
        
        if not has_priority_event and result.message:
            messages.append(result.message)
        
        has_combat_summary = False
        for event in result.events:
            if has_priority_event and event.event_type == "unit_moved":
                continue
            message = self._format_action_event(event)
            if not message:
                continue
            if event.event_type == "combat_resolved":
                has_combat_summary = True
            if event.event_type == "unit_destroyed" and has_combat_summary:
                continue
            if message not in messages:
                messages.append(message)
        
        if not messages and result.message:
            messages.append(result.message)
        
        for index, message in enumerate(messages):
            if actor_name and index == 0:
                self._notify(f"{actor_name}: {message}")
            else:
                self._notify(message)
    
    def _format_action_event(self, event) -> Optional[str]:
        """将行动事件格式化为更友好的 UI 文案。"""
        if event.event_type == "combat_resolved":
            destroyed_count = len(event.data.get("destroyed_unit_ids", []))
            return f"战斗结束：消灭 {destroyed_count} 个单位"
        if event.event_type == "unit_destroyed":
            return "单位被消灭"
        if event.event_type == "city_captured":
            return event.message or "城市被占领"
        if event.event_type == "game_over":
            return event.message or "游戏结束"
        if event.event_type == "unit_moved":
            from_terrain = event.data.get("from_terrain")
            to_terrain = event.data.get("to_terrain")
            if from_terrain == "land" and to_terrain == "ocean":
                return "单位下海，移动力已耗尽"
            if from_terrain == "ocean" and to_terrain == "ocean":
                return "单位在海上移动"
            if from_terrain == "ocean" and to_terrain == "land":
                return "单位登陆"
            return "单位移动成功"
        if event.event_type == "city_built":
            return event.message or "城市建立成功"
        if event.event_type == "unit_produced":
            return event.message or "单位生产成功"
        if event.event_type == "turn_ended":
            return event.message or "回合结束"
        return event.message
    
    def start_game(self, player_names: list, map_seed: int = None):
        """开始游戏"""
        new_engine = GameEngine()
        if new_engine.initialize_game(player_names, map_seed):
            self.game_engine = new_engine
            self.game_started = True
            self._clear_ui_selection_state()
            self._setup_ai_players()
            
            # 将摄像机移动到地图中心
            self._center_camera_on_map()
            
            self._notify(f"游戏开始！玩家: {', '.join(player_names)}")
            self._notify("新手提示：左键选中初始移民，黄色边框是可移动范围。")
            self._notify("移动到合适陆地后，按 B 或点击建城按钮建立第一座城市。")
            self._notify("目标：建城、生产士兵，探索并占领对手城市。")
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
            self._notify_action_result(result, current_player.name)
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
        center_x, center_y = HexRenderer.hex_to_pixel(center_q, center_r, OFFSET_X, OFFSET_Y)
        
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
        self.screen.fill(COLORS['MAP_BACKGROUND'] if self.game_started else COLORS['BLACK'])
        
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
            
            self._update_hover_path_preview(visible_tiles)
            self.render_system.render_map(
                self.screen,
                self.game_engine.map_tiles,
                visible_tiles,
                explored_tiles,
                current_player
            )
            
            # 渲染UI
            self.ui_system.render(self.screen, game_state)
            self.render_system.render_minimap(
                self.screen,
                self.game_engine.map_tiles,
                visible_tiles,
                explored_tiles
            )
        else:
            # 显示开始界面
            self._render_start_screen()
        
        pygame.display.flip()
    def _render_start_screen(self):
        """渲染开始界面"""
        title = self.font_manager.render_text("六边形策略游戏", 'large', COLORS['WHITE'])
        title_rect = title.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 120))
        self.screen.blit(title, title_rect)
        
        instructions = [
            "SPACE 新游戏",
            "L 加载游戏",
            "ESC 退出",
        ]
        for index, text in enumerate(instructions):
            instruction = self.font_manager.render_text(text, 'medium', COLORS['WHITE'])
            instruction_rect = instruction.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 55 + index * 34))
            self.screen.blit(instruction, instruction_rect)
        
        if self.ui_system.messages:
            message = self.font_manager.render_text(self.ui_system.messages[-1], 'small', COLORS['LIGHT_GRAY'])
            message_rect = message.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 75))
            self.screen.blit(message, message_rect)
    
    def _update_hover_path_preview(self, visible_tiles: Set[HexCoord]):
        """根据鼠标悬停位置更新移动路径预览。"""
        mouse_pos = self.input_system.mouse_pos
        hovered_coord = self._get_tile_at_screen_pos(mouse_pos[0], mouse_pos[1])
        self.render_system.hovered_tile = hovered_coord
        self.render_system.clear_path_preview()
        if not hovered_coord or hovered_coord not in visible_tiles:
            return
        if not self.input_system.is_unit_selected():
            return
        if hovered_coord not in self.render_system.reachable_tiles:
            return
        unit = self._find_unit_by_id(self.input_system.get_selected_unit_id())
        if not unit or hovered_coord == unit.position:
            return
        path = self.game_engine.unit_system.find_movement_path(
            unit,
            hovered_coord,
            self.game_engine.map_tiles
        )
        if path:
            self.render_system.set_path_preview(path)
    
    def _get_game_state(self) -> Dict[str, Any]:
        """获取游戏状态快照"""
        current_player = self.game_engine.get_current_player()
        selected_coord = self.render_system.selected_tile
        selected_tile = self.game_engine.map_tiles.get(selected_coord) if selected_coord else None
        selected_unit = self._find_unit_by_id(self.input_system.get_selected_unit_id()) if self.input_system.is_unit_selected() else None
        selected_city = self.ui_system.selected_city if self.ui_system.show_city_panel else None
        
        return {
            'current_player': current_player,
            'turn_number': self.game_engine.turn_system.turn_number,
            'game_over': self.game_engine.game_over,
            'winner': self.game_engine.winner,
            'selected_coord': selected_coord,
            'selected_tile': selected_tile,
            'selected_unit': selected_unit,
            'selected_city': selected_city
        }
    
    def _get_tile_at_screen_pos(self, screen_x: int, screen_y: int) -> Optional[HexCoord]:
        """获取屏幕位置对应的地块"""
        world_x, world_y = self.camera_system.screen_to_world(screen_x, screen_y)
        q, r = HexRenderer.pixel_to_hex(world_x, world_y, OFFSET_X, OFFSET_Y)
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
        if self.render_system.is_minimap_pos(screen_pos):
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
        if not self._cycle_selectable_on_tile(tile, current_player):
            self._clear_ui_selection_state()
    
    def _get_selectables_on_tile(self, tile, current_player):
        """获取当前地块上可循环选择的己方对象。"""
        selectables = []
        for unit in tile.units:
            if unit.owner == current_player:
                selectables.append(("unit", unit.id, unit))
        if tile.city and tile.city.owner == current_player:
            selectables.append(("city", tile.city.id, tile.city))
        return selectables
    
    def _get_current_selection_key(self) -> Optional[tuple]:
        """获取当前选中对象标识。"""
        if self.input_system.is_unit_selected():
            return ("unit", self.input_system.get_selected_unit_id())
        if self.input_system.is_city_selected():
            return ("city", self.input_system.get_selected_city_id())
        return None
    
    def _cycle_selectable_on_tile(self, tile, current_player) -> bool:
        """在同一地块的多个单位/城市之间循环选择。"""
        selectables = self._get_selectables_on_tile(tile, current_player)
        if not selectables:
            return False
        
        current_key = self._get_current_selection_key()
        selected_index = 0
        if current_key:
            keys = [(item_type, item_id) for item_type, item_id, _ in selectables]
            if current_key in keys:
                selected_index = (keys.index(current_key) + 1) % len(selectables)
        
        item_type, _, item = selectables[selected_index]
        if item_type == "unit":
            self._select_unit(item)
        else:
            self._select_city(item, current_player)
        return True
    
    def _select_unit(self, unit):
        """选中单位并刷新移动范围。"""
        self.input_system.set_mode(InputMode.UNIT_SELECTED, unit.id)
        self.ui_system._close_city_panel()
        self.render_system.set_selected_unit(unit.id)
        reachable_tiles = self.game_engine.unit_system.get_reachable_tiles(unit, self.game_engine.map_tiles)
        self.render_system.set_reachable_tiles(set(reachable_tiles))
        if unit.unit_type == UnitType.SETTLER:
            self._notify(f"选中移民：移动力 {unit.movement_points}。左键移动，按 B 或点击建城按钮建城。")
        elif unit.unit_type == UnitType.SOLDIER:
            self._notify(f"选中士兵：移动力 {unit.movement_points}。左键移动/攻击，可占领敌方地块和城市。")
        else:
            self._notify(f"选中单位: {unit.unit_type.value} (移动力: {unit.movement_points})")
        if unit.movement_points <= 0:
            self._notify("该单位本回合移动力已用完，请点击结束回合恢复。")
    
    def _select_city(self, city, current_player):
        """选中城市并打开城市面板。"""
        self.input_system.set_mode(InputMode.CITY_SELECTED, city.id)
        self.ui_system.show_city_panel_for(city)
        self.render_system.clear_selected_unit()
        self.render_system.clear_reachable_tiles()
        self._notify(f"选中城市：当前金币 {current_player.gold}。可在城市面板生产移民或士兵。")
    
    def _handle_unit_selected_click(self, tile, current_player):
        """处理选中单位时的点击"""
        unit_id = self.input_system.get_selected_unit_id()
        unit = self._find_unit_by_id(unit_id)
        
        if not unit:
            self.input_system.set_mode(InputMode.NORMAL)
            return
        
        # 点击当前格时，在同格单位/城市之间循环选择
        if tile.coord == unit.position:
            self._cycle_selectable_on_tile(tile, current_player)
            return
        
        moving_units = [unit]
        if unit.unit_type == UnitType.SOLDIER:
            source_tile = self.game_engine.map_tiles.get(unit.position)
            if source_tile:
                same_tile_soldiers = [
                    candidate for candidate in source_tile.units
                    if candidate.owner == current_player
                    and candidate.unit_type == UnitType.SOLDIER
                    and candidate.movement_points > 0
                ]
                same_tile_soldiers.sort(key=lambda candidate: 0 if candidate.id == unit.id else 1)
                moving_units = same_tile_soldiers[:max(1, min(self.ui_system.move_soldier_quantity, len(same_tile_soldiers)))]
        
        for moving_unit in moving_units:
            move_failure = self.game_engine.unit_system.get_move_failure_reason(moving_unit, tile.coord, self.game_engine.map_tiles)
            if move_failure:
                self._notify(move_failure)
                return
        
        # 移动单位到目标地块
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.MOVE_UNIT,
            params={
                'unit_id': unit_id,
                'unit_ids': [moving_unit.id for moving_unit in moving_units],
                'target': [tile.coord.q, tile.coord.r]
            }
        )
        
        result = self._execute_action_and_notify(action)
        if result.success:
            if len(moving_units) > 1:
                self._notify(f"已移动 {len(moving_units)} 名士兵")
            unit = self._find_unit_by_id(unit_id)
            if unit:
                if unit.movement_points <= 0:
                    self._notify("移动力已耗尽，已取消选中。")
                    self._clear_ui_selection_state()
                else:
                    reachable_tiles = self.game_engine.unit_system.get_reachable_tiles(unit, self.game_engine.map_tiles)
                    self.render_system.set_reachable_tiles(set(reachable_tiles))
            else:
                self._clear_ui_selection_state()
    
    def _handle_city_selected_click(self, tile, current_player):
        """处理选中城市时的点击"""
        # 点击当前城市所在格时，在同格单位/城市之间循环选择
        if tile.city == self.ui_system.selected_city:
            self._cycle_selectable_on_tile(tile, current_player)
            return
        
        self.ui_system._close_city_panel()
        self.input_system.set_mode(InputMode.NORMAL)
        
        # 如果点击了其他对象，递归处理
        self._handle_normal_click(tile, current_player)
    
    def _handle_tile_right_click(self, screen_pos):
        """处理右键：取消当前选择。"""
        if self.input_system.mode != InputMode.NORMAL or self.ui_system.show_city_panel or self.render_system.selected_tile:
            self._clear_ui_selection_state()
            self._notify("已取消选择")
    
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
        
        if key == pygame.K_ESCAPE:
            if not self.game_started or self.game_engine.game_over:
                self.running = False
            elif self.input_system.mode != InputMode.NORMAL:
                self._clear_ui_selection_state()
            else:
                self.running = False
            return
        
        if not self.game_started:
            if key == pygame.K_SPACE:
                self.start_game(["玩家1", "AI玩家"])
            elif key == pygame.K_l:
                self._handle_load_game()
            return
        
        if self.game_engine.game_over:
            if key == pygame.K_r:
                self.start_game(["玩家1", "AI玩家"])
            return
        
        if key == pygame.K_b:
            self._handle_build_city()
            return
    
    def _handle_build_city(self):
        """处理移民建城。"""
        unit_id = self.input_system.get_selected_unit_id()
        unit = self._find_unit_by_id(unit_id) if unit_id else None
        current_player = self.game_engine.get_current_player()
        if not unit:
            self._notify("请先选中一个移民，再建城。")
            return
        if unit.owner != current_player:
            self._notify("只能使用自己的移民建城。")
            return
        if unit.unit_type != UnitType.SETTLER:
            self._notify("只有移民可以建城。")
            return
        
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.BUILD_CITY,
            params={'unit_id': unit_id}
        )
        result = self._execute_action_and_notify(action)
        if result.success:
            self._clear_ui_selection_state()
    
    def _handle_build_unit(self, city_id: str, unit_type: UnitType, quantity: int = 1):
        """处理建造单位。"""
        current_player = self.game_engine.get_current_player()
        quantity = 1 if unit_type == UnitType.SETTLER else max(1, quantity)
        success_count = 0
        last_result = None
        for _ in range(quantity):
            action = GameAction(
                player_id=current_player.id,
                action_type=ActionType.BUILD_UNIT,
                params={'city_id': city_id, 'unit_type': unit_type.value}
            )
            result = self.game_engine.execute_action_with_result(action)
            last_result = result
            if not result.success:
                break
            success_count += 1
        
        if success_count > 1 and unit_type == UnitType.SOLDIER:
            self._notify(f"生产士兵 {success_count} 名")
        elif last_result:
            self._notify_action_result(last_result)
    
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
            self._clear_ui_selection_state()
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
            self._clear_ui_selection_state()
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
