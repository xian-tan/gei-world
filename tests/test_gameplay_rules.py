"""
关键玩法规则回归测试。
"""
import tempfile
import unittest

from src.game_engine import GameEngine
from src.models import ActionType, GameAction, UnitType, TerrainType
from src.systems.save_system import GameSaveSystem


class TestGameplayRules(unittest.TestCase):
    def test_first_city_does_not_end_game_while_other_player_has_settler(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1 = engine.player_system.players[0]
        settler = player1.units[0]
        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": settler.id}
        )))

        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.END_TURN,
            params={}
        )))

        self.assertFalse(engine.game_over)
        self.assertIsNone(engine.winner)

    def test_player_without_cities_or_units_is_eliminated(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1, player2 = engine.player_system.players
        settler = player1.units[0]
        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": settler.id}
        )))

        for unit in list(player2.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.END_TURN,
            params={}
        )))

        self.assertTrue(engine.game_over)
        self.assertEqual(engine.winner, player1)

    def test_city_capture_transfers_city_and_territory(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        attacker, defender = engine.player_system.players
        city_center = defender.units[0].position
        for unit in list(defender.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

        city = engine.city_system.create_city(defender, city_center, engine.map_tiles)
        defender.cities.append(city)

        city_tile = engine.map_tiles[city.center_tile]
        stationed_soldier = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, city.center_tile)
        city_tile.units.append(stationed_soldier)
        attacker.units.append(stationed_soldier)

        source = next(coord for coord in city.center_tile.neighbors() if coord in engine.map_tiles)
        engine.map_tiles[source].terrain_type = TerrainType.LAND
        moving_soldier = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, source)
        engine.map_tiles[source].units.append(moving_soldier)
        attacker.units.append(moving_soldier)

        self.assertTrue(engine.execute_action(GameAction(
            player_id=attacker.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": moving_soldier.id, "target": [city.center_tile.q, city.center_tile.r]}
        )))

        self.assertEqual(city.owner, attacker)
        self.assertIn(city, attacker.cities)
        self.assertNotIn(city, defender.cities)
        for coord in city.territory_tiles:
            self.assertEqual(engine.map_tiles[coord].owner, attacker)

    def test_save_load_roundtrip_preserves_core_state(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=456))

        player1 = engine.player_system.players[0]
        settler = player1.units[0]
        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": settler.id}
        )))

        city = player1.cities[0]
        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_UNIT,
            params={"city_id": city.id, "unit_type": UnitType.SOLDIER.value}
        )))

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_system = GameSaveSystem(tmp_dir)
            self.assertTrue(save_system.save_game(engine, "roundtrip"))
            loaded = save_system.load_game("roundtrip")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.turn_system.current_turn, engine.turn_system.current_turn)
        self.assertEqual(loaded.turn_system.current_player_index, engine.turn_system.current_player_index)
        self.assertEqual(len(loaded.map_tiles), len(engine.map_tiles))
        self.assertEqual([p.id for p in loaded.player_system.players], [p.id for p in engine.player_system.players])

        loaded_player1 = loaded.player_system.players[0]
        self.assertEqual(loaded_player1.gold, player1.gold)
        self.assertEqual(len(loaded_player1.cities), len(player1.cities))
        self.assertEqual(len(loaded_player1.units), len(player1.units))
        self.assertEqual(loaded_player1.cities[0].center_tile, city.center_tile)
        self.assertIs(loaded.map_tiles[city.center_tile].city, loaded_player1.cities[0])


if __name__ == "__main__":
    unittest.main()
