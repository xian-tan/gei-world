"""
HTTP + 轮询多人传输层原型。

基于 Python 标准库提供最小 HTTP API，把进程内 MultiplayerServer 暴露为可连接服务。
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib import parse, request, error

from .models import GameAction
from .multiplayer_server import MultiplayerServer
from .network_protocol import serialize_action
from .systems.turn_system import TurnSystem


class MultiplayerHTTPServer(ThreadingHTTPServer):
    """携带 MultiplayerServer 实例的 HTTPServer。"""

    def __init__(self, server_address, RequestHandlerClass, multiplayer_server: MultiplayerServer = None):
        super().__init__(server_address, RequestHandlerClass)
        self.multiplayer_server = multiplayer_server or MultiplayerServer()


class MultiplayerHTTPRequestHandler(BaseHTTPRequestHandler):
    """多人 HTTP API 处理器。"""

    server: MultiplayerHTTPServer

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def log_message(self, format, *args):
        """测试和本地调试默认不输出访问日志。"""
        return

    def _handle_request(self, method: str):
        try:
            parsed = parse.urlparse(self.path)
            path_parts = [part for part in parsed.path.split("/") if part]
            query = parse.parse_qs(parsed.query)
            payload = self._read_json() if method == "POST" else {}
            response = self._route(method, path_parts, query, payload)
            self._send_json(response, 200 if response.get("success", True) else 400)
        except KeyError as exc:
            self._send_json({"success": False, "message": str(exc)}, 404)
        except ValueError as exc:
            self._send_json({"success": False, "message": str(exc)}, 400)
        except Exception as exc:
            self._send_json({"success": False, "message": f"服务器错误: {exc}"}, 500)

    def _route(self, method: str, path_parts, query, payload: Dict[str, object]) -> Dict[str, object]:
        app = self.server.multiplayer_server
        if method == "POST" and path_parts == ["rooms"]:
            return app.create_room(
                host_name=str(payload.get("host_name", "玩家1")),
                max_players=int(payload.get("max_players", 2)),
                turn_mode=str(payload.get("turn_mode", TurnSystem.MODE_SIMULTANEOUS)),
                map_seed=payload.get("map_seed")
            )

        if len(path_parts) >= 2 and path_parts[0] == "rooms":
            room_id = path_parts[1]
            if method == "GET" and len(path_parts) == 2:
                return {"success": True, "room": app.get_room_state(room_id)}
            if method == "POST" and len(path_parts) == 3 and path_parts[2] == "join":
                return app.join_room(room_id, str(payload.get("player_name", "玩家")))
            if method == "POST" and len(path_parts) == 3 and path_parts[2] == "leave":
                return app.leave_room(room_id, str(payload.get("client_id", "")))
            if method == "POST" and len(path_parts) == 3 and path_parts[2] == "reconnect":
                return app.reconnect_room(room_id, str(payload.get("client_id", "")))
            if method == "POST" and len(path_parts) == 3 and path_parts[2] == "start":
                return app.start_room(
                    room_id,
                    map_seed=payload.get("map_seed"),
                    turn_mode=payload.get("turn_mode")
                )
            if method == "POST" and len(path_parts) == 3 and path_parts[2] == "actions":
                client_id = str(payload.get("client_id", ""))
                return app.submit_action(room_id, client_id, payload.get("action", {}))
            if method == "GET" and len(path_parts) == 3 and path_parts[2] == "view":
                client_id = query.get("client_id", [""])[0]
                return app.get_player_view(room_id, client_id)

        raise ValueError(f"未知接口: {method} /{'/'.join(path_parts)}")

    def _read_json(self) -> Dict[str, object]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        raw_data = self.rfile.read(content_length).decode("utf-8")
        return json.loads(raw_data) if raw_data else {}

    def _send_json(self, data: Dict[str, object], status_code: int):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_http_server(host: str = "127.0.0.1", port: int = 8000,
                       multiplayer_server: MultiplayerServer = None) -> MultiplayerHTTPServer:
    """创建多人 HTTP 服务实例。"""
    return MultiplayerHTTPServer((host, port), MultiplayerHTTPRequestHandler, multiplayer_server)


class HTTPMultiplayerClient:
    """HTTP 多人客户端，供测试和后续 NetworkSession 传输层使用。"""

    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_room(self, host_name: str, max_players: int = 2,
                    turn_mode: str = TurnSystem.MODE_SIMULTANEOUS,
                    map_seed: int = None) -> Dict[str, object]:
        return self._request("POST", "/rooms", {
            "host_name": host_name,
            "max_players": max_players,
            "turn_mode": turn_mode,
            "map_seed": map_seed,
        })

    def join_room(self, room_id: str, player_name: str) -> Dict[str, object]:
        return self._request("POST", f"/rooms/{room_id}/join", {"player_name": player_name})

    def leave_room(self, room_id: str, client_id: str) -> Dict[str, object]:
        return self._request("POST", f"/rooms/{room_id}/leave", {"client_id": client_id})

    def reconnect_room(self, room_id: str, client_id: str) -> Dict[str, object]:
        return self._request("POST", f"/rooms/{room_id}/reconnect", {"client_id": client_id})

    def start_room(self, room_id: str, map_seed: int = None, turn_mode: str = None) -> Dict[str, object]:
        return self._request("POST", f"/rooms/{room_id}/start", {
            "map_seed": map_seed,
            "turn_mode": turn_mode,
        })

    def submit_action(self, room_id: str, client_id: str, action: GameAction) -> Dict[str, object]:
        return self._request("POST", f"/rooms/{room_id}/actions", {
            "client_id": client_id,
            "action": serialize_action(action),
        })

    def get_room_state(self, room_id: str) -> Dict[str, object]:
        return self._request("GET", f"/rooms/{room_id}")

    def get_player_view(self, room_id: str, client_id: str) -> Dict[str, object]:
        encoded_client_id = parse.quote(client_id)
        return self._request("GET", f"/rooms/{room_id}/view?client_id={encoded_client_id}")

    def _request(self, method: str, path: str, payload: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            return json.loads(body) if body else {"success": False, "message": str(exc)}
        except (error.URLError, TimeoutError, OSError) as exc:
            return {"success": False, "message": f"连接失败: {exc}"}


def run_http_server(host: str = "127.0.0.1", port: int = 8000):
    """阻塞运行 HTTP 多人服务。"""
    http_server = create_http_server(host, port)
    print(f"多人 HTTP 服务已启动: http://{host}:{port}")
    http_server.serve_forever()
