#!/usr/bin/env python3
"""
AI 对 AI 批量对战模拟，用于平衡数值与验证 AI 强度。

示例：
./.conda/bin/python scripts/simulate.py --games 50 --difficulty normal normal
"""
import argparse
import os
import random
import statistics
import sys
from typing import Dict, List, Sequence

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.game_engine import GameEngine
from src.systems.ai_system import AIManager
from src.systems.turn_system import TurnSystem


def simulate_game(seed: int, difficulties: Sequence[str] = ("normal", "normal"),
                  turn_mode: str = TurnSystem.MODE_SEQUENTIAL, max_turns: int = 100,
                  map_type: str = None, snapshot_turn: int = 30) -> Dict[str, object]:
    """运行一局全 AI 对局，返回胜者席位、回合数、指定回合城市数等统计。"""
    engine = GameEngine(turn_mode=turn_mode)
    names = [f"AI{index + 1}" for index in range(len(difficulties))]
    if not engine.initialize_game(names, map_seed=seed, turn_mode=turn_mode, map_type=map_type):
        raise RuntimeError(f"初始化失败: seed={seed}")
    manager = AIManager(seed=seed)
    players = engine.player_system.players
    for player, difficulty in zip(players, difficulties):
        manager.add_ai_player(player, difficulty=difficulty)

    order_rng = random.Random(seed)
    snapshot = None
    while not engine.game_over and engine.turn_system.current_turn <= max_turns:
        turn = engine.turn_system.current_turn
        if snapshot is None and turn >= snapshot_turn:
            snapshot = [len(player.cities) for player in players]
        actors = list(engine.turn_system.get_actionable_players())
        if turn_mode == TurnSystem.MODE_SIMULTANEOUS:
            # 同时回合中各玩家并行操作，模拟时每回合随机处理顺序，避免固定后手优势
            order_rng.shuffle(actors)
        if not actors:
            break
        for player in actors:
            if engine.game_over or engine.turn_system.current_turn != turn:
                break
            manager.play_turn(player.id, engine, engine.execute_action_with_result)

    if snapshot is None:
        snapshot = [len(player.cities) for player in players]
    winner_index = players.index(engine.winner) if engine.winner in players else None
    return {
        "seed": seed,
        "winner": winner_index,
        "turns": engine.turn_system.current_turn,
        "game_over": engine.game_over,
        "cities_at_snapshot": snapshot,
        "scores": [engine.calculate_score(player) for player in players],
    }


def summarize(results: List[Dict[str, object]], seats: int) -> Dict[str, object]:
    wins = [sum(1 for r in results if r["winner"] == seat) for seat in range(seats)]
    decided = sum(wins)
    return {
        "games": len(results),
        "wins": wins,
        "draws": len(results) - decided,
        "first_seat_win_rate": wins[0] / decided if decided else None,
        "avg_turns": statistics.mean(r["turns"] for r in results),
        "avg_cities_at_snapshot": [
            statistics.mean(r["cities_at_snapshot"][seat] for r in results) for seat in range(seats)
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="AI 对 AI 批量模拟")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--difficulty", nargs="+", default=["normal", "normal"])
    parser.add_argument("--turn-mode", choices=sorted(TurnSystem.SUPPORTED_MODES), default=TurnSystem.MODE_SEQUENTIAL)
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--map-type", default=None)
    parser.add_argument("--seed-offset", type=int, default=0)
    args = parser.parse_args()

    results = [
        simulate_game(args.seed_offset + index, args.difficulty, args.turn_mode, args.max_turns, args.map_type)
        for index in range(args.games)
    ]
    summary = summarize(results, len(args.difficulty))
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
