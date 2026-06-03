"""
多人联机网络协议 DTO。

当前只定义纯 JSON 友好的数据转换，不包含实际传输层。
"""
from typing import Any, Dict, List

from .game_engine import GameEngine
from .models import ActionEvent, ActionResult, ActionType, GameAction, HexCoord, Tile, Unit


def coord_to_key(coord: HexCoord) -> str:
    """将坐标转为 JSON dict key。"""
    return f"{coord.q},{coord.r}"


def coord_to_list(coord: HexCoord) -> List[int]:
    """将坐标转为 JSON 数组。"""
    return [coord.q, coord.r]


def parse_coord(value: Any) -> HexCoord:
    """从 JSON 友好格式解析坐标。"""
    if isinstance(value, str):
        q, r = value.split(",")
        return HexCoord(int(q), int(r))
    return HexCoord(int(value[0]), int(value[1]))


def serialize_action(action: GameAction) -> Dict[str, Any]:
    """序列化玩家行动请求。"""
    return {
        "player_id": action.player_id,
        "action_type": action.action_type.value,
        "params": dict(action.params or {})
    }


def deserialize_action(data: Dict[str, Any]) -> GameAction:
    """反序列化玩家行动请求。"""
    return GameAction(
        player_id=data["player_id"],
        action_type=ActionType(data["action_type"]),
        params=dict(data.get("params") or {})
    )


def serialize_event(event: ActionEvent) -> Dict[str, Any]:
    """序列化行动事件。"""
    return {
        "event_type": event.event_type,
        "message": event.message,
        "data": dict(event.data or {})
    }


def deserialize_event(data: Dict[str, Any]) -> ActionEvent:
    """反序列化行动事件。"""
    return ActionEvent(
        event_type=data["event_type"],
        message=data.get("message", ""),
        data=dict(data.get("data") or {})
    )


def serialize_action_result(result: ActionResult) -> Dict[str, Any]:
    """序列化行动结果。"""
    return {
        "success": result.success,
        "message": result.message,
        "events": [serialize_event(event) for event in result.events]
    }


def deserialize_action_result(data: Dict[str, Any]) -> ActionResult:
    """反序列化行动结果。"""
    return ActionResult(
        success=bool(data.get("success")),
        message=data.get("message", ""),
        events=[deserialize_event(event) for event in data.get("events", [])]
    )


def serialize_room_state(room) -> Dict[str, Any]:
    """序列化房间状态。"""
    ended_player_ids = getattr(room.engine.turn_system, "ended_player_ids", set()) if room.engine else set()
    actionable_player_ids = set(room.engine.turn_system.get_turn_status().get("actionable_player_ids", [])) if room.engine else set()
    return {
        "room_id": room.room_id,
        "started": room.started,
        "max_players": room.max_players,
        "turn_mode": room.turn_mode,
        "map_seed": room.map_seed,
        "seats": [
            {
                "client_id": seat.client_id,
                "player_name": seat.player_name,
                "player_id": seat.player_id,
                "connected": seat.connected,
                "ended_turn": seat.player_id in ended_player_ids,
                "can_act": seat.player_id in actionable_player_ids
            }
            for seat in room.seats
        ],
        "recent_events": list(getattr(room, "event_log", [])[-12:])
    }


def _serialize_unit(unit: Unit) -> Dict[str, Any]:
    return {
        "id": unit.id,
        "owner_id": unit.owner.id,
        "unit_type": unit.unit_type.value,
        "position": coord_to_list(unit.position),
        "movement_points": unit.movement_points,
        "max_movement_points": unit.max_movement_points,
        "vision_range": unit.vision_range,
        "quantity": unit.quantity
    }


def _serialize_tile(tile: Tile, visible: bool, explored: bool) -> Dict[str, Any]:
    data = {
        "coord": coord_to_list(tile.coord),
        "terrain": tile.terrain_type.value,
        "visible": visible,
        "explored": explored,
        "owner_id": tile.owner.id if visible and tile.owner else None,
        "city": None,
        "units": []
    }
    if visible and tile.city:
        data["city"] = {
            "id": tile.city.id,
            "owner_id": tile.city.owner.id,
            "center": coord_to_list(tile.city.center_tile)
        }
    if visible:
        data["units"] = [_serialize_unit(unit) for unit in tile.units]
    return data


def serialize_player_view(engine: GameEngine, player_id: str) -> Dict[str, Any]:
    """生成某个玩家可接收的安全视图状态。"""
    player = engine.player_system.get_player_by_id(player_id)
    if not player:
        raise ValueError(f"玩家不存在: {player_id}")

    visible_tiles = engine.vision_system.get_visible_tiles(player_id)
    explored_tiles = engine.vision_system.get_explored_tiles(player_id)
    turn_status = engine.turn_system.get_turn_status()

    players = []
    for other in engine.player_system.players:
        is_self = other.id == player_id
        players.append({
            "id": other.id,
            "name": other.name,
            "is_self": is_self,
            "gold": other.gold if is_self else None,
            "city_count": len(other.cities) if is_self else None,
            "unit_count": len(other.units) if is_self else None,
            "ended_turn": other.id in engine.turn_system.ended_player_ids
        })

    return {
        "player_id": player_id,
        "turn": engine.turn_system.current_turn,
        "turn_status": {
            "turn": turn_status["turn"],
            "turn_number": turn_status["turn_number"],
            "mode": turn_status["mode"],
            "current_player_id": turn_status["current_player_id"],
            "ended_player_ids": turn_status["ended_player_ids"],
            "actionable_player_ids": turn_status["actionable_player_ids"]
        },
        "game_over": engine.game_over,
        "winner_id": engine.winner.id if engine.winner else None,
        "players": players,
        "tiles": {
            coord_to_key(coord): _serialize_tile(
                tile,
                coord in visible_tiles,
                coord in explored_tiles
            )
            for coord, tile in engine.map_tiles.items()
        }
    }
