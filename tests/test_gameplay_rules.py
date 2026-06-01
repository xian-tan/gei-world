"""
关键玩法规则回归测试。
"""
import tempfile
import unittest

from src.game_engine import GameEngine
from src.models import ActionType, GameAction, UnitType, TerrainType, HexCoord
from src.systems.save_system import GameSaveSystem


class TestGameplayRules(unittest.TestCase):
    def test_action_result_reports_success_message_and_events(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1 = engine.player_system.players[0]
        settler = player1.units[0]
        result = engine.execute_action_with_result(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": settler.id}
        ))

        self.assertTrue(result.success)
        self.assertEqual(result.message, "城市建立成功")
        self.assertEqual([event.event_type for event in result.events], ["city_built"])

    def test_action_result_reports_city_capture_and_game_over_events(self):
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

        result = engine.execute_action_with_result(GameAction(
            player_id=attacker.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": moving_soldier.id, "target": [city.center_tile.q, city.center_tile.r]}
        ))

        self.assertTrue(result.success)
        event_types = [event.event_type for event in result.events]
        self.assertIn("city_captured", event_types)
        self.assertIn("game_over", event_types)
        self.assertEqual(result.message, f"游戏结束，获胜者：{attacker.name}")

    def test_unit_cannot_jump_over_ocean_without_land_path(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1 = engine.player_system.players[0]
        for unit in list(player1.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

        start = HexCoord(0, 0)
        blocker = HexCoord(1, 0)
        target = HexCoord(2, 0)
        self.assertIn(start, engine.map_tiles)
        self.assertIn(target, engine.map_tiles)
        self.assertIn(blocker, engine.map_tiles)
        engine.map_tiles[start].terrain_type = TerrainType.LAND
        engine.map_tiles[target].terrain_type = TerrainType.LAND
        engine.map_tiles[blocker].terrain_type = TerrainType.OCEAN

        soldier = engine.unit_system.create_unit(UnitType.SOLDIER, player1, start)
        engine.map_tiles[start].units.append(soldier)
        player1.units.append(soldier)

        self.assertFalse(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": soldier.id, "target": [target.q, target.r]}
        )))
        self.assertEqual(soldier.position, start)

    def test_non_current_player_cannot_act(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player2 = engine.player_system.players[1]
        target = player2.units[0].position.neighbors()[0]
        self.assertFalse(engine.execute_action(GameAction(
            player_id=player2.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": player2.units[0].id, "target": [target.q, target.r]}
        )))

    def test_current_player_cannot_move_enemy_unit(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1, player2 = engine.player_system.players
        enemy_unit = player2.units[0]
        original_position = enemy_unit.position
        target = next(coord for coord in original_position.neighbors() if coord in engine.map_tiles)
        engine.map_tiles[target].terrain_type = TerrainType.LAND
        self.assertFalse(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": enemy_unit.id, "target": [target.q, target.r]}
        )))
        self.assertEqual(enemy_unit.position, original_position)

    def test_current_player_cannot_build_city_with_enemy_settler(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1, player2 = engine.player_system.players
        enemy_settler = player2.units[0]
        self.assertFalse(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": enemy_settler.id}
        )))
        self.assertEqual(len(player1.cities), 0)
        self.assertEqual(len(player2.cities), 0)

    def test_current_player_cannot_build_unit_in_enemy_city(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1, player2 = engine.player_system.players
        enemy_settler = player2.units[0]
        enemy_city = engine.city_system.create_city(player2, enemy_settler.position, engine.map_tiles)
        player2.cities.append(enemy_city)
        engine.unit_system.remove_unit(enemy_settler, engine.map_tiles)
        player2_gold = player2.gold

        self.assertFalse(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_UNIT,
            params={"city_id": enemy_city.id, "unit_type": UnitType.SOLDIER.value}
        )))
        self.assertEqual(player2.gold, player2_gold)
        self.assertEqual(len(player2.units), 0)

    def test_cannot_build_city_on_enemy_owned_tile_or_core_range(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1, player2 = engine.player_system.players
        enemy_city = engine.city_system.create_city(player2, player2.units[0].position, engine.map_tiles)
        player2.cities.append(enemy_city)

        enemy_tile = next(iter(enemy_city.territory_tiles))
        self.assertFalse(engine.city_system.can_build_city(enemy_tile, engine.map_tiles, player1))

        adjacent = next(coord for coord in enemy_city.center_tile.neighbors() if coord in engine.map_tiles)
        engine.map_tiles[adjacent].terrain_type = TerrainType.LAND
        engine.map_tiles[adjacent].owner = None
        self.assertFalse(engine.city_system.can_build_city(adjacent, engine.map_tiles, player1))

    def test_city_capture_can_end_game_immediately(self):
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
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.winner, attacker)

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

    def test_save_load_preserves_winner(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1, player2 = engine.player_system.players
        for unit in list(player2.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)
        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.END_TURN,
            params={}
        )))
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.winner, player1)

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_system = GameSaveSystem(tmp_dir)
            self.assertTrue(save_system.save_game(engine, "winner"))
            loaded = save_system.load_game("winner")

        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.game_over)
        self.assertEqual(loaded.winner.id, player1.id)

    def test_save_load_roundtrip_preserves_core_state(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=456))
        engine.ai_player_configs = {"player_1": {"ai_type": "simple", "difficulty": "easy"}}

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
        self.assertEqual(loaded.ai_player_configs, engine.ai_player_configs)
        self.assertTrue(player1.explored_tiles.issubset(loaded_player1.explored_tiles))


if __name__ == "__main__":
    unittest.main()
