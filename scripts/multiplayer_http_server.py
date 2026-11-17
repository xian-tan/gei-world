#!/usr/bin/env python3
"""
多人 HTTP 服务启动脚本。等价于安装后的 gei-world-server。
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.http_multiplayer import main  # noqa: E402

if __name__ == "__main__":
    main()
