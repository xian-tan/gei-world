"""
对局流程：开局、AI 回合调度、结束回合、返回菜单与退出。
"""


from src.game_session import LocalGameSession
from src.models import ActionType, GameAction
from src.systems.ai_system import AIManager
from ui.hex_renderer import HexRenderer
from ui.ui_config import COLORS, OFFSET_X, OFFSET_Y


class GameFlowMixin:
    """对局流程：开局、AI 回合调度、结束回合、返回菜单与退出。"""

    def start_game(self, player_names: list, map_seed: int = None, turn_mode: str = "sequential",
                   map_type: str = None, map_size: str = None, human_count: int = 1,
                   ai_difficulty: str = "normal"):
        """开始本地对局：前 human_count 名为人类（热座），其余为电脑。"""
        new_session = LocalGameSession()
        if not new_session.start_game(player_names, map_seed, turn_mode=turn_mode,
                                      map_type=map_type, map_size=map_size):
            return False
        self.session = new_session
        self._clear_multiplayer_context()
        self.game_started = True
        players = self.game_engine.player_system.players
        human_count = max(1, min(human_count, len(players)))
        self.human_player_ids = [player.id for player in players[:human_count]]
        self.local_player_id = self.human_player_ids[0]
        self._clear_ui_selection_state()
        self.ui_system.close_modal()
        self._setup_ai_players(ai_difficulty, human_count)
        self.last_game_settings = getattr(self, "last_game_settings", None) or {}
        self.last_game_settings.update({
            "names": list(player_names), "seed": map_seed, "turn_mode": turn_mode, "map_type": map_type,
            "map_size": map_size, "humans": human_count, "difficulty": ai_difficulty, "players": len(player_names),
        })
        self.camera_system.zoom = 1.6
        self._focus_on_player(self._get_controlled_player())
        self.ui_system.show_banner(f"第 1 回合 · {self._get_controlled_player().name}")
        self._notify(f"游戏开始！玩家: {', '.join(player_names)}")
        self._notify("新手提示：左键选中单位或城市，右键移动选中单位。")
        self._notify("移动到合适陆地后，按 B 或点击建城按钮建立第一座城市。")
        self._notify("目标：建城、生产士兵，探索并占领或消灭全部对手。按 F1 查看快捷键。")
        return True

    def _restart_game(self):
        """按上一局设置重新开局（固定种子沿用，随机种子重新随机）。"""
        settings = getattr(self, "last_game_settings", None) or {}
        names = settings.get("names") or ["玩家1", "电脑1"]
        self.start_game(names, settings.get("seed"), turn_mode=settings.get("turn_mode", "sequential"),
                        map_type=settings.get("map_type"), map_size=settings.get("map_size"),
                        human_count=settings.get("humans", 1), ai_difficulty=settings.get("difficulty", "normal"))

    def _focus_on_player(self, player):
        """把视角移到玩家的首座城市或首个单位。"""
        if not player:
            self._center_camera_on_map()
            return
        anchor = player.cities[0].center_tile if player.cities else (player.units[0].position if player.units else None)
        if anchor is None:
            self._center_camera_on_map()
            return
        self.camera_system.set_position(*HexRenderer.hex_to_pixel(anchor.q, anchor.r, OFFSET_X, OFFSET_Y))

    def _is_hotseat(self) -> bool:
        return not self.multiplayer_room_id and len(getattr(self, "human_player_ids", [])) > 1

    def _switch_hotseat_player(self, announce: bool = True) -> bool:
        """同时回合热座：切换到下一位仍可行动的人类玩家。"""
        if not self._is_hotseat() or self.game_engine.turn_system.mode != "simultaneous":
            return False
        ids = self.human_player_ids
        start = ids.index(self.local_player_id) if self.local_player_id in ids else -1
        for offset in range(1, len(ids) + 1):
            candidate = ids[(start + offset) % len(ids)]
            if self.game_engine.turn_system.can_player_act(candidate) and candidate != self.local_player_id:
                self.local_player_id = candidate
                self._clear_ui_selection_state()
                player = self._get_controlled_player()
                self._focus_on_player(player)
                if announce:
                    self.ui_system.show_banner(f"轮到 {player.name}")
                return True
        return False

    def _setup_ai_players(self, difficulty: str = "normal", human_count: int = 1):
        """将前 human_count 名之外的玩家设为 AI。"""
        self.ai_manager = AIManager()
        self.game_engine.ai_player_configs = {}
        for player in self.game_engine.player_system.players[human_count:]:
            self.ai_manager.add_ai_player(player, difficulty=difficulty)
            self.game_engine.ai_player_configs[player.id] = {"difficulty": difficulty}

    def _restore_ai_players_from_engine(self):
        """根据引擎中的 AI 配置重建 AI 管理器。"""
        self.ai_manager = AIManager()
        for player_id, config in getattr(self.game_engine, 'ai_player_configs', {}).items():
            player = self.game_engine.player_system.get_player_by_id(player_id)
            if player:
                self.ai_manager.add_ai_player(player, difficulty=config.get("difficulty", "normal"))

    def _on_ai_result(self, player_name: str):
        """AI 行动只播报战斗、攻城和胜负等关键事件，避免刷屏。"""
        important = {"combat_resolved", "city_captured", "siege_failed", "player_eliminated", "game_over"}
        
        def handle(_action, result):
            if any(event.event_type in important for event in result.events):
                self._notify_action_result(result, player_name)
        return handle

    def _play_ai_turn(self, player):
        self.ai_manager.play_turn(
            player.id,
            self.game_engine,
            self.session.submit_action,
            on_result=self._on_ai_result(player.name)
        )

    def _process_ai_turns(self):
        """轮流回合：自动处理连续 AI 回合，直到轮回人类玩家或游戏结束。"""
        for _ in range(len(self.game_engine.player_system.players) * 2):
            current_player = self.game_engine.get_current_player()
            if self.game_engine.game_over or not current_player or not self.ai_manager.is_ai_player(current_player.id):
                return
            self._play_ai_turn(current_player)

    def _process_simultaneous_ai_turns(self):
        """同时回合：所有仍可行动的 AI 完成本回合，不跨入下一回合。"""
        starting_turn = self.game_engine.turn_system.current_turn
        ai_players = [
            player for player in self.game_engine.player_system.players
            if self.ai_manager.is_ai_player(player.id)
        ]
        for player in ai_players:
            if self.game_engine.game_over or self.game_engine.turn_system.current_turn != starting_turn:
                return
            if self.game_engine.turn_system.can_player_act(player.id):
                self._play_ai_turn(player)

    def _handle_end_turn(self, force: bool = False):
        """处理结束回合；有单位仍可移动时先确认。"""
        current_player = self._get_controlled_player()
        if not current_player:
            return
        if not force:
            movable_units = [
                unit for unit in current_player.units
                if unit.movement_points > 0
            ]
            if movable_units:
                self.render_system.set_attention_tiles({unit.position for unit in movable_units})
                self.ui_system.show_modal(
                    "仍有单位可移动",
                    [f"还有 {len(movable_units)} 个单位/士兵栈保留移动力。", "橙色轮廓已在地图上标出。", "确定要结束回合吗？"],
                    [
                        {
                            'text': "继续操作",
                            'callback': self.ui_system.close_modal,
                        },
                        {
                            'text': "仍然结束回合",
                            'callback': lambda: self._handle_end_turn(force=True),
                            'color': COLORS['SUCCESS'],
                            'text_color': COLORS['TEXT']
                        }
                    ]
                )
                return
        
        self.ui_system.close_modal()
        self.render_system.clear_attention_tiles()
        turn_before = self.game_engine.turn_system.current_turn
        action = GameAction(player_id=current_player.id, action_type=ActionType.END_TURN, params={})
        result = self._execute_action_and_notify(action)
        if not result.success:
            return
        self._clear_ui_selection_state()
        turn_advanced = any(
            event.event_type == "turn_advanced" or event.data.get("turn_advanced")
            for event in result.events
        )
        if self.multiplayer_room_id and not turn_advanced:
            self._notify("等待其他玩家结束本回合。")
        if self.game_engine.turn_system.mode == "sequential":
            self._process_ai_turns()
        else:
            self._process_simultaneous_ai_turns()
            if self._is_hotseat() and not self._can_controlled_player_act():
                self._switch_hotseat_player(announce=False)
        self._announce_turn_change(turn_before, current_player.id)

    def _announce_turn_change(self, turn_before: int, previous_player_id: str):
        """回合推进或热座换人时显示横幅并移动视角。"""
        if self.game_engine.game_over or self.multiplayer_room_id:
            return
        turn = self.game_engine.turn_system.current_turn
        if turn != turn_before and self._is_hotseat() and self.game_engine.turn_system.mode == "simultaneous":
            self.local_player_id = self.human_player_ids[0]
        player = self._get_controlled_player()
        if not player:
            return
        if turn != turn_before:
            self.ui_system.show_banner(f"第 {turn} 回合 · {player.name}")
        elif player.id != previous_player_id:
            self.ui_system.show_banner(f"轮到 {player.name}")
        else:
            return
        if self._is_hotseat():
            self._clear_ui_selection_state()
            self._focus_on_player(player)

    def _show_return_to_menu_modal(self):
        """显示返回主菜单确认弹窗。"""
        lines = ["确定要返回主菜单吗？", "未保存的进度会丢失。"]
        if self.multiplayer_room_id:
            lines.append("多人房间会先执行离开；房主退出会关闭房间。")
        self.ui_system.show_modal(
            "返回主菜单",
            lines,
            [
                {
                    'text': "继续游戏",
                    'callback': self.ui_system.close_modal,
                },
                {
                    'text': "返回主菜单",
                    'callback': self._confirm_return_to_main_menu,
                    'color': COLORS['WARNING'],
                    'text_color': COLORS['PANEL_BG']
                }
            ]
        )

    def _confirm_return_to_main_menu(self):
        """确认返回主菜单。"""
        if self.multiplayer_room_id:
            if hasattr(self.session, 'leave_room'):
                response = self.session.leave_room()
                if not response.get("success"):
                    self._notify(f"离开房间失败，已返回主菜单：{response.get('message', '未知错误')}")
            elif self.multiplayer_server and self.active_multiplayer_client_id:
                self.multiplayer_server.leave_room(self.multiplayer_room_id, self.active_multiplayer_client_id)
        self._clear_multiplayer_context()
        self.session = LocalGameSession()
        self.ai_manager = AIManager()
        self.game_started = False
        self.local_player_id = None
        self._clear_ui_selection_state()
        self.ui_system.close_modal()
        self._notify("已返回主菜单。")
        return True

    def _show_exit_confirmation(self):
        """显示退出确认弹窗。"""
        actions = [
            {
                'text': "取消",
                'callback': self.ui_system.close_modal,
            }
        ]
        if self.game_started:
            actions.append({
                'text': "返回主菜单",
                'callback': self._confirm_return_to_main_menu,
                'color': COLORS['WARNING'],
                'text_color': COLORS['PANEL_BG']
            })
        actions.append({
            'text': "退出游戏",
            'callback': self._confirm_exit_game,
            'color': COLORS['DANGER'],
            'text_color': COLORS['TEXT']
        })
        self.ui_system.show_modal(
            "确认退出",
            ["确定要退出游戏吗？", "未保存的进度会丢失。"],
            actions
        )

    def _confirm_exit_game(self):
        """确认退出游戏。"""
        self.ui_system.close_modal()
        self.running = False
