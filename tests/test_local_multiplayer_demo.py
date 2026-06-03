"""
本机双客户端多人调试脚本测试。
"""

from scripts.local_multiplayer_demo import run_demo
from src.systems.turn_system import TurnSystem


def test_local_multiplayer_demo_sequential_flow():
    summary = run_demo(TurnSystem.MODE_SEQUENTIAL, map_seed=123)

    assert summary["turn_mode"] == "sequential"
    assert summary["turn"] == 2
    assert summary["host_player_id"] == "player_0"
    assert summary["guest_player_id"] == "player_1"
    assert summary["host_view_player_id"] == "player_0"
    assert summary["guest_view_player_id"] == "player_1"
    assert summary["host_city_count"] == 1
    assert summary["guest_city_count"] == 1
    assert any("伪造对方行动: 失败" in line for line in summary["log"])


def test_local_multiplayer_demo_simultaneous_flow():
    summary = run_demo(TurnSystem.MODE_SIMULTANEOUS, map_seed=123)

    assert summary["turn_mode"] == "simultaneous"
    assert summary["turn"] == 2
    assert summary["host_player_id"] == "player_0"
    assert summary["guest_player_id"] == "player_1"
    assert summary["host_city_count"] == 1
    assert summary["guest_city_count"] == 1
    assert any("玩家1 建城: 成功" in line for line in summary["log"])
    assert any("玩家2 建城: 成功" in line for line in summary["log"])
