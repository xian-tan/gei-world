"""
实用工具函数
"""
import json
from typing import Dict, Any
from .models import GameState, Player, HexCoord, Tile, Unit, City


class GameStateSerializer:
    """游戏状态序列化器"""
    
    @staticmethod
    def serialize_game_state(game_state: GameState) -> str:
        """将游戏状态序列化为JSON字符串"""
        # 这里需要实现复杂的序列化逻辑
        # 当前先返回简单的占位符
        return json.dumps({
            "turn": game_state.turn,
            "current_player_id": game_state.current_player_id,
            "game_over": game_state.game_over,
            "player_count": len(game_state.players),
            "map_size": len(game_state.map_tiles)
        })
    
    @staticmethod
    def deserialize_game_state(data: str) -> GameState:
        """从JSON字符串反序列化游戏状态"""
        raise NotImplementedError(
            "GameStateSerializer 仅用于轻量状态摘要；完整存档加载请使用 GameSaveSystem。"
        )


def format_coordinates(coord: HexCoord) -> str:
    """格式化坐标显示"""
    return f"({coord.q}, {coord.r})"


def calculate_map_bounds(tiles: Dict[HexCoord, Tile]) -> Dict[str, int]:
    """计算地图边界"""
    if not tiles:
        return {"min_q": 0, "max_q": 0, "min_r": 0, "max_r": 0}
    
    coords = list(tiles.keys())
    min_q = min(coord.q for coord in coords)
    max_q = max(coord.q for coord in coords)
    min_r = min(coord.r for coord in coords)
    max_r = max(coord.r for coord in coords)
    
    return {
        "min_q": min_q,
        "max_q": max_q,
        "min_r": min_r,
        "max_r": max_r
    }


def get_player_statistics(player: Player) -> Dict[str, Any]:
    """获取玩家统计信息"""
    territory_count = sum(len(city.territory_tiles) for city in player.cities)
    
    unit_counts = {}
    for unit in player.units:
        unit_type = unit.unit_type.value
        unit_counts[unit_type] = unit_counts.get(unit_type, 0) + 1
    
    return {
        "name": player.name,
        "gold": player.gold,
        "cities": len(player.cities),
        "territory": territory_count,
        "units": unit_counts,
        "vision_tiles": len(player.vision_tiles)
    }