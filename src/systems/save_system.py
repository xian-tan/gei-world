"""
游戏保存和加载系统
"""
import json
import pickle
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from ..models import GameState, Player, HexCoord, Tile, Unit, City, TerrainType, UnitType
from ..game_engine import GameEngine


class GameSaveSystem:
    """游戏保存系统"""
    
    def __init__(self, save_directory: str = "saves"):
        self.save_directory = Path(save_directory)
        self.save_directory.mkdir(exist_ok=True)
    
    def save_game(self, engine: GameEngine, save_name: str) -> bool:
        """保存游戏状态"""
        try:
            game_data = self._serialize_game_state(engine)
            
            # 添加元数据
            save_data = {
                "metadata": {
                    "save_name": save_name,
                    "timestamp": datetime.now().isoformat(),
                    "version": "0.1.0",
                    "turn": engine.turn_system.current_turn,
                    "players": [p.name for p in engine.player_system.players]
                },
                "game_data": game_data
            }
            
            # 保存为JSON文件
            save_file = self.save_directory / f"{save_name}.json"
            with open(save_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            print(f"游戏已保存到: {save_file}")
            return True
            
        except Exception as e:
            print(f"保存游戏失败: {e}")
            return False
    
    def load_game(self, save_name: str) -> Optional[GameEngine]:
        """加载游戏状态"""
        try:
            save_file = self.save_directory / f"{save_name}.json"
            if not save_file.exists():
                print(f"保存文件不存在: {save_file}")
                return None
            
            with open(save_file, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            # 验证保存文件格式
            if "metadata" not in save_data or "game_data" not in save_data:
                print("无效的保存文件格式")
                return None
            
            # 重建游戏状态
            engine = self._deserialize_game_state(save_data["game_data"])
            
            if engine:
                print(f"游戏已从 {save_file} 加载")
                metadata = save_data["metadata"]
                print(f"保存时间: {metadata['timestamp']}")
                print(f"回合数: {metadata['turn']}")
                print(f"玩家: {', '.join(metadata['players'])}")
            
            return engine
            
        except Exception as e:
            print(f"加载游戏失败: {e}")
            return None
    
    def list_saves(self) -> list:
        """列出所有保存文件"""
        saves = []
        for save_file in self.save_directory.glob("*.json"):
            try:
                with open(save_file, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)
                
                if "metadata" in save_data:
                    metadata = save_data["metadata"]
                    saves.append({
                        "name": save_file.stem,
                        "timestamp": metadata.get("timestamp", "未知"),
                        "turn": metadata.get("turn", 0),
                        "players": metadata.get("players", [])
                    })
            except:
                # 忽略损坏的保存文件
                pass
        
        return sorted(saves, key=lambda x: x["timestamp"], reverse=True)
    
    def _serialize_game_state(self, engine: GameEngine) -> Dict[str, Any]:
        """序列化游戏状态"""
        # 简化的序列化实现
        # 实际项目中可能需要更复杂的序列化逻辑
        
        # 序列化地图
        map_data = {}
        for coord, tile in engine.map_tiles.items():
            key = f"{coord.q},{coord.r}"
            map_data[key] = {
                "terrain": tile.terrain_type.value,
                "owner_id": tile.owner.id if tile.owner else None,
                "has_city": tile.city is not None,
                "unit_count": len(tile.units)
            }
        
        # 序列化玩家
        players_data = []
        for player in engine.player_system.players:
            player_data = {
                "id": player.id,
                "name": player.name,
                "gold": player.gold,
                "cities": [self._serialize_city(city) for city in player.cities],
                "units": [self._serialize_unit(unit) for unit in player.units]
            }
            players_data.append(player_data)
        
        return {
            "map_config": {
                "radius": engine.map_system.radius,
                "generator_type": engine.map_system.generator_type
            },
            "map_data": map_data,
            "players": players_data,
            "turn": engine.turn_system.current_turn,
            "current_player_index": engine.turn_system.current_player_index,
            "game_started": engine.game_started,
            "game_over": engine.game_over
        }
    
    def _serialize_city(self, city: City) -> Dict[str, Any]:
        """序列化城市"""
        return {
            "id": city.id,
            "center": f"{city.center_tile.q},{city.center_tile.r}",
            "territory": [f"{coord.q},{coord.r}" for coord in city.territory_tiles],
            "production_queue": [unit_type.value for unit_type in city.production_queue]
        }
    
    def _serialize_unit(self, unit: Unit) -> Dict[str, Any]:
        """序列化单位"""
        return {
            "id": unit.id,
            "type": unit.unit_type.value,
            "position": f"{unit.position.q},{unit.position.r}",
            "movement_points": unit.movement_points,
            "max_movement_points": unit.max_movement_points,
            "vision_range": unit.vision_range
        }
    
    def _deserialize_game_state(self, game_data: Dict[str, Any]) -> Optional[GameEngine]:
        """反序列化游戏状态"""
        # 这是一个简化的实现
        # 实际项目中需要完整重建所有游戏对象
        try:
            # 创建新的游戏引擎
            engine = GameEngine()
            
            # 这里需要完整实现反序列化逻辑
            # 当前只是一个占位符
            print("注意：完整的游戏加载功能尚未实现")
            print("这需要复杂的对象重建逻辑")
            
            return None  # 暂时返回None，表示未实现
            
        except Exception as e:
            print(f"反序列化失败: {e}")
            return None
