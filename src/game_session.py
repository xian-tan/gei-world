"""
游戏会话抽象。

该层用于把 UI 与具体的本地 GameEngine 实例解耦，后续可用同一接口接入网络会话。
"""
from typing import Dict, List, Optional, Protocol, Set

from .game_engine import GameEngine
from .models import ActionResult, City, GameAction, GameState, HexCoord, Player, TerrainType, Tile, Unit, UnitType
from .network_protocol import deserialize_action_result, parse_coord, serialize_action
from .systems.turn_system import TurnSystem


class GameSessionClient(Protocol):
    """UI/网络层面向的游戏会话接口。"""

    @property
    def engine(self) -> GameEngine:
        """当前会话使用的本地引擎；网络会话可返回只读镜像。"""
        ...

    def start_game(self, player_names: List[str], map_seed: int = None,
                   turn_mode: str = TurnSystem.MODE_SEQUENTIAL) -> bool:
        """开始一局游戏。"""
        ...

    def submit_action(self, action: GameAction) -> ActionResult:
        """提交玩家行动。"""
        ...

    def get_turn_status(self) -> Dict[str, object]:
        """获取回合状态。"""
        ...

    def get_controlled_player(self, local_player_id: str = None) -> Optional[Player]:
        """获取当前客户端视角下控制/查看的玩家。"""
        ...

    def can_player_act(self, player_id: str) -> bool:
        """判断玩家当前是否可提交行动。"""
        ...

    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        """获取玩家可见状态。"""
        ...

    def get_visible_tiles(self, player_id: str) -> Set[HexCoord]:
        """获取玩家当前可见地块集合。"""
        ...

    def get_explored_tiles(self, player_id: str) -> Set[HexCoord]:
        """获取玩家已探索地块集合。"""
        ...


class LocalGameSession:
    """本地单机会话，直接包装 GameEngine。"""

    def __init__(self, engine: GameEngine = None):
        self._engine = engine or GameEngine()

    @property
    def engine(self) -> GameEngine:
        return self._engine

    def replace_engine(self, engine: GameEngine):
        """替换当前引擎，主要用于加载存档。"""
        self._engine = engine

    def start_game(self, player_names: List[str], map_seed: int = None,
                   turn_mode: str = TurnSystem.MODE_SEQUENTIAL) -> bool:
        new_engine = GameEngine(turn_mode=turn_mode)
        if not new_engine.initialize_game(player_names, map_seed, turn_mode=turn_mode):
            return False
        self._engine = new_engine
        return True

    def submit_action(self, action: GameAction) -> ActionResult:
        return self._engine.execute_action_with_result(action)

    def get_turn_status(self) -> Dict[str, object]:
        return self._engine.turn_system.get_turn_status()

    def get_controlled_player(self, local_player_id: str = None) -> Optional[Player]:
        turn_system = self._engine.turn_system
        if turn_system.mode == TurnSystem.MODE_SIMULTANEOUS and local_player_id:
            player = self._engine.player_system.get_player_by_id(local_player_id)
            if player:
                return player
        return self._engine.get_current_player()

    def can_player_act(self, player_id: str) -> bool:
        return self._engine.turn_system.can_player_act(player_id)

    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        return self._engine.get_visible_state(player_id)

    def get_visible_tiles(self, player_id: str) -> Set[HexCoord]:
        return self._engine.vision_system.get_visible_tiles(player_id)

    def get_explored_tiles(self, player_id: str) -> Set[HexCoord]:
        return self._engine.vision_system.get_explored_tiles(player_id)


class NetworkGameSession:
    """进程内网络会话骨架，通过 MultiplayerServer 访问服务端权威引擎。"""

    def __init__(self, server, room_id: str, client_id: str):
        self.server = server
        self.room_id = room_id
        self.client_id = client_id

    @property
    def engine(self) -> GameEngine:
        """当前进程内服务端权威引擎；真实网络版可替换为只读镜像。"""
        engine = self.server.get_room_engine(self.room_id)
        return engine or GameEngine()

    @property
    def player_id(self) -> Optional[str]:
        """当前客户端绑定的玩家 ID。"""
        return self.server.get_client_player_id(self.room_id, self.client_id)

    def start_game(self, player_names: List[str] = None, map_seed: int = None,
                   turn_mode: str = TurnSystem.MODE_SIMULTANEOUS) -> bool:
        """启动当前房间。player_names 由房间席位决定，参数仅用于兼容接口。"""
        response = self.server.start_room(self.room_id, map_seed=map_seed, turn_mode=turn_mode)
        return bool(response.get("success"))

    def submit_action(self, action: GameAction) -> ActionResult:
        response = self.server.submit_action(self.room_id, self.client_id, serialize_action(action))
        return deserialize_action_result(response["result"])

    def get_turn_status(self) -> Dict[str, object]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.turn_system.get_turn_status() if engine else {}

    def get_controlled_player(self, local_player_id: str = None) -> Optional[Player]:
        engine = self.server.get_room_engine(self.room_id)
        player_id = self.player_id
        return engine.player_system.get_player_by_id(player_id) if engine and player_id else None

    def can_player_act(self, player_id: str) -> bool:
        engine = self.server.get_room_engine(self.room_id)
        return bool(engine and engine.turn_system.can_player_act(player_id))

    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.get_visible_state(player_id) if engine else None

    def get_visible_tiles(self, player_id: str) -> Set[HexCoord]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.vision_system.get_visible_tiles(player_id) if engine else set()

    def get_explored_tiles(self, player_id: str) -> Set[HexCoord]:
        engine = self.server.get_room_engine(self.room_id)
        return engine.vision_system.get_explored_tiles(player_id) if engine else set()

    def get_player_view(self) -> Dict[str, object]:
        """获取服务端返回的当前玩家安全视图。"""
        return self.server.get_player_view(self.room_id, self.client_id)


class HTTPNetworkSession:
    """HTTP 网络会话，通过 HTTPMultiplayerClient 访问远端服务端权威状态。"""

    def __init__(self, http_client, room_id: str, client_id: str):
        self.http_client = http_client
        self.room_id = room_id
        self.client_id = client_id
        self._view_cache: Optional[Dict[str, object]] = None
        self._engine_mirror: Optional[GameEngine] = None

    @property
    def engine(self) -> GameEngine:
        """根据最近一次安全视图构建只读引擎镜像，供现有 UI 渲染。"""
        view = self._poll_view()
        if not view:
            return GameEngine()
        if self._engine_mirror is None:
            self._engine_mirror = self._build_engine_mirror(view)
        return self._engine_mirror

    @property
    def player_id(self) -> Optional[str]:
        view = self._poll_view()
        return view.get("player_id") if view else None

    def start_game(self, player_names: List[str] = None, map_seed: int = None,
                   turn_mode: str = TurnSystem.MODE_SIMULTANEOUS) -> bool:
        response = self.http_client.start_room(self.room_id, map_seed=map_seed, turn_mode=turn_mode)
        if response.get("success"):
            views = response.get("views", {})
            self._set_view_cache(views.get(self.client_id))
        return bool(response.get("success"))

    def submit_action(self, action: GameAction) -> ActionResult:
        response = self.http_client.submit_action(self.room_id, self.client_id, action)
        if response.get("view"):
            self._set_view_cache(response["view"])
        return deserialize_action_result(response["result"])

    def get_turn_status(self) -> Dict[str, object]:
        view = self._poll_view()
        return view.get("turn_status", {}) if view else {}

    def get_controlled_player(self, local_player_id: str = None) -> Optional[Player]:
        view = self._poll_view()
        if not view:
            return None
        player_data = next((player for player in view.get("players", []) if player.get("is_self")), None)
        if not player_data:
            return None
        return Player(
            id=player_data["id"],
            name=player_data["name"],
            gold=player_data.get("gold") or 0
        )

    def can_player_act(self, player_id: str) -> bool:
        turn_status = self.get_turn_status()
        return player_id in set(turn_status.get("actionable_player_ids", []))

    def get_visible_state(self, player_id: str) -> Optional[GameState]:
        return None

    def get_visible_tiles(self, player_id: str) -> Set[HexCoord]:
        view = self._poll_view()
        return self._tiles_matching(view, "visible") if view else set()

    def get_explored_tiles(self, player_id: str) -> Set[HexCoord]:
        view = self._poll_view()
        return self._tiles_matching(view, "explored") if view else set()

    def get_player_view(self) -> Dict[str, object]:
        response = self.http_client.get_player_view(self.room_id, self.client_id)
        if response.get("success"):
            self._set_view_cache(response.get("view"))
        return response

    def _set_view_cache(self, view: Optional[Dict[str, object]]):
        self._view_cache = view
        self._engine_mirror = None

    def _poll_view(self) -> Optional[Dict[str, object]]:
        if self._view_cache is None:
            self.get_player_view()
        return self._view_cache

    def _build_engine_mirror(self, view: Dict[str, object]) -> GameEngine:
        turn_status = view.get("turn_status", {})
        engine = GameEngine(turn_mode=turn_status.get("mode", TurnSystem.MODE_SIMULTANEOUS))
        players_by_id = {}
        for player_data in view.get("players", []):
            player = Player(
                id=player_data["id"],
                name=player_data.get("name", player_data["id"]),
                gold=player_data.get("gold") or 0
            )
            players_by_id[player.id] = player
            engine.player_system.players.append(player)

        for coord_key, tile_data in view.get("tiles", {}).items():
            coord = parse_coord(coord_key)
            owner = players_by_id.get(tile_data.get("owner_id"))
            tile = Tile(
                coord=coord,
                terrain_type=TerrainType(tile_data.get("terrain", "land")),
                owner=owner,
                units=[]
            )
            engine.map_tiles[coord] = tile

        for coord_key, tile_data in view.get("tiles", {}).items():
            coord = parse_coord(coord_key)
            tile = engine.map_tiles[coord]
            city_data = tile_data.get("city")
            if city_data:
                owner = players_by_id.get(city_data.get("owner_id"))
                if owner:
                    city = City(
                        id=city_data["id"],
                        owner=owner,
                        center_tile=parse_coord(city_data.get("center", [coord.q, coord.r])),
                        territory_tiles=set()
                    )
                    tile.city = city
                    owner.cities.append(city)
                    engine.city_system.cities.append(city)
            for unit_data in tile_data.get("units", []):
                owner = players_by_id.get(unit_data.get("owner_id"))
                if not owner:
                    continue
                unit = Unit(
                    id=unit_data["id"],
                    owner=owner,
                    position=parse_coord(unit_data.get("position", [coord.q, coord.r])),
                    unit_type=UnitType(unit_data["unit_type"]),
                    movement_points=unit_data.get("movement_points", 0),
                    max_movement_points=unit_data.get("max_movement_points", 0),
                    vision_range=unit_data.get("vision_range", 0),
                    quantity=unit_data.get("quantity", 1)
                )
                tile.units.append(unit)
                owner.units.append(unit)
                engine.unit_system.units.append(unit)

        engine.map_system.tiles = engine.map_tiles
        engine.turn_system.players = engine.player_system.players
        engine.turn_system.mode = turn_status.get("mode", TurnSystem.MODE_SIMULTANEOUS)
        engine.turn_system.current_turn = view.get("turn", turn_status.get("turn", 1))
        engine.turn_system.turn_number = turn_status.get("turn_number", engine.turn_system.current_turn)
        engine.turn_system.ended_player_ids = set(turn_status.get("ended_player_ids", []))
        current_player_id = turn_status.get("current_player_id")
        player_ids = [player.id for player in engine.player_system.players]
        if current_player_id in player_ids:
            engine.turn_system.current_player_index = player_ids.index(current_player_id)
        engine.game_started = True
        engine.game_over = view.get("game_over", False)
        winner_id = view.get("winner_id")
        engine.winner = players_by_id.get(winner_id) if winner_id else None
        return engine

    def _tiles_matching(self, view: Dict[str, object], key: str) -> Set[HexCoord]:
        tiles = view.get("tiles", {})
        return {
            parse_coord(coord_key)
            for coord_key, tile in tiles.items()
            if tile.get(key)
        }
