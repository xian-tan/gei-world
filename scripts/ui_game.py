#!/usr/bin/env python3
"""
游戏启动脚本（PyInstaller 打包入口）。等价于 python -m ui。
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ui.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
