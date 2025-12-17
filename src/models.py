"""
核心数据结构定义
"""
from dataclasses import dataclass
from typing import List, Set, Optional, Dict, Any
from enum import Enum
import uuid


class TerrainType(Enum):
    LAND = "land"
    OCEAN = "ocean"


class UnitType(Enum):
    SETTLER = "settler"
    SOLDIER = "soldier"


class ActionType(Enum):
    MOVE_UNIT = "move_unit"
    BUILD_CITY = "build_city" 
    BUILD_UNIT = "build_unit"
    END_TURN = "end_turn"


@dataclass
class HexCoord:
    """六边形轴向坐标"""
    q: int
    r: int
    
    def __hash__(self):
        return hash((self.q, self.r))
    
    def __eq__(self, other):
        if not isinstance(other, HexCoord):
            return False
        return self.q == other.q and self.r == other.r
    
    def neighbors(self) -> List['HexCoord']:
        """获取相邻六边形坐标"""
        directions = [
            (1, 0), (1, -1), (0, -1),
            (-1, 0), (-1, 1), (0, 1)
        ]
        return [HexCoord(self.q + dq, self.r + dr) for dq, dr in directions]
    
    def distance_to(self, other: 'HexCoord') -> int:
        """计算到另一个坐标的距离"""
        return (abs(self.q - other.q) + 
                abs(self.q + self.r - other.q - other.r) + 
                abs(self.r - other.r)) // 2


@dataclass
class Tile:
    """地块"""
    coord: HexCoord
    terrain_type: TerrainType
    owner: Optional['Player'] = None
    city: Optional['City'] = None
    units: List['Unit'] = None
    
    def __post_init__(self):
        if self.units is None:
            self.units = []


@dataclass  
class Unit:
    """单位"""
    id: str
    owner: 'Player'
    position: HexCoord
    unit_type: UnitType
    movement_points: int
    max_movement_points: int
    vision_range: int
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class City:
    """城市"""
    id: str
    owner: 'Player'
    center_tile: HexCoord
    territory_tiles: Set[HexCoord]
    production_queue: List[UnitType] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.production_queue is None:
            self.production_queue = []
        if not self.territory_tiles:
            self.territory_tiles = set()


@dataclass
class Player:
    """玩家"""
    id: str
    name: str
    gold: int
    cities: List[City] = None
    units: List[Unit] = None
    vision_tiles: Set[HexCoord] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.cities is None:
            self.cities = []
        if self.units is None:
            self.units = []
        if self.vision_tiles is None:
            self.vision_tiles = set()


@dataclass
class GameAction:
    """游戏行动"""
    player_id: str
    action_type: ActionType
    params: Dict[str, Any]


@dataclass
class GameState:
    """游戏状态快照"""
    turn: int
    current_player_id: str
    players: List[Player]
    map_tiles: Dict[HexCoord, Tile]
    game_over: bool = False
    winner: Optional[Player] = None
