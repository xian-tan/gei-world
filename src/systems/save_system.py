"""
游戏保存和加载系统
"""
import json
import os
import platform
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .. import __version__
from ..models import GameState, Player, HexCoord, Tile, Unit, City, TerrainType, UnitType
from ..game_engine import GameEngine


class GameSaveSystem:
    """游戏保存系统"""
    
    def __init__(self, save_directory: Optional[str] = None):
        self.save_directory = Path(save_directory) if save_directory else self.get_default_save_directory()
        self.save_directory.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def get_default_save_directory() -> Path:
        """获取发布版默认存档目录，可用 GEI_WORLD_SAVE_DIR 覆盖。"""
        env_dir = os.environ.get("GEI_WORLD_SAVE_DIR")
        if env_dir:
            return Path(env_dir).expanduser()
        system = platform.system()
        if system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "gei-world" / "saves"
        if system == "Windows":
            base_dir = os.environ.get("APPDATA")
            if base_dir:
                return Path(base_dir) / "gei-world" / "saves"
            return Path.home() / "AppData" / "Roaming" / "gei-world" / "saves"
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            return Path(xdg_data_home) / "gei-world" / "saves"
        return Path.home() / ".local" / "share" / "gei-world" / "saves"
    
    def save_game(self, engine: GameEngine, save_name: str) -> bool:
        """保存游戏状态"""
        try:
            game_data = self._serialize_game_state(engine)
            
            # 添加元数据
            save_data = {
                "metadata": {
                    "save_name": save_name,
                    "timestamp": datetime.now().isoformat(),
                    "version": __version__,
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
                "units": [self._serialize_unit(unit) for unit in player.units],
                "explored_tiles": [
                    f"{coord.q},{coord.r}"
                    for coord in getattr(player, "explored_tiles", set())
                ]
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
            "game_over": engine.game_over,
            "winner_id": engine.winner.id if engine.winner else None,
            "ai_player_configs": getattr(engine, "ai_player_configs", {})
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
            "vision_range": unit.vision_range,
            "quantity": unit.quantity
        }
    
    def _parse_coord(self, value: str) -> HexCoord:
        """解析保存文件中的坐标。"""
        q, r = value.split(",")
        return HexCoord(int(q), int(r))
    
    def _deserialize_game_state(self, game_data: Dict[str, Any]) -> Optional[GameEngine]:
        """反序列化游戏状态"""
        try:
            engine = GameEngine()
            
            map_config = game_data.get("map_config", {})
            engine.map_system.radius = map_config.get("radius", engine.map_system.radius)
            engine.map_system.generator_type = map_config.get(
                "generator_type", engine.map_system.generator_type
            )
            
            # 重建玩家
            players = []
            player_by_id = {}
            for player_data in game_data.get("players", []):
                player = Player(
                    id=player_data["id"],
                    name=player_data["name"],
                    gold=player_data["gold"],
                    explored_tiles={
                        self._parse_coord(coord_text)
                        for coord_text in player_data.get("explored_tiles", [])
                    }
                )
                players.append(player)
                player_by_id[player.id] = player
            
            # 重建地图
            map_tiles = {}
            for coord_text, tile_data in game_data.get("map_data", {}).items():
                coord = self._parse_coord(coord_text)
                owner_id = tile_data.get("owner_id")
                tile = Tile(
                    coord=coord,
                    terrain_type=TerrainType(tile_data["terrain"]),
                    owner=player_by_id.get(owner_id)
                )
                map_tiles[coord] = tile
            
            # 重建城市
            for player_data in game_data.get("players", []):
                owner = player_by_id[player_data["id"]]
                for city_data in player_data.get("cities", []):
                    center = self._parse_coord(city_data["center"])
                    territory = {
                        self._parse_coord(coord_text)
                        for coord_text in city_data.get("territory", [])
                    }
                    city = City(
                        id=city_data["id"],
                        owner=owner,
                        center_tile=center,
                        territory_tiles=territory,
                        production_queue=[
                            UnitType(unit_type)
                            for unit_type in city_data.get("production_queue", [])
                        ]
                    )
                    owner.cities.append(city)
                    engine.city_system.cities.append(city)
                    
                    center_tile = map_tiles.get(center)
                    if center_tile:
                        center_tile.city = city
                    for coord in territory:
                        tile = map_tiles.get(coord)
                        if tile:
                            tile.owner = owner
            
            # 重建单位
            for player_data in game_data.get("players", []):
                owner = player_by_id[player_data["id"]]
                for unit_data in player_data.get("units", []):
                    position = self._parse_coord(unit_data["position"])
                    unit = Unit(
                        id=unit_data["id"],
                        owner=owner,
                        position=position,
                        unit_type=UnitType(unit_data["type"]),
                        movement_points=unit_data["movement_points"],
                        max_movement_points=unit_data["max_movement_points"],
                        vision_range=unit_data["vision_range"],
                        quantity=unit_data.get("quantity", 1)
                    )
                    owner.units.append(unit)
                    engine.unit_system.units.append(unit)
                    tile = map_tiles.get(position)
                    if tile:
                        tile.units.append(unit)
            
            engine.unit_system.merge_compatible_stacks(map_tiles)
            
            engine.map_tiles = map_tiles
            engine.map_system.tiles = map_tiles
            engine.player_system.players = players
            engine.turn_system.players = players
            engine.turn_system.current_turn = game_data.get("turn", 1)
            engine.turn_system.turn_number = game_data.get("turn", 1)
            engine.turn_system.current_player_index = game_data.get("current_player_index", 0)
            engine.game_started = game_data.get("game_started", True)
            engine.game_over = game_data.get("game_over", False)
            winner_id = game_data.get("winner_id")
            engine.winner = player_by_id.get(winner_id) if winner_id else (
                engine.turn_system.get_winner() if engine.game_over else None
            )
            engine.ai_player_configs = game_data.get("ai_player_configs", {})
            
            engine.vision_system.set_players(players)
            for player in players:
                saved_explored_tiles = set(player.explored_tiles)
                engine.vision_system.update_player_vision(player, map_tiles)
                player.explored_tiles.update(saved_explored_tiles)
            
            return engine
            
        except Exception as e:
            print(f"反序列化失败: {e}")
            return None
