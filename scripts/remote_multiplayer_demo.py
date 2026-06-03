#!/usr/bin/env python3
"""
HTTP 远端多人调试入口。

需要先启动：
./.conda/bin/python scripts/multiplayer_http_server.py --host 127.0.0.1 --port 8000
"""
import argparse
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.game_session import HTTPNetworkSession
from src.http_multiplayer import HTTPMultiplayerClient
from src.models import ActionType, GameAction
from src.systems.turn_system import TurnSystem


def run_demo(base_url: str, turn_mode: str = TurnSystem.MODE_SIMULTANEOUS, map_seed: int = 123,
             room_id: str = None, player_name: str = "玩家2"):
    client = HTTPMultiplayerClient(base_url)
    if room_id:
        joined = client.join_room(room_id, player_name)
        if not joined.get("success"):
            raise RuntimeError(joined.get("message", "加入房间失败"))
        guest_client_id = joined["client_id"]
        start_response = client.start_room(room_id, turn_mode=turn_mode)
        if not start_response.get("success"):
            raise RuntimeError(start_response.get("message", "开始房间失败"))
        guest_session = HTTPNetworkSession(client, room_id, guest_client_id)
        guest_player = guest_session.get_controlled_player()
        log = [
            f"房间: {room_id}",
            f"模式: {turn_mode}",
            f"加入客户端: {guest_client_id}->{guest_player.id}",
        ]
        return {"room_id": room_id, "turn": guest_session.get_player_view()["view"]["turn"], "log": log}

    created = client.create_room("玩家1", max_players=2, turn_mode=turn_mode, map_seed=map_seed)
    if not created.get("success"):
        raise RuntimeError(created.get("message", "创建房间失败"))
    room_id = created["room"]["room_id"]
    host_client_id = created["client_id"]
    joined = client.join_room(room_id, "玩家2")
    if not joined.get("success"):
        raise RuntimeError(joined.get("message", "加入房间失败"))
    guest_client_id = joined["client_id"]

    host_session = HTTPNetworkSession(client, room_id, host_client_id)
    guest_session = HTTPNetworkSession(client, room_id, guest_client_id)
    if not host_session.start_game(turn_mode=turn_mode):
        raise RuntimeError("开始房间失败")

    host_player = host_session.get_controlled_player()
    guest_player = guest_session.get_controlled_player()
    log = [
        f"房间: {room_id}",
        f"模式: {turn_mode}",
        f"客户端: {host_client_id}->{host_player.id}, {guest_client_id}->{guest_player.id}",
    ]

    spoofed = host_session.submit_action(GameAction(
        player_id=guest_player.id,
        action_type=ActionType.END_TURN,
        params={}
    ))
    log.append(f"伪造对方行动: {'成功' if spoofed.success else '失败'} - {spoofed.message}")
    if spoofed.success:
        raise AssertionError("伪造对方行动不应成功")

    host_end = host_session.submit_action(GameAction(
        player_id=host_player.id,
        action_type=ActionType.END_TURN,
        params={}
    ))
    guest_end = guest_session.submit_action(GameAction(
        player_id=guest_player.id,
        action_type=ActionType.END_TURN,
        params={}
    ))
    log.append(f"玩家1结束: {'成功' if host_end.success else '失败'} - {host_end.message}")
    log.append(f"玩家2结束: {'成功' if guest_end.success else '失败'} - {guest_end.message}")

    host_view = host_session.get_player_view()["view"]
    guest_view = guest_session.get_player_view()["view"]
    summary = {
        "room_id": room_id,
        "turn": host_view["turn"],
        "host_player_id": host_view["player_id"],
        "guest_player_id": guest_view["player_id"],
        "log": log,
    }
    log.append(f"当前回合: {summary['turn']}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="运行 HTTP 远端多人调试流程")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="多人 HTTP 服务地址")
    parser.add_argument("--turn-mode", choices=[TurnSystem.MODE_SEQUENTIAL, TurnSystem.MODE_SIMULTANEOUS], default=TurnSystem.MODE_SIMULTANEOUS)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--room-id", default=None, help="加入已有房间；不填则创建调试双人房")
    parser.add_argument("--player-name", default="玩家2", help="加入已有房间时使用的玩家名")
    args = parser.parse_args()
    summary = run_demo(args.url, args.turn_mode, args.seed, args.room_id, args.player_name)
    for line in summary["log"]:
        print(line)
    print("✓ HTTP 远端多人流程完成")


if __name__ == "__main__":
    main()
