"""
地图交互：选择、移动、建城、生产与路径预览。
"""
from typing import Optional, Set

import pygame

from src.models import ActionType, GameAction, HexCoord, UnitType
from ui.hex_renderer import HexRenderer
from ui.systems.input_system import InputMode
from ui.ui_config import OFFSET_X, OFFSET_Y


class SelectionMixin:
    """地图交互：选择、移动、建城、生产与路径预览。"""

    def _clear_ui_selection_state(self):
        """清理 UI 选中状态、城市面板和可达高亮。"""
        self.move_mode_active = False
        self.input_system.set_mode(InputMode.NORMAL)
        self.ui_system._close_city_panel()
        self.render_system.selected_tile = None
        self.render_system.clear_selected_unit()
        self.render_system.clear_reachable_tiles()
        self.render_system.clear_attention_tiles()
        self.render_system.clear_selected_city_economic_tiles()

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
            if self._has_cancelable_ui_state():
                self._clear_ui_selection_state()
            return
        
        tile = self.game_engine.map_tiles.get(coord)
        if not tile:
            return
        
        current_player = self._get_controlled_player()
        
        # 根据当前模式处理点击；左键只负责选择/切换，空地取消选中
        if self.input_system.mode == InputMode.NORMAL:
            self._handle_normal_click(tile, current_player)
        elif self.input_system.mode == InputMode.UNIT_SELECTED:
            self._handle_unit_selected_click(tile, current_player)
        elif self.input_system.mode == InputMode.CITY_SELECTED:
            self._handle_city_selected_click(tile, current_player)
        
        if self.input_system.mode != InputMode.NORMAL or self.ui_system.show_city_panel or self.render_system.selected_unit_id:
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
        """选中单位并刷新右键移动范围。"""
        self.move_mode_active = False
        self.input_system.set_mode(InputMode.UNIT_SELECTED, unit.id)
        self.ui_system._close_city_panel()
        self.render_system.set_selected_unit(unit.id)
        self.render_system.clear_attention_tiles()
        self.render_system.clear_path_preview()
        self.render_system.clear_selected_city_economic_tiles()
        reachable_tiles = self.game_engine.unit_system.get_reachable_tiles(unit, self.game_engine.map_tiles)
        self.render_system.set_reachable_tiles(set(reachable_tiles))
        if unit.unit_type == UnitType.SETTLER:
            self._notify(f"选中移民：移动力 {unit.movement_points}。右键移动，按 B 或点击建城按钮建城。")
        elif unit.unit_type == UnitType.SOLDIER:
            self._notify(f"选中士兵：{unit.quantity} 名，移动力 {unit.movement_points}。右键移动/攻击，按 M 全选，按 1-9 设置移动人数。")
        else:
            self._notify(f"选中单位: {unit.unit_type.value} (移动力: {unit.movement_points})，右键移动。")
        if unit.movement_points <= 0:
            self._notify("该单位本回合移动力已用完，请点击结束回合恢复。")

    def _select_city(self, city, current_player):
        """选中城市并打开城市面板。"""
        self.move_mode_active = False
        self.input_system.set_mode(InputMode.CITY_SELECTED, city.id)
        self.ui_system.show_city_panel_for(city)
        self.render_system.selected_tile = city.center_tile
        self.render_system.clear_selected_unit()
        self.render_system.clear_reachable_tiles()
        self.render_system.clear_attention_tiles()
        economic_tiles = self.game_engine.city_system.get_city_economic_tiles(city, self.game_engine.map_tiles)
        self.render_system.set_selected_city_economic_tiles(economic_tiles)
        self._notify(f"选中城市：当前金币 {current_player.gold}。可在城市面板生产移民或士兵。")

    def _handle_unit_selected_click(self, tile, current_player):
        """处理选中单位时的左键选择。"""
        if not self._cycle_selectable_on_tile(tile, current_player):
            self._clear_ui_selection_state()

    def _handle_unit_move_click(self, tile, current_player):
        """处理移动模式下的单位移动点击。"""
        unit_id = self.input_system.get_selected_unit_id()
        unit = self._find_unit_by_id(unit_id)
        
        if not unit:
            self._clear_ui_selection_state()
            return
        
        if tile.coord == unit.position:
            self._notify("已在当前位置，选择黄色范围内的目标地块移动。")
            return
        
        move_quantity = 1
        if unit.unit_type == UnitType.SOLDIER:
            move_quantity = max(1, min(self.ui_system.move_soldier_quantity, unit.quantity))
        
        move_failure = self.game_engine.unit_system.get_move_failure_reason(unit, tile.coord, self.game_engine.map_tiles)
        if move_failure:
            self._notify(move_failure)
            return
        
        self.render_system.clear_attention_tiles()
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.MOVE_UNIT,
            params={
                'unit_id': unit_id,
                'move_quantity': move_quantity,
                'target': [tile.coord.q, tile.coord.r]
            }
        )
        
        result = self._execute_action_and_notify(action)
        if result.success:
            moved_unit_id = action.params.get('unit_id', unit_id)
            if move_quantity > 1 and unit.unit_type == UnitType.SOLDIER:
                self._notify(f"已移动 {move_quantity} 名士兵")
            unit = self._find_unit_by_id(moved_unit_id)
            if unit:
                self.input_system.set_mode(InputMode.UNIT_SELECTED, unit.id)
                self.render_system.set_selected_unit(unit.id)
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
        """处理右键：选中单位时移动。"""
        if self.ui_system.has_active_modal():
            self.ui_system.close_modal()
            return
        coord = self._get_tile_at_screen_pos(screen_pos[0], screen_pos[1])
        if not coord:
            return
        tile = self.game_engine.map_tiles.get(coord)
        current_player = self._get_controlled_player()
        if tile and self.input_system.is_unit_selected():
            self._handle_unit_move_click(tile, current_player)

    def _has_cancelable_ui_state(self) -> bool:
        """是否存在可先取消的 UI 状态。"""
        return bool(
            self.input_system.mode != InputMode.NORMAL
            or self.ui_system.show_city_panel
            or self.render_system.selected_tile
            or self.render_system.selected_unit_id
            or self.render_system.reachable_tiles
            or self.render_system.selected_city_economic_tiles
            or self.render_system.path_preview
            or self.move_mode_active
        )

    def _handle_soldier_quantity_hotkey(self, key: int) -> bool:
        """处理选中士兵时的移动数量快捷键。"""
        if not self.input_system.is_unit_selected():
            return False
        unit = self._find_unit_by_id(self.input_system.get_selected_unit_id())
        current_player = self._get_controlled_player()
        if not unit or not current_player:
            return False
        if unit.owner != current_player or unit.unit_type != UnitType.SOLDIER:
            return False
        
        quantity_by_key = {
            pygame.K_1: 1,
            pygame.K_2: 2,
            pygame.K_3: 3,
            pygame.K_4: 4,
            pygame.K_5: 5,
            pygame.K_6: 6,
            pygame.K_7: 7,
            pygame.K_8: 8,
            pygame.K_9: 9,
            pygame.K_KP1: 1,
            pygame.K_KP2: 2,
            pygame.K_KP3: 3,
            pygame.K_KP4: 4,
            pygame.K_KP5: 5,
            pygame.K_KP6: 6,
            pygame.K_KP7: 7,
            pygame.K_KP8: 8,
            pygame.K_KP9: 9,
        }
        max_quantity = max(1, unit.quantity)
        if key == pygame.K_m:
            quantity = max_quantity
        elif key in quantity_by_key:
            quantity = min(quantity_by_key[key], max_quantity)
        else:
            return False
        
        self.ui_system.move_soldier_quantity = quantity
        self._notify(f"移动士兵数量已设为 {quantity}/{max_quantity}")
        return True

    def _handle_build_city(self):
        """处理移民建城。"""
        unit_id = self.input_system.get_selected_unit_id()
        unit = self._find_unit_by_id(unit_id) if unit_id else None
        current_player = self._get_controlled_player()
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
        current_player = self._get_controlled_player()
        if not current_player:
            return
        quantity = 1 if unit_type == UnitType.SETTLER else max(1, quantity)
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.BUILD_UNIT,
            params={
                'city_id': city_id,
                'unit_type': unit_type.value,
                'quantity': quantity
            }
        )
        result = self.session.submit_action(action)
        if result.success and quantity > 1 and unit_type == UnitType.SOLDIER:
            self._notify(f"生产士兵 {quantity} 名")
        else:
            self._notify_action_result(result)

    def _find_unit_by_id(self, unit_id: str):
        """根据ID查找单位"""
        for player in self.game_engine.player_system.players:
            for unit in player.units:
                if unit.id == unit_id:
                    return unit
        return None

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
