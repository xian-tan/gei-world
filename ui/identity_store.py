"""
多人身份记忆：保存"服务地址 + 房间码 → 本机客户端身份"，重连时无需手抄客户端 ID。
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

from src.systems.save_system import GameSaveSystem


def _key(base_url: str, room_id: str, player_name: str = "") -> str:
    return f"{base_url.rstrip('/')}|{room_id.strip().upper()}|{player_name.strip()}"


class IdentityStore:
    """以 JSON 文件持久化的多人身份表。"""

    def __init__(self, path: Optional[Path] = None):
        if path is None:
            override = os.environ.get("GEI_WORLD_IDENTITY_FILE")
            path = Path(override) if override else GameSaveSystem.get_default_save_directory().parent / "multiplayer_identities.json"
        self.path = Path(path)

    def _load(self) -> Dict[str, Dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: Dict[str, Dict]):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def remember(self, base_url: str, room_id: str, client_id: str, player_name: str = ""):
        data = self._load()
        data[_key(base_url, room_id, player_name)] = {
            "base_url": base_url.rstrip('/'), "room_id": room_id.strip().upper(), "client_id": client_id,
            "player_name": player_name, "updated_at": time.time(),
        }
        if len(data) > 30:
            for stale in sorted(data, key=lambda k: data[k].get("updated_at", 0))[:-30]:
                data.pop(stale, None)
        self._save(data)

    def lookup(self, base_url: str, room_id: str, player_name: str = "") -> Optional[Dict]:
        """优先按玩家名精确匹配；未提供或未找到时返回该房间最近一次使用的身份。"""
        data = self._load()
        if player_name and _key(base_url, room_id, player_name) in data:
            return data[_key(base_url, room_id, player_name)]
        prefix = f"{base_url.rstrip('/')}|{room_id.strip().upper()}|"
        matches = [value for key, value in data.items() if key.startswith(prefix)]
        return max(matches, key=lambda item: item.get("updated_at", 0)) if matches else None

    def latest(self) -> Optional[Dict]:
        data = self._load()
        if not data:
            return None
        return max(data.values(), key=lambda item: item.get("updated_at", 0))
