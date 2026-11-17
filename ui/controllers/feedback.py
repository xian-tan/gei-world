"""
消息反馈：行动结果与事件文案。
"""
from typing import Optional




class FeedbackMixin:
    """消息反馈：行动结果与事件文案。"""

    def _notify(self, message: str):
        """同时输出控制台和界面消息。"""
        print(message)
        self.ui_system.add_message(message)

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
