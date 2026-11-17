"""
阶段 B 规则与数值测试：城市防御、生产限制、收入、占领、淘汰、回合上限。
"""
import tempfile

from src.config import CITY_CONFIG, ECONOMY_CONFIG, GAME_CONFIG, PLAYER_CONFIG, UNIT_CONFIG
from src.game_engine import GameEngine
from src.models import ActionType, GameAction, HexCoord, TerrainType, UnitType
from src.systems.save_system import GameSaveSystem
from tests.helpers import anchor_player, place_unit


def _engine(players=2, mode="sequential"):
    engine = GameEngine(turn_mode=mode)
    assert engine.initialize_game([f"玩家{i + 1}" for i in range(players)], map_seed=123, turn_mode=mode)
    for player in engine.player_system.players:
        for unit in list(player.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)
    for tile in engine.map_tiles.values():
        tile.terrain_type = TerrainType.LAND
        tile.owner = None
    for player in engine.player_system.players:
        anchor_player(engine, player)
    return engine


def _end_full_turn(engine):
    for player in list(engine.turn_system.alive_players()):
        if engine.turn_system.can_player_act(player.id):
            assert engine.execute_action(GameAction(player.id, ActionType.END_TURN, {}))


def test_initial_economy_values():
    assert PLAYER_CONFIG["initial_gold"] < UNIT_CONFIG["settler_cost"]
    assert UNIT_CONFIG["soldier_cost"] > 1


def test_city_defense_grows_each_turn_up_to_max():
    engine = _engine()
    player = engine.player_system.players[0]
    city = engine.city_system.create_city(player, HexCoord(0, 0), engine.map_tiles)
    player.cities.append(city)
    assert city.defense == CITY_CONFIG["base_defense"]
    for _ in range(CITY_CONFIG["max_defense"] + 2):
        _end_full_turn(engine)
    assert city.defense == CITY_CONFIG["max_defense"]


def test_failed_siege_wears_down_city_defense_then_capture_resets_it():
    engine = _engine()
    attacker, defender = engine.player_system.players
    city = engine.city_system.create_city(defender, HexCoord(0, 0), engine.map_tiles)
    defender.cities.append(city)
    city.defense = 5

    first = place_unit(engine, attacker, UnitType.SOLDIER, HexCoord(2, 0), quantity=3)
    assert engine.execute_action(GameAction(
        attacker.id, ActionType.MOVE_UNIT, {"unit_id": first.id, "target": [0, 0], "move_quantity": 3}
    ))
    assert city.owner == defender
    assert city.defense == 2
    assert first not in attacker.units

    second = place_unit(engine, attacker, UnitType.SOLDIER, HexCoord(1, 0), quantity=4)
    result = engine.execute_action_with_result(GameAction(
        attacker.id, ActionType.MOVE_UNIT, {"unit_id": second.id, "target": [0, 0], "move_quantity": 4}
    ))
    assert "city_captured" in [event.event_type for event in result.events]
    assert city.owner == attacker
    assert city.defense == CITY_CONFIG["captured_defense"]
    assert second.quantity == 2


def test_income_includes_city_center_bonus():
    engine = _engine()
    player = engine.player_system.players[0]
    city = engine.city_system.create_city(player, HexCoord(0, 0), engine.map_tiles)
    player.cities.append(city)
    expected = ECONOMY_CONFIG["city_center_income"] + len(city.territory_tiles) * ECONOMY_CONFIG["territory_income"]
    assert engine.player_system.calculate_income(player, engine.map_tiles) == expected


def test_occupation_requires_adjacent_own_territory():
    engine = _engine()
    player = engine.player_system.players[0]
    soldier = place_unit(engine, player, UnitType.SOLDIER, HexCoord(4, 0))
    assert not engine.combat_system.occupy_tile(soldier, HexCoord(4, 0), engine.map_tiles)
    engine.map_tiles[HexCoord(3, 0)].owner = player
    assert engine.combat_system.occupy_tile(soldier, HexCoord(4, 0), engine.map_tiles)


def test_player_with_only_soldiers_is_eliminated_and_units_removed():
    engine = _engine()
    winner, loser = engine.player_system.players
    city = engine.city_system.create_city(winner, HexCoord(0, 0), engine.map_tiles)
    winner.cities.append(city)
    lone = place_unit(engine, loser, UnitType.SOLDIER, HexCoord(5, -2), quantity=4)
    loser_settler = next(unit for unit in loser.units if unit.unit_type == UnitType.SETTLER)
    hunter = place_unit(engine, winner, UnitType.SOLDIER, HexCoord(loser_settler.position.q + 1, loser_settler.position.r))

    assert engine.execute_action(GameAction(
        winner.id, ActionType.MOVE_UNIT, {"unit_id": hunter.id, "target": [loser_settler.position.q, loser_settler.position.r]}
    ))
    assert engine.game_over
    assert engine.winner == winner
    assert lone not in loser.units
    assert not loser.units


def test_sequential_turn_skips_eliminated_player():
    engine = _engine(players=3)
    p1, p2, p3 = engine.player_system.players
    for unit in list(p2.units):
        engine.unit_system.remove_unit(unit, engine.map_tiles)
    assert engine.execute_action(GameAction(p1.id, ActionType.END_TURN, {}))
    assert engine.turn_system.get_current_player() == p3


def test_simultaneous_turn_advances_when_remaining_player_eliminated():
    engine = _engine(players=3, mode="simultaneous")
    p1, p2, p3 = engine.player_system.players
    assert engine.execute_action(GameAction(p1.id, ActionType.END_TURN, {}))
    assert engine.execute_action(GameAction(p2.id, ActionType.END_TURN, {}))
    assert engine.turn_system.current_turn == 1
    for unit in list(p3.units):
        engine.unit_system.remove_unit(unit, engine.map_tiles)
    engine._check_game_over()
    assert engine.turn_system.current_turn == 2


def test_turn_limit_ends_game_by_score():
    engine = _engine()
    strong, weak = engine.player_system.players
    city = engine.city_system.create_city(strong, HexCoord(0, 0), engine.map_tiles)
    strong.cities.append(city)
    engine.turn_system.current_turn = GAME_CONFIG["max_turns"]
    _end_full_turn(engine)
    assert engine.game_over
    assert engine.winner == strong
    assert engine.calculate_score(strong) > engine.calculate_score(weak)


def test_city_defense_and_production_state_survive_save_load():
    engine = _engine()
    player = engine.player_system.players[0]
    city = engine.city_system.create_city(player, HexCoord(0, 0), engine.map_tiles)
    player.cities.append(city)
    city.defense = 6
    city.productions_this_turn = 1
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_system = GameSaveSystem(tmp_dir)
        assert save_system.save_game(engine, "rules")
        loaded = save_system.load_game("rules")
    loaded_city = loaded.player_system.players[0].cities[0]
    assert loaded_city.defense == 6
    assert loaded_city.productions_this_turn == 1
