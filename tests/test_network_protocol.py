"""
多人联机网络协议 DTO 测试。
"""

from src.game_engine import GameEngine
from src.models import ActionType, GameAction, HexCoord, TerrainType
from src.network_protocol import (
    deserialize_action,
    serialize_action,
    serialize_action_result,
    serialize_player_view,
)


def test_action_dto_roundtrip():
    action = GameAction(
        player_id="player_0",
        action_type=ActionType.MOVE_UNIT,
        params={"unit_id": "u1", "target": [1, 2]}
    )

    data = serialize_action(action)
    restored = deserialize_action(data)

    assert data == {
        "player_id": "player_0",
        "action_type": "move_unit",
        "params": {"unit_id": "u1", "target": [1, 2]}
    }
    assert restored == action


def test_action_result_serializes_events():
    engine = GameEngine()
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=123)
    player = engine.player_system.players[0]
    settler = player.units[0]

    result = engine.execute_action_with_result(GameAction(
        player_id=player.id,
        action_type=ActionType.BUILD_CITY,
        params={"unit_id": settler.id}
    ))
    data = serialize_action_result(result)

    assert data["success"]
    assert data["message"] == "城市建立成功"
    assert data["events"][0]["event_type"] == "city_built"
    assert data["events"][0]["data"]["owner_id"] == player.id


def test_player_view_hides_invisible_units_and_enemy_private_counts():
    engine = GameEngine(turn_mode="simultaneous")
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=123, turn_mode="simultaneous")
    player1, player2 = engine.player_system.players
    enemy_unit = player2.units[0]

    hidden_coord = next(
        coord for coord, tile in engine.map_tiles.items()
        if coord not in player1.vision_tiles and tile.terrain_type == TerrainType.LAND
    )
    old_tile = engine.map_tiles[enemy_unit.position]
    if enemy_unit in old_tile.units:
        old_tile.units.remove(enemy_unit)
    enemy_unit.position = hidden_coord
    engine.map_tiles[hidden_coord].units.append(enemy_unit)
    engine.vision_system.update_player_vision(player1, engine.map_tiles)

    view = serialize_player_view(engine, player1.id)
    hidden_tile = view["tiles"][f"{hidden_coord.q},{hidden_coord.r}"]
    enemy_summary = next(player for player in view["players"] if player["id"] == player2.id)
    self_summary = next(player for player in view["players"] if player["id"] == player1.id)

    assert not hidden_tile["visible"]
    assert hidden_tile["units"] == []
    assert hidden_tile["city"] is None
    assert enemy_summary["gold"] is None
    assert enemy_summary["unit_count"] is None
    assert self_summary["gold"] == player1.gold
    assert view["turn_status"]["mode"] == "simultaneous"
