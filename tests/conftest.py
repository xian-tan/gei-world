"""
测试全局配置：把存档与多人身份文件重定向到临时目录，避免污染本机用户数据。
"""
import os
import tempfile

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(autouse=True, scope="session")
def isolated_user_data():
    with tempfile.TemporaryDirectory() as tmp_dir:
        old = os.environ.get("GEI_WORLD_SAVE_DIR")
        os.environ["GEI_WORLD_SAVE_DIR"] = os.path.join(tmp_dir, "saves")
        try:
            yield tmp_dir
        finally:
            if old is None:
                os.environ.pop("GEI_WORLD_SAVE_DIR", None)
            else:
                os.environ["GEI_WORLD_SAVE_DIR"] = old
