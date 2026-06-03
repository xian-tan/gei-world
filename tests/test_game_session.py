"""
游戏会话抽象测试。
"""

from src.game_engine import GameEngine
from src.game_session import LocalGameSession
from src.models import ActionType, GameAction


def test_local_game_session_starts_game_and_submits_actions():
    session = LocalGameSession()
    assert session.start_game(["玩家1", "玩家2"], map_seed=123)

    engine = session.engine
    player1, player2 = engine.player_system.players
    assert session.get_controlled_player() == player1
    assert session.can_player_act(player1.id)
    assert not session.can_player_act(player2.id)

    result = session.submit_action(GameAction(
        player_id=player1.id,
        action_type=ActionType.END_TURN,
        params={}
    ))
    assert result.success
    assert session.get_controlled_player() == player2


def test_local_game_session_uses_local_player_in_simultaneous_mode():
    session = LocalGameSession()
    assert session.start_game(["玩家1", "玩家2"], map_seed=123, turn_mode="simultaneous")

    player1, player2 = session.engine.player_system.players
    assert session.get_controlled_player(player2.id) == player2
    assert session.can_player_act(player1.id)
    assert session.can_player_act(player2.id)

    result = session.submit_action(GameAction(
        player_id=player2.id,
        action_type=ActionType.END_TURN,
        params={}
    ))
    assert result.success
    assert not session.can_player_act(player2.id)
    assert session.can_player_act(player1.id)


def test_local_game_session_can_wrap_loaded_engine():
    engine = GameEngine(turn_mode="simultaneous")
    assert engine.initialize_game(["玩家1", "玩家2"], map_seed=123, turn_mode="simultaneous")
    session = LocalGameSession(engine)

    player1 = engine.player_system.players[0]
    assert session.engine is engine
    assert session.get_turn_status()["mode"] == "simultaneous"
    assert session.get_visible_state(player1.id) is not None
    assert session.get_visible_tiles(player1.id)
    assert session.get_explored_tiles(player1.id)
