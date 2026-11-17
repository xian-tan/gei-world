"""
对局流程：开局、AI 回合调度、结束回合、返回菜单与退出。
"""


from src.game_session import LocalGameSession
from src.models import ActionType, GameAction
from src.systems.ai_system import AIManager
from ui.ui_config import COLORS


class GameFlowMixin:
    """对局流程：开局、AI 回合调度、结束回合、返回菜单与退出。"""

    def start_game(self, player_names: list, map_seed: int = None, turn_mode: str = "sequential"):
        """开始游戏"""
        new_session = LocalGameSession()
        if new_session.start_game(player_names, map_seed, turn_mode=turn_mode):
            self.session = new_session
            self._clear_multiplayer_context()
            self.game_started = True
            self.local_player_id = self.game_engine.player_system.players[0].id if self.game_engine.player_system.players else None
            self._clear_ui_selection_state()
            self.ui_system.close_modal()
            self._setup_ai_players()
            
            # 将摄像机移动到地图中心
            self._center_camera_on_map()
            
            self._notify(f"游戏开始！玩家: {', '.join(player_names)}")
            self._notify("新手提示：左键选中单位或城市，右键移动选中单位。")
            self._notify("移动到合适陆地后，按 B 或点击建城按钮建立第一座城市。")
            self._notify("目标：建城、生产士兵，探索并占领对手城市。")
            return True
        return False

    def _setup_ai_players(self, difficulty: str = "normal"):
        """将第一个玩家之外的玩家设为 AI。"""
        self.ai_manager = AIManager()
        self.game_engine.ai_player_configs = {}
        for player in self.game_engine.player_system.players[1:]:
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
        important = {"combat_resolved", "city_captured", "game_over"}
        
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
                            'color': COLORS['LIGHT_GRAY'],
                            'text_color': COLORS['BLACK']
                        },
                        {
                            'text': "仍然结束回合",
                            'callback': lambda: self._handle_end_turn(force=True),
                            'color': COLORS['GREEN'],
                            'text_color': COLORS['WHITE']
                        }
                    ]
                )
                return
        
        self.ui_system.close_modal()
        self.render_system.clear_attention_tiles()
        action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.END_TURN,
            params={}
        )
        
        result = self._execute_action_and_notify(action)
        if result.success:
            self._clear_ui_selection_state()
            turn_advanced = any(
                event.event_type == "turn_advanced"
                or event.data.get("turn_advanced")
                for event in result.events
            )
            if self.multiplayer_room_id and not turn_advanced:
                self._notify("等待其他玩家结束本回合。")
            if self.game_engine.turn_system.mode == "sequential":
                self._process_ai_turns()
            else:
                self._process_simultaneous_ai_turns()

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
                    'color': COLORS['LIGHT_GRAY'],
                    'text_color': COLORS['BLACK']
                },
                {
                    'text': "返回主菜单",
                    'callback': self._confirm_return_to_main_menu,
                    'color': COLORS['ORANGE'],
                    'text_color': COLORS['BLACK']
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
                'color': COLORS['LIGHT_GRAY'],
                'text_color': COLORS['BLACK']
            }
        ]
        if self.game_started:
            actions.append({
                'text': "返回主菜单",
                'callback': self._confirm_return_to_main_menu,
                'color': COLORS['ORANGE'],
                'text_color': COLORS['BLACK']
            })
        actions.append({
            'text': "退出游戏",
            'callback': self._confirm_exit_game,
            'color': COLORS['RED'],
            'text_color': COLORS['WHITE']
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
