"""
关键玩法规则回归测试。
"""
import tempfile
import unittest

from src.game_engine import GameEngine
from src.models import ActionType, GameAction, UnitType, TerrainType, HexCoord
from src.systems.save_system import GameSaveSystem
from src.config import UNIT_CONFIG


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

    def test_combat_result_reports_combat_event(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        attacker, defender = engine.player_system.players
        for unit in list(attacker.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)
        for unit in list(defender.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

        start = HexCoord(0, 0)
        target = HexCoord(1, 0)
        engine.map_tiles[start].terrain_type = TerrainType.LAND
        engine.map_tiles[target].terrain_type = TerrainType.LAND

        attacking_soldier = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, start)
        defending_soldier = engine.unit_system.create_unit(UnitType.SOLDIER, defender, target)
        engine.map_tiles[start].units.append(attacking_soldier)
        engine.map_tiles[target].units.append(defending_soldier)
        attacker.units.append(attacking_soldier)
        defender.units.append(defending_soldier)

        result = engine.execute_action_with_result(GameAction(
            player_id=attacker.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": attacking_soldier.id, "target": [target.q, target.r]}
        ))

        self.assertTrue(result.success)
        event_types = [event.event_type for event in result.events]
        self.assertIn("combat_resolved", event_types)
        self.assertIn("unit_destroyed", event_types)
        self.assertEqual(len(engine.map_tiles[target].units), 0)

    def test_soldier_cost_is_one_and_can_build_with_one_gold(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player = engine.player_system.players[0]
        settler = player.units[0]
        self.assertTrue(engine.execute_action(GameAction(
            player_id=player.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": settler.id}
        )))
        city = player.cities[0]
        player.gold = 1
        self.assertEqual(UNIT_CONFIG["soldier_cost"], 1)

        result = engine.execute_action_with_result(GameAction(
            player_id=player.id,
            action_type=ActionType.BUILD_UNIT,
            params={"city_id": city.id, "unit_type": UnitType.SOLDIER.value}
        ))
        self.assertTrue(result.success)
        self.assertEqual(player.gold, 0)
        self.assertEqual(len([unit for unit in player.units if unit.unit_type == UnitType.SOLDIER]), 1)

    def test_batch_soldiers_can_capture_city_without_siege_state(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        attacker, defender = engine.player_system.players
        for player in [attacker, defender]:
            for unit in list(player.units):
                engine.unit_system.remove_unit(unit, engine.map_tiles)

        city_center = HexCoord(0, 0)
        source = HexCoord(1, 0)
        for coord in [city_center, source]:
            engine.map_tiles[coord].terrain_type = TerrainType.LAND

        city = engine.city_system.create_city(defender, city_center, engine.map_tiles)
        defender.cities.append(city)
        soldier_a = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, source)
        soldier_b = engine.unit_system.create_unit(UnitType.SOLDIER, attacker, source)
        for soldier in [soldier_a, soldier_b]:
            engine.map_tiles[source].units.append(soldier)
            attacker.units.append(soldier)

        result = engine.execute_action_with_result(GameAction(
            player_id=attacker.id,
            action_type=ActionType.MOVE_UNIT,
            params={
                "unit_id": soldier_a.id,
                "unit_ids": [soldier_a.id, soldier_b.id],
                "target": [city_center.q, city_center.r]
            }
        ))
        self.assertTrue(result.success)
        self.assertEqual(city.owner, attacker)
        event_types = [event.event_type for event in result.events]
        self.assertIn("city_captured", event_types)
        self.assertNotIn("city_under_siege", event_types)

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

    def test_units_can_embark_and_land_to_sea_consumes_all_movement(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1 = engine.player_system.players[0]
        for unit in list(player1.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

        start = HexCoord(0, 0)
        ocean = HexCoord(1, 0)
        engine.map_tiles[start].terrain_type = TerrainType.LAND
        engine.map_tiles[ocean].terrain_type = TerrainType.OCEAN

        settler = engine.unit_system.create_unit(UnitType.SETTLER, player1, start)
        engine.map_tiles[start].units.append(settler)
        player1.units.append(settler)

        result = engine.execute_action_with_result(GameAction(
            player_id=player1.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": settler.id, "target": [ocean.q, ocean.r]}
        ))
        self.assertTrue(result.success)
        self.assertEqual(settler.position, ocean)
        self.assertEqual(settler.movement_points, 0)
        move_event = next(event for event in result.events if event.event_type == "unit_moved")
        self.assertEqual(move_event.data["from_terrain"], "land")
        self.assertEqual(move_event.data["to_terrain"], "ocean")
        self.assertEqual(move_event.data["remaining_movement"], 0)

    def test_sea_movement_is_halved(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))

        player1 = engine.player_system.players[0]
        for unit in list(player1.units):
            engine.unit_system.remove_unit(unit, engine.map_tiles)

        start = HexCoord(0, 0)
        adjacent_ocean = HexCoord(1, 0)
        far_ocean = HexCoord(2, 0)
        for coord in [start, adjacent_ocean, far_ocean]:
            engine.map_tiles[coord].terrain_type = TerrainType.OCEAN

        soldier = engine.unit_system.create_unit(UnitType.SOLDIER, player1, start)
        engine.map_tiles[start].units.append(soldier)
        player1.units.append(soldier)

        self.assertFalse(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": soldier.id, "target": [far_ocean.q, far_ocean.r]}
        )))
        self.assertEqual(soldier.position, start)

        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": soldier.id, "target": [adjacent_ocean.q, adjacent_ocean.r]}
        )))
        self.assertEqual(soldier.position, adjacent_ocean)
        self.assertEqual(soldier.movement_points, 0)

    def test_unit_cannot_reach_land_beyond_ocean_without_enough_sea_budget(self):
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

    def test_action_result_reports_failure_reasons(self):
        engine = GameEngine()
        self.assertTrue(engine.initialize_game(["玩家1", "玩家2"], map_seed=123))
        player1, player2 = engine.player_system.players

        result = engine.execute_action_with_result(GameAction(
            player_id=player2.id,
            action_type=ActionType.END_TURN,
            params={}
        ))
        self.assertFalse(result.success)
        self.assertIn("还没轮到", result.message)

        enemy_unit = player2.units[0]
        result = engine.execute_action_with_result(GameAction(
            player_id=player1.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": enemy_unit.id, "target": [enemy_unit.position.q, enemy_unit.position.r]}
        ))
        self.assertFalse(result.success)
        self.assertIn("只能移动自己的单位", result.message)

        own_unit = player1.units[0]
        result = engine.execute_action_with_result(GameAction(
            player_id=player1.id,
            action_type=ActionType.MOVE_UNIT,
            params={"unit_id": own_unit.id, "target": [99, 99]}
        ))
        self.assertFalse(result.success)
        self.assertIn("目标不在地图内", result.message)

        engine.map_tiles[own_unit.position].terrain_type = TerrainType.OCEAN
        result = engine.execute_action_with_result(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": own_unit.id}
        ))
        self.assertFalse(result.success)
        self.assertIn("只能在陆地建城", result.message)
        engine.map_tiles[own_unit.position].terrain_type = TerrainType.LAND

        self.assertTrue(engine.execute_action(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_CITY,
            params={"unit_id": own_unit.id}
        )))
        city = player1.cities[0]
        player1.gold = 0
        result = engine.execute_action_with_result(GameAction(
            player_id=player1.id,
            action_type=ActionType.BUILD_UNIT,
            params={"city_id": city.id, "unit_type": UnitType.SOLDIER.value}
        ))
        self.assertFalse(result.success)
        self.assertIn("金币不足", result.message)


if __name__ == "__main__":
    unittest.main()
