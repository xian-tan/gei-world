"""
消息反馈：行动结果与事件文案、地图浮字。
"""
from typing import Optional




from src.models import HexCoord
from ui.ui_config import COLORS


class FeedbackMixin:
    """消息反馈：行动结果与事件文案。"""

    def _notify(self, message: str):
        """同时输出控制台和界面消息。"""
        print(message)
        self.ui_system.add_message(message)

    def _notify_action_result(self, result, actor_name: str = None):
        """展示结构化行动结果，优先显示战斗/攻城等关键事件。"""
        self._spawn_event_effects(result)
        turn_events = {"turn_ended", "turn_advanced"}
        if result.success and result.events and all(e.event_type in turn_events for e in result.events):
            for event in result.events:
                if event.event_type == "turn_advanced":
                    self._notify(event.message)
            return
        priority_types = {"combat_resolved", "city_captured", "siege_failed", "game_over"}
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
        if event.event_type == "unit_produced":
            return event.message or "单位生产成功"
        return event.message

    def _spawn_event_effects(self, result):
        """在可见地块上显示战斗/攻城/建城浮字。"""
        effects = {
            "combat_resolved": ("战斗！", COLORS['WARNING']),
            "siege_failed": ("攻城失败", COLORS['DANGER']),
            "city_captured": ("城市易主", COLORS['WARNING']),
            "city_built": ("建城", COLORS['SUCCESS']),
        }
        viewer = self._get_controlled_player()
        visible = self.session.get_visible_tiles(viewer.id) if viewer else set()
        for event in result.events:
            if event.event_type not in effects or not event.data.get("position"):
                continue
            coord = HexCoord(*event.data["position"])
            if coord in visible:
                text, color = effects[event.event_type]
                self.render_system.add_floating_text(coord, text, color)
