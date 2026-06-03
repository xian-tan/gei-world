#!/usr/bin/env python3
"""
本机双客户端多人调试入口。

不启动真实网络；用两个 NetworkGameSession 驱动同一个进程内 MultiplayerServer 房间。
"""
import argparse
import os
import sys
from typing import Dict, List

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.game_session import NetworkGameSession
from src.models import ActionType, GameAction, UnitType
from src.multiplayer_server import MultiplayerServer
from src.systems.turn_system import TurnSystem


PLAYER_NAMES = ["玩家1", "玩家2"]


def _format_result(prefix: str, result) -> str:
    status = "成功" if result.success else "失败"
    return f"{prefix}: {status} - {result.message}"


def _build_first_city(session: NetworkGameSession):
    """让当前 session 对应玩家用首个移民建城。"""
    player = session.get_controlled_player()
    if not player:
        raise RuntimeError("当前 session 未绑定玩家")
    settler = next((unit for unit in player.units if unit.unit_type == UnitType.SETTLER), None)
    if not settler:
        raise RuntimeError(f"{player.name} 没有可建城的移民")
    return session.submit_action(GameAction(
        player_id=player.id,
        action_type=ActionType.BUILD_CITY,
        params={"unit_id": settler.id}
    ))


def _end_turn(session: NetworkGameSession):
    player = session.get_controlled_player()
    if not player:
        raise RuntimeError("当前 session 未绑定玩家")
    return session.submit_action(GameAction(
        player_id=player.id,
        action_type=ActionType.END_TURN,
        params={}
    ))


def _run_player_opening(session: NetworkGameSession, label: str, log: List[str]):
    build_result = _build_first_city(session)
    log.append(_format_result(f"{label} 建城", build_result))
    if not build_result.success:
        raise AssertionError(build_result.message)
    end_result = _end_turn(session)
    log.append(_format_result(f"{label} 结束回合", end_result))
    if not end_result.success:
        raise AssertionError(end_result.message)


def run_demo(turn_mode: str = TurnSystem.MODE_SIMULTANEOUS, map_seed: int = 123) -> Dict[str, object]:
    """运行一轮本机双客户端多人流程，返回摘要。"""
    if turn_mode not in TurnSystem.SUPPORTED_MODES:
        raise ValueError(f"未知回合模式: {turn_mode}")

    server = MultiplayerServer()
    created = server.create_room(PLAYER_NAMES[0], max_players=2, turn_mode=turn_mode, map_seed=map_seed)
    room_id = created["room"]["room_id"]
    host_client_id = created["client_id"]
    joined = server.join_room(room_id, PLAYER_NAMES[1])
    guest_client_id = joined["client_id"]

    host_session = NetworkGameSession(server, room_id, host_client_id)
    guest_session = NetworkGameSession(server, room_id, guest_client_id)
    if not host_session.start_game(turn_mode=turn_mode):
        raise RuntimeError("房间启动失败")

    host_player = host_session.get_controlled_player()
    guest_player = guest_session.get_controlled_player()
    if not host_player or not guest_player:
        raise RuntimeError("玩家席位绑定失败")

    log = [
        f"房间: {room_id}",
        f"模式: {turn_mode}",
        f"客户端: {host_client_id}->{host_player.id}, {guest_client_id}->{guest_player.id}",
    ]

    spoof_result = host_session.submit_action(GameAction(
        player_id=guest_player.id,
        action_type=ActionType.END_TURN,
        params={}
    ))
    log.append(_format_result("伪造对方行动", spoof_result))
    if spoof_result.success:
        raise AssertionError("伪造对方行动不应成功")

    if turn_mode == TurnSystem.MODE_SEQUENTIAL:
        _run_player_opening(host_session, host_player.name, log)
        _run_player_opening(guest_session, guest_player.name, log)
    else:
        host_build = _build_first_city(host_session)
        guest_build = _build_first_city(guest_session)
        log.append(_format_result(f"{host_player.name} 建城", host_build))
        log.append(_format_result(f"{guest_player.name} 建城", guest_build))
        if not host_build.success or not guest_build.success:
            raise AssertionError("同时回合建城失败")
        host_end = _end_turn(host_session)
        guest_end = _end_turn(guest_session)
        log.append(_format_result(f"{host_player.name} 结束回合", host_end))
        log.append(_format_result(f"{guest_player.name} 结束回合", guest_end))
        if not host_end.success or not guest_end.success:
            raise AssertionError("同时回合结束失败")

    host_view = host_session.get_player_view()["view"]
    guest_view = guest_session.get_player_view()["view"]
    engine = server.get_room_engine(room_id)
    summary = {
        "room_id": room_id,
        "turn_mode": turn_mode,
        "turn": engine.turn_system.current_turn,
        "host_player_id": host_player.id,
        "guest_player_id": guest_player.id,
        "host_view_player_id": host_view["player_id"],
        "guest_view_player_id": guest_view["player_id"],
        "host_city_count": len(host_player.cities),
        "guest_city_count": len(guest_player.cities),
        "log": log,
    }
    log.append(f"当前回合: {summary['turn']}")
    log.append(f"城市数量: {host_player.name}={summary['host_city_count']}, {guest_player.name}={summary['guest_city_count']}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="运行本机双客户端多人调试流程")
    parser.add_argument(
        "--turn-mode",
        choices=[TurnSystem.MODE_SEQUENTIAL, TurnSystem.MODE_SIMULTANEOUS, "both"],
        default="both",
        help="回合模式，默认同时运行两种模式"
    )
    parser.add_argument("--seed", type=int, default=123, help="地图种子")
    args = parser.parse_args()

    modes = [TurnSystem.MODE_SEQUENTIAL, TurnSystem.MODE_SIMULTANEOUS] if args.turn_mode == "both" else [args.turn_mode]
    for mode in modes:
        summary = run_demo(mode, args.seed)
        print("\n" + "=" * 50)
        for line in summary["log"]:
            print(line)
        print("✓ 本机双客户端流程完成")


if __name__ == "__main__":
    main()
