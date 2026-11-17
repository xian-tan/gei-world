"""
策略 AI 测试。
"""
import statistics

from scripts.simulate import simulate_game
from src.game_engine import GameEngine
from src.models import ActionType, HexCoord, TerrainType, UnitType
from src.systems.ai_system import AIManager, StrategicAI, normalize_difficulty
from tests.helpers import anchor_player, place_unit


def _arena():
    engine = GameEngine()
    assert engine.initialize_game(["AI", "玩家"], map_seed=123)
    for player in engine.player_system.players:
        for unit in list(player.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)
    for tile in engine.map_tiles.values():
        tile.terrain_type = TerrainType.LAND
        tile.owner = None
    ai_player, human = engine.player_system.players
    home = engine.city_system.create_city(ai_player, HexCoord(-4, 0), engine.map_tiles)
    ai_player.cities.append(home)
    target = engine.city_system.create_city(human, HexCoord(2, 0), engine.map_tiles)
    human.cities.append(target)
    anchor_player(engine, human)
    return engine, ai_player, human, target


def _refresh_vision(engine):
    engine._update_all_visions()


def test_ai_does_not_suicide_into_strong_city():
    engine, ai_player, _human, city = _arena()
    city.defense = 5
    stack = place_unit(engine, ai_player, UnitType.SOLDIER, HexCoord(0, 0), quantity=3)
    _refresh_vision(engine)
    action = StrategicAI(ai_player, "normal", seed=1)._soldier_move(engine, stack)
    assert action is None or action.params["target"] != [city.center_tile.q, city.center_tile.r]


def test_ai_attacks_city_when_force_is_sufficient():
    engine, ai_player, _human, city = _arena()
    city.defense = 2
    stack = place_unit(engine, ai_player, UnitType.SOLDIER, HexCoord(0, 0), quantity=5)
    _refresh_vision(engine)
    action = StrategicAI(ai_player, "normal", seed=1)._soldier_move(engine, stack)
    assert action.action_type == ActionType.MOVE_UNIT
    assert action.params["target"] == [city.center_tile.q, city.center_tile.r]


def test_ai_play_turn_captures_weak_city_and_ends_turn():
    engine, ai_player, human, city = _arena()
    city.defense = 1
    place_unit(engine, ai_player, UnitType.SOLDIER, HexCoord(0, 0), quantity=4)
    _refresh_vision(engine)
    manager = AIManager(seed=3)
    manager.add_ai_player(ai_player, difficulty="normal")
    results = manager.play_turn(ai_player.id, engine, engine.execute_action_with_result)
    assert city.owner == ai_player
    assert results[-1].events[0].event_type in {"turn_ended", "game_over"} or engine.game_over
    assert not engine.turn_system.can_player_act(ai_player.id) or engine.game_over


def test_ai_settler_builds_first_city_immediately():
    engine = GameEngine()
    assert engine.initialize_game(["AI", "AI2"], map_seed=7)
    player = engine.player_system.players[0]
    action = StrategicAI(player, "normal", seed=1).get_action(engine)
    assert action.action_type == ActionType.BUILD_CITY


def test_ai_actions_are_always_legal_over_a_short_game():
    result = simulate_game(11, ("normal", "hard"), max_turns=25)
    assert result["turns"] >= 2


def test_normal_ai_expands_to_three_cities_by_turn_30():
    results = [simulate_game(seed, ("normal", "normal"), max_turns=30, snapshot_turn=30) for seed in range(12)]
    cities = [count for result in results for count in result["cities_at_snapshot"]]
    assert statistics.mean(cities) >= 3.0


def test_difficulty_profiles():
    assert normalize_difficulty("medium") == "normal"
    assert normalize_difficulty("unknown") == "normal"
    engine = GameEngine()
    assert engine.initialize_game(["AI", "AI2"], map_seed=7)
    player = engine.player_system.players[0]
    manager = AIManager(seed=1)
    manager.add_ai_player(player, difficulty="hard")
    gold = player.gold
    manager.play_turn(player.id, engine, engine.execute_action_with_result)
    assert player.gold >= gold  # 困难 AI 获得回合金币加成（首回合建城不花钱）
