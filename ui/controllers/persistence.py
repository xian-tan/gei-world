"""
存档：保存槽位、读档列表与读档恢复。
"""
from typing import Any, Dict


from src.game_session import LocalGameSession
from ui.ui_config import COLORS


class PersistenceMixin:
    """存档：保存槽位、读档列表与读档恢复。"""

    def _format_save_summary(self, save_info: Dict[str, Any]) -> str:
        """格式化存档列表项。"""
        timestamp = str(save_info.get('timestamp', '未知'))[:16].replace('T', ' ')
        return f"{save_info.get('name', '未知')} | 回合 {save_info.get('turn', 0)} | {timestamp}"

    def _handle_save_game(self, save_name: str = None):
        """处理保存游戏。无存档名时打开多存档槽位面板。"""
        if save_name is None:
            self._show_save_slots_modal()
            return
        try:
            success = self.save_system.save_game(self.game_engine, save_name)
            self.ui_system.close_modal()
            if success:
                self._notify(f"游戏已保存到 {save_name}.json")
            else:
                self._notify("保存失败")
        except Exception as e:
            self._notify(f"保存游戏时出错: {e}")

    def _show_save_slots_modal(self):
        """显示固定多存档槽位。"""
        saves_by_name = {save['name']: save for save in self.save_system.list_saves()}
        actions = []
        for index, save_name in enumerate(self.save_slots, start=1):
            existing = saves_by_name.get(save_name)
            label = f"保存槽 {index}：空"
            if existing:
                label = f"覆盖槽 {index}：{self._format_save_summary(existing)}"
            actions.append({
                'text': label,
                'callback': lambda name=save_name: self._handle_save_game(name),
                'color': COLORS['BLUE'],
                'text_color': COLORS['WHITE']
            })
        actions.append({
            'text': "取消",
            'callback': self.ui_system.close_modal,
            'color': COLORS['LIGHT_GRAY'],
            'text_color': COLORS['BLACK']
        })
        self.ui_system.show_modal("保存游戏", ["选择一个槽位保存；已有存档会被覆盖。"], actions)

    def _handle_load_game(self, save_name: str = None):
        """处理加载游戏。无存档名时打开存档列表。"""
        if save_name is None:
            self._show_load_saves_modal()
            return
        self._load_save(save_name)

    def _show_load_saves_modal(self):
        """显示可加载存档列表。"""
        saves = self.save_system.list_saves()
        if not saves:
            self.ui_system.show_modal(
                "加载游戏",
                ["没有找到任何存档。"],
                [{
                    'text': "关闭",
                    'callback': self.ui_system.close_modal,
                    'color': COLORS['LIGHT_GRAY'],
                    'text_color': COLORS['BLACK']
                }]
            )
            return
        actions = []
        for save in saves[:8]:
            save_name = save['name']
            actions.append({
                'text': self._format_save_summary(save),
                'callback': lambda name=save_name: self._load_save(name),
                'color': COLORS['ORANGE'],
                'text_color': COLORS['BLACK']
            })
        actions.append({
            'text': "取消",
            'callback': self.ui_system.close_modal,
            'color': COLORS['LIGHT_GRAY'],
            'text_color': COLORS['BLACK']
        })
        self.ui_system.show_modal("加载游戏", ["选择要读取的存档。"], actions)

    def _load_save(self, save_name: str):
        """按名称读取指定存档。"""
        try:
            loaded_engine = self.save_system.load_game(save_name)
            if not loaded_engine:
                self._notify(f"加载失败：未找到 {save_name}.json")
                return
            
            self.session = LocalGameSession(loaded_engine)
            self._clear_multiplayer_context()
            self.game_started = True
            if not self.game_engine.player_system.get_player_by_id(self.local_player_id):
                self.local_player_id = self.game_engine.player_system.players[0].id if self.game_engine.player_system.players else None
            self._restore_ai_players_from_engine()
            self._clear_ui_selection_state()
            self.ui_system.close_modal()
            self._center_camera_on_map()
            self._notify(f"已加载 {save_name}.json")
            self._process_ai_turns()
        except Exception as e:
            self._notify(f"加载游戏时出错: {e}")
