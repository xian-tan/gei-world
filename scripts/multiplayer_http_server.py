#!/usr/bin/env python3
"""
多人 HTTP 服务启动脚本。
"""
import argparse
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.http_multiplayer import run_http_server


def main():
    parser = argparse.ArgumentParser(description="启动 gei-world 多人 HTTP 服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    args = parser.parse_args()
    run_http_server(args.host, args.port)


if __name__ == "__main__":
    main()
