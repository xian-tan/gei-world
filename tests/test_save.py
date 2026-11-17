"""
存档系统测试。
"""
import os
import tempfile
from pathlib import Path

from src.game_engine import GameEngine
from src.systems.save_system import GameSaveSystem


def test_save_system_uses_environment_save_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        old_value = os.environ.get("GEI_WORLD_SAVE_DIR")
        os.environ["GEI_WORLD_SAVE_DIR"] = tmp_dir
        try:
            save_system = GameSaveSystem()
            assert save_system.save_directory == Path(tmp_dir)
            assert save_system.save_directory.exists()
        finally:
            if old_value is None:
                os.environ.pop("GEI_WORLD_SAVE_DIR", None)
            else:
                os.environ["GEI_WORLD_SAVE_DIR"] = old_value


def test_save_and_list_saves():
    engine = GameEngine()
    assert engine.initialize_game(["测试玩家1", "测试玩家2"], map_seed=456)
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_system = GameSaveSystem(tmp_dir)
        assert save_system.save_game(engine, "test_save")
        saves = save_system.list_saves()
        assert [save["name"] for save in saves] == ["test_save"]
        assert saves[0]["players"] == ["测试玩家1", "测试玩家2"]


def test_save_load_preserves_map_type_and_radius():
    engine = GameEngine()
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=9, map_type="pangaea", map_size="small")
    with tempfile.TemporaryDirectory() as tmp_dir:
        save_system = GameSaveSystem(tmp_dir)
        assert save_system.save_game(engine, "map")
        loaded = save_system.load_game("map")
    assert loaded.map_system.generator_type == "pangaea"
    assert loaded.map_system.radius == 8
    assert len(loaded.map_tiles) == len(engine.map_tiles)
