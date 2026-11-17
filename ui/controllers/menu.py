"""
主菜单与新游戏设置。
"""
import os
from typing import Any, Dict, List

from ui.ui_config import COLORS

PLAYER_COUNT_OPTIONS = [(2, "2 名玩家"), (3, "3 名玩家"), (4, "4 名玩家")]
HUMAN_COUNT_OPTIONS = [(1, "1 人 + 电脑"), (2, "2 人热座"), (3, "3 人热座"), (4, "4 人热座")]
DIFFICULTY_OPTIONS = [("easy", "简单"), ("normal", "普通"), ("hard", "困难")]
TURN_MODE_OPTIONS = [("sequential", "轮流回合"), ("simultaneous", "同时回合")]
MAP_TYPE_OPTIONS = [("continents", "大陆"), ("pangaea", "盘古大陆"), ("islands", "群岛")]
MAP_SIZE_OPTIONS = [("small", "小（半径 8）"), ("medium", "中（半径 10）"), ("large", "大（半径 14）")]


def is_dev_mode() -> bool:
    """开发模式：显示调试入口（本机双客户端房间、HTTP 调试房）。"""
    return os.environ.get("GEI_WORLD_DEV") == "1"


class MenuMixin:
    """主菜单与新游戏设置。"""

    def _main_menu_actions(self) -> List[Dict[str, Any]]:
        actions = [
            {'text': "开始新游戏", 'callback': self._show_new_game_modal, 'color': COLORS['SUCCESS']},
            {'text': "多人联机", 'callback': self._show_http_multiplayer_modal, 'color': COLORS['ACCENT']},
            {'text': "读取存档", 'callback': self._handle_load_game},
        ]
        if is_dev_mode():
            actions.append({'text': "本机双客户端（调试）", 'callback': self._show_local_multiplayer_modal})
        actions.append({'text': "退出游戏", 'callback': self._show_exit_confirmation, 'color': COLORS['DANGER']})
        return actions

    def _render_start_screen(self):
        """渲染按钮式主菜单。"""
        info = []
        if self.ui_system.messages:
            info.append(self.ui_system.messages[-1])
        if self.last_http_room_info.get("room_id"):
            info.append(f"最近房间：{self.last_http_room_info['room_id']}（多人联机中可直接重新连接）")
        info.append("快捷键：N 新游戏 · H 多人联机 · L 读取存档 · ESC 退出")
        self.ui_system.render_main_menu(self.screen, self._main_menu_actions(), info)

    def _show_new_game_modal(self):
        """新游戏设置：玩家数、热座人数、电脑难度、回合模式、地图类型/尺寸、种子。"""
        last = getattr(self, "last_game_settings", None) or {}
        self.ui_system.show_modal(
            "新游戏",
            ["←/→ 或点击切换选项，TAB 切换输入框，种子留空为随机。"],
            [
                {'text': "开始游戏", 'callback': self._start_from_new_game_form, 'color': COLORS['SUCCESS']},
                {'text': "取消", 'callback': self.ui_system.close_modal},
            ],
            inputs=[
                {"key": "players", "label": "玩家数", "value": last.get("players", 2), "options": PLAYER_COUNT_OPTIONS},
                {"key": "humans", "label": "人类玩家", "value": last.get("humans", 1), "options": HUMAN_COUNT_OPTIONS},
                {"key": "difficulty", "label": "电脑难度", "value": last.get("difficulty", "normal"),
                 "options": DIFFICULTY_OPTIONS},
                {"key": "turn_mode", "label": "回合模式", "value": last.get("turn_mode", "sequential"),
                 "options": TURN_MODE_OPTIONS},
                {"key": "map_type", "label": "地图类型", "value": last.get("map_type", "continents"),
                 "options": MAP_TYPE_OPTIONS},
                {"key": "map_size", "label": "地图尺寸", "value": last.get("map_size", "medium"),
                 "options": MAP_SIZE_OPTIONS},
                {"key": "seed", "label": "地图种子", "value": ""},
            ]
        )

    def _start_from_new_game_form(self) -> bool:
        values = self.ui_system.get_modal_input_values()
        players = int(values.get("players", 2))
        humans = max(1, min(players, int(values.get("humans", 1))))
        seed_text = str(values.get("seed", "")).strip()
        try:
            seed = int(seed_text) if seed_text else None
        except ValueError:
            self._notify("地图种子必须是整数，已改用随机种子。")
            seed = None
        settings = {
            "players": players, "humans": humans, "difficulty": values.get("difficulty", "normal"),
            "turn_mode": values.get("turn_mode", "sequential"), "map_type": values.get("map_type", "continents"),
            "map_size": values.get("map_size", "medium"),
        }
        names = [f"玩家{i + 1}" for i in range(humans)] + [f"电脑{i + 1}" for i in range(players - humans)]
        started = self.start_game(names, seed, turn_mode=settings["turn_mode"], map_type=settings["map_type"],
                                  map_size=settings["map_size"], human_count=humans,
                                  ai_difficulty=settings["difficulty"])
        if started:
            self.last_game_settings = {**settings, "names": names, "seed": seed}
        else:
            self._notify("开局失败：地图无法容纳全部玩家，请换一个种子或更大的地图。")
        return started
