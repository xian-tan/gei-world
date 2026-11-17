"""
移动阻挡与战斗边界规则测试。
"""
import random

from src.game_engine import GameEngine
from src.models import ActionType, GameAction, HexCoord, TerrainType, UnitType
from tests.helpers import anchor_player


def _clear_board(engine):
    for player in engine.player_system.players:
        for unit in list(player.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)
    for tile in engine.map_tiles.values():
        tile.terrain_type = TerrainType.LAND
        tile.owner = None


def _place(engine, player, unit_type, coord, quantity=1):
    unit = engine.unit_system.create_unit(unit_type, player, coord, quantity)
    engine.map_tiles[coord].units.append(unit)
    player.units.append(unit)
    return unit


def _engine():
    engine = GameEngine()
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=123)
    _clear_board(engine)
    for player in engine.player_system.players:
        anchor_player(engine, player)
    return engine


def test_soldier_destroys_unguarded_enemy_settler():
    engine = _engine()
    attacker, defender = engine.player_system.players
    soldier = _place(engine, attacker, UnitType.SOLDIER, HexCoord(0, 0))
    settler = _place(engine, defender, UnitType.SETTLER, HexCoord(1, 0))

    result = engine.execute_action_with_result(GameAction(
        attacker.id, ActionType.MOVE_UNIT, {"unit_id": soldier.id, "target": [1, 0]}
    ))
    assert result.success
    assert settler not in defender.units
    assert settler not in engine.unit_system.units
    assert soldier.position == HexCoord(1, 0)


def test_defeated_stack_removes_settlers_on_same_tile():
    engine = _engine()
    attacker, defender = engine.player_system.players
    soldier = _place(engine, attacker, UnitType.SOLDIER, HexCoord(0, 0), quantity=5)
    settler = _place(engine, defender, UnitType.SETTLER, HexCoord(1, 0))
    _place(engine, defender, UnitType.SOLDIER, HexCoord(1, 0), quantity=2)

    assert engine.execute_action(GameAction(
        attacker.id, ActionType.MOVE_UNIT, {"unit_id": soldier.id, "target": [1, 0], "move_quantity": 5}
    ))
    assert settler not in defender.units
    assert all(unit.owner == attacker for unit in engine.map_tiles[HexCoord(1, 0)].units)
    assert soldier.quantity == 3


def test_settler_cannot_enter_enemy_tile():
    engine = _engine()
    mover, other = engine.player_system.players
    settler = _place(engine, mover, UnitType.SETTLER, HexCoord(0, 0))
    _place(engine, other, UnitType.SOLDIER, HexCoord(1, 0))

    assert HexCoord(1, 0) not in engine.unit_system.get_reachable_tiles(settler, engine.map_tiles)
    result = engine.execute_action_with_result(GameAction(
        mover.id, ActionType.MOVE_UNIT, {"unit_id": settler.id, "target": [1, 0]}
    ))
    assert not result.success
    assert "移民" in result.message


def test_units_cannot_pass_through_enemy_stack():
    engine = _engine()
    mover, other = engine.player_system.players
    soldier = _place(engine, mover, UnitType.SOLDIER, HexCoord(0, 0))
    soldier.movement_points = soldier.max_movement_points = 2
    for coord in HexCoord(0, 0).neighbors():
        if coord != HexCoord(1, 0):
            engine.map_tiles[coord].terrain_type = TerrainType.OCEAN
    _place(engine, other, UnitType.SOLDIER, HexCoord(1, 0))

    reachable = set(engine.unit_system.get_reachable_tiles(soldier, engine.map_tiles))
    assert HexCoord(1, 0) in reachable
    assert HexCoord(2, 0) not in reachable


def test_map_generation_does_not_touch_global_random_state():
    random.seed(42)
    expected = random.random()
    random.seed(42)
    engine = GameEngine()
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=7)
    assert random.random() == expected


def test_same_seed_produces_same_map_and_spawns():
    first, second = GameEngine(), GameEngine()
    assert first.initialize_game(["玩家1", "玩家2"], map_seed=99)
    assert second.initialize_game(["玩家1", "玩家2"], map_seed=99)
    assert {c: t.terrain_type for c, t in first.map_tiles.items()} == \
        {c: t.terrain_type for c, t in second.map_tiles.items()}
    assert [p.units[0].position for p in first.player_system.players] == \
        [p.units[0].position for p in second.player_system.players]


def test_failed_siege_emits_siege_failed_and_destroyed_events():
    engine = _engine()
    attacker, defender = engine.player_system.players
    city = engine.city_system.create_city(defender, HexCoord(0, 0), engine.map_tiles)
    defender.cities.append(city)
    city.defense = 4
    soldier = _place(engine, attacker, UnitType.SOLDIER, HexCoord(2, 0), quantity=2)

    result = engine.execute_action_with_result(GameAction(
        attacker.id, ActionType.MOVE_UNIT, {"unit_id": soldier.id, "target": [0, 0], "move_quantity": 2}
    ))
    types = [event.event_type for event in result.events]
    assert types[0] == "unit_moved"
    assert "siege_failed" in types
    assert "combat_resolved" in types
    assert result.message.startswith("攻城失败")
    assert soldier.id not in {unit.id for unit in engine.unit_system.units}


def test_elimination_emits_player_eliminated_and_game_over():
    engine = _engine()
    hunter_owner, victim = engine.player_system.players
    city = engine.city_system.create_city(hunter_owner, HexCoord(-3, 0), engine.map_tiles)
    hunter_owner.cities.append(city)
    victim_settler = next(u for u in victim.units if u.unit_type == UnitType.SETTLER)
    _place(engine, victim, UnitType.SOLDIER, HexCoord(5, -5))
    target = victim_settler.position
    hunter = _place(engine, hunter_owner, UnitType.SOLDIER, HexCoord(target.q + 1, target.r))

    result = engine.execute_action_with_result(GameAction(
        hunter_owner.id, ActionType.MOVE_UNIT, {"unit_id": hunter.id, "target": [target.q, target.r]}
    ))
    types = [event.event_type for event in result.events]
    assert "player_eliminated" in types
    assert types[-1] == "game_over"
    assert engine.winner == hunter_owner
    assert not victim.units


def test_unit_registry_stays_consistent_after_combat():
    engine = _engine()
    attacker, defender = engine.player_system.players
    soldier = _place(engine, attacker, UnitType.SOLDIER, HexCoord(0, 0), quantity=3)
    _place(engine, defender, UnitType.SOLDIER, HexCoord(1, 0), quantity=5)
    assert engine.execute_action(GameAction(
        attacker.id, ActionType.MOVE_UNIT, {"unit_id": soldier.id, "target": [1, 0], "move_quantity": 3}
    ))
    registry = {unit.id for unit in engine.unit_system.units}
    on_map = {unit.id for tile in engine.map_tiles.values() for unit in tile.units}
    owned = {unit.id for player in engine.player_system.players for unit in player.units}
    assert registry == on_map == owned
