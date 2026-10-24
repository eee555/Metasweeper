from __future__ import annotations

import copy
import json
import secrets
import socket
import threading
import time
from collections import deque
from concurrent.futures import Future, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, cast

PROTOCOL_VERSION = "2025-11-25"
MAX_BODY = 64 * 1024
MAX_CONNECTIONS = 8
IO_TIMEOUT = 3.0
CALL_TIMEOUT = 8.0
STOP_TIMEOUT = 1.0


def failure(message: str, outcome: str = "not_executed") -> dict:
    return {"success": False, "error": message, "outcome": outcome}


@dataclass(eq=False)
class PendingCall:
    name: str
    arguments: dict
    key: tuple
    deadline: float
    future: Future = field(default_factory=Future)
    lock: threading.Lock = field(default_factory=threading.Lock)
    started: bool = False
    cancelled: bool = False
    result: dict | None = None
    progress: dict | None = None

    def __post_init__(self) -> None:
        if self.name == "click_cell" and "clicks" in self.arguments and self.progress is None:
            clicks = self.arguments["clicks"]
            requested = len(clicks) if isinstance(clicks, list) else 0
            self.progress = {"success": False, "outcome": "not_executed",
                             "requested": requested, "completed": 0, "results": [],
                             "stopped_index": 0, "unattempted": requested}


class RequestBridge:
    """Dispatch PendingCall objects; use execute() to complete them cooperatively."""

    def __init__(self, dispatch: Callable[[PendingCall], None]):
        self.dispatch = dispatch
        self.lock = threading.Lock()
        self.pending: dict[tuple, PendingCall] = {}
        self.workers: set[threading.Thread] = set()
        self.closed_sessions: set[str] = set()
        self.stopped = False

    def call(self, name: str, arguments: dict, key: tuple, timeout: float) -> dict:
        call = PendingCall(name, arguments, key, time.monotonic() + timeout)
        with self.lock:
            if self.stopped or key[0] in self.closed_sessions:
                return failure("Service or session stopped")
            if (key in self.pending or len(self.pending) >= MAX_CONNECTIONS
                    or len(self.workers) >= MAX_CONNECTIONS):
                return failure("Request already pending or queue full")
            self.pending[key] = call
            worker = threading.Thread(
                target=self._dispatch, args=(call,), daemon=True)
            self.workers.add(worker)
            try:
                worker.start()
            except RuntimeError:
                self.workers.discard(worker)
                self.pending.pop(key, None)
                return failure("Request queue unavailable")
        try:
            try:
                return call.future.result(timeout=max(0.0, call.deadline - time.monotonic()))
            except FutureTimeout:
                self._cancel(call, "Timeout; do not retry automatically")
                return call.future.result()
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def _dispatch(self, call: PendingCall) -> None:
        try:
            with call.lock:
                if call.cancelled or call.future.done():
                    return
            self.dispatch(call)
        except Exception:
            self._cancel(call, "Request queue unavailable")
        finally:
            with self.lock:
                self.workers.discard(threading.current_thread())

    def _wait_until(self, deadline: float) -> None:
        with self.lock:
            workers = list(self.workers)
        for worker in workers:
            if worker is not threading.current_thread():
                worker.join(timeout=max(0.0, deadline - time.monotonic()))

    @staticmethod
    def _cancel(call: PendingCall, message: str) -> None:
        with call.lock:
            if call.future.done():
                return
            call.cancelled = True
            if call.progress is not None:
                call.result = copy.deepcopy(call.progress)
                if not call.result["success"]:
                    call.result["error"] = message
                    if call.result["results"] and not call.result["results"][-1]["success"]:
                        call.result["results"][-1]["error"] = message
            else:
                call.result = failure(
                    message, "unknown" if call.started else "not_executed")
            call.future.set_result(call.result)

    def cancel(self, key: tuple) -> None:
        with self.lock:
            call = self.pending.get(key)
        if call is not None:
            self._cancel(call, "Request cancelled; do not retry automatically")

    def cancel_session(self, session: str) -> None:
        with self.lock:
            self.closed_sessions.add(session)
            calls = [call for key, call in self.pending.items() if key[0]
                     == session]
        for call in calls:
            self._cancel(call, "Session closed; do not retry automatically")

    def stop(self) -> None:
        with self.lock:
            self.stopped = True
            calls = list(self.pending.values())
        for call in calls:
            self._cancel(call, "Service stopped; do not retry automatically")

    @staticmethod
    def execute(call: PendingCall, executor: Callable[[str, dict], dict]) -> None:
        with call.lock:
            if call.cancelled or call.future.done():
                return
            if time.monotonic() >= call.deadline:
                call.result = {**copy.deepcopy(call.progress or {}),
                               **failure("Request expired before execution")}
                call.future.set_result(call.result)
                return
            call.started = True
        try:
            result = executor(call.name, call.arguments)
        except Exception:
            RequestBridge._cancel(
                call, "Execution failed; result unknown; do not retry automatically")
            return
        with call.lock:
            if not call.future.done():
                call.result = result
                call.future.set_result(result)


class _HttpServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False
    request_queue_size = MAX_CONNECTIONS

    def __init__(self, owner: McpServer):
        self.owner = owner
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.active: set[socket.socket] = set()
        self.active_lock = threading.Condition()
        super().__init__(("127.0.0.1", owner.port), _Handler, bind_and_activate=False)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.server_bind()
            self.server_activate()
        except BaseException:
            self.server_close()
            raise

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        with self.active_lock:
            self.active.add(cast(socket.socket, request))
        try:
            super().process_request(request, client_address)
        except BaseException:
            with self.active_lock:
                self.active.discard(request)
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.active_lock:
                self.active.discard(request)
                self.active_lock.notify_all()
            self.slots.release()


class McpServer:
    """Local JSON-only MCP 2025-11-25 transport, with caller-owned tool validation.

    dispatcher(call) may enqueue work or invoke RequestBridge.execute(call, executor).
    executor(name, arguments) validates tool inputs and returns a JSON object with
    success: bool. Dispatch runs on bounded daemon threads, never the HTTP thread.
    Timed-out callbacks cannot be forcibly killed; they keep their worker slot until
    returning, and execute() ignores cancelled/expired work and late results.
    """

    def __init__(self, port: int, tools: list[dict], bridge: RequestBridge | None = None,
                 *, dispatcher: Callable[[PendingCall], None] | None = None):
        if type(port) is not int or not (port == 0 or 1024 <= port <= 65535):
            raise ValueError(
                "Port must be 0 or an integer between 1024 and 65535")
        if (bridge is None) == (dispatcher is None):
            raise ValueError("Provide exactly one bridge or dispatcher")
        snapshot = json.loads(json.dumps(tools, allow_nan=False))
        names = set()
        for tool in snapshot:
            if (not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
                    or not tool["name"] or tool["name"] in names
                    or not isinstance(tool.get("inputSchema"), dict)
                    or tool["inputSchema"].get("type") != "object"):
                raise ValueError(
                    "Tools require unique names and object input schemas")
            names.add(tool["name"])
        self.port = port
        self.tools: list[dict] = snapshot
        self.bridge = bridge if bridge is not None else RequestBridge(
            cast(Callable[[PendingCall], None], dispatcher))
        self.sessions: dict[str, bool] = {}
        self.lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self.stopped = threading.Event()
        self.arrivals: deque[float] = deque()
        self.http: _HttpServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    def start(self) -> None:
        """Start idempotently; restart only once previous dispatchers have returned."""
        with self._lifecycle_lock:
            if self.http is not None:
                return
            with self.bridge.lock:
                if self.stopped.is_set() and self.bridge.workers:
                    raise RuntimeError(
                        "Previous dispatchers must return before restarting")
            http = _HttpServer(self)
            if self.stopped.is_set():
                self.bridge = RequestBridge(self.bridge.dispatch)
            self.stopped.clear()
            self.arrivals.clear()
            self.port = http.server_address[1]
            thread = threading.Thread(target=http.serve_forever,
                                      kwargs={"poll_interval": 0.05}, daemon=True)
            try:
                thread.start()
            except BaseException:
                http.server_close()
                self.stopped.set()
                raise
            self.http, self.thread = http, thread

    def stop(self) -> None:
        """Invalidate sessions, close HTTP waits and join within STOP_TIMEOUT."""
        with self._lifecycle_lock:
            deadline = time.monotonic() + STOP_TIMEOUT
            self.stopped.set()
            self.bridge.stop()
            with self.lock:
                self.sessions.clear()
            http, thread = self.http, self.thread
            if http is not None:
                http.shutdown()
                with http.active_lock:
                    sockets = list(http.active)
                for connection in sockets:
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    connection.close()
                http.server_close()
                with http.active_lock:
                    http.active_lock.wait_for(lambda: not http.active,
                                              timeout=max(0.0, deadline - time.monotonic()))
            if thread is not None:
                thread.join(timeout=max(0.0, deadline - time.monotonic()))
            self.bridge._wait_until(deadline)
            self.http = None
            self.thread = None

    def admit_request(self) -> bool:
        now = time.monotonic()
        with self.lock:
            while self.arrivals and self.arrivals[0] < now - 1.0:
                self.arrivals.popleft()
            if len(self.arrivals) >= 32:
                return False
            self.arrivals.append(now)
            return True


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    @property
    def mcp(self) -> _HttpServer:
        return cast(_HttpServer, self.server)

    def setup(self):
        super().setup()
        self.connection.settimeout(IO_TIMEOUT)
        self.deadline = time.monotonic() + IO_TIMEOUT
        self._body_remaining: int | None = None
        self._input_timer = threading.Timer(IO_TIMEOUT, self._expire_input)
        self._input_timer.daemon = True
        self._input_timer.start()

    def _expire_input(self):
        try:
            self.connection.shutdown(socket.SHUT_RD)
        except OSError:
            pass

    def finish(self):
        self._input_timer.cancel()
        super().finish()

    def handle(self):
        try:
            super().handle()
        except (ConnectionError, OSError):
            pass

    def parse_request(self):
        if not super().parse_request():
            return False
        if sum(len(name) + len(value) for name, value in self.headers.items()) > 16384:
            self._reply(431)
            return False
        return True

    def log_message(self, format, *args):
        pass

    def _reply(self, status: int, body=None, headers: dict | None = None):
        self._input_timer.cancel()
        self.connection.settimeout(IO_TIMEOUT)
        payload = b"" if body is None else json.dumps(
            body, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("MCP-Protocol-Version", PROTOCOL_VERSION)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if payload:
            self.wfile.write(payload)
        if status >= 400:
            self._discard_body()

    def _discard_body(self) -> None:
        remaining = self._body_remaining
        if remaining is None:
            length = self.headers.get("Content-Length", "")
            remaining = (int(length) if length.isascii() and length.isdigit() and len(length) <= 10
                         else MAX_BODY)
        remaining = min(remaining, MAX_BODY)
        if remaining <= 0:
            return
        deadline = time.monotonic() + min(0.05, IO_TIMEOUT)
        try:
            while remaining:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    break
                self.connection.settimeout(timeout)
                chunk = self.rfile.read1(min(4096, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (OSError, ValueError):
            pass

    def _error(self, code: int, message: str, request_id=None, status: int = 200):
        body = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
        if type(request_id) in (str, int):
            body["id"] = request_id
        self._reply(status, body)

    def _guard(self) -> bool:
        owner = self.mcp.owner
        if owner.stopped.is_set():
            self._reply(503)
            return False
        for name in ("Host", "Origin", "Content-Length", "Content-Type",
                     "Accept", "Transfer-Encoding", "MCP-Protocol-Version", "Mcp-Session-Id"):
            if len(self.headers.get_all(name, [])) > 1:
                self._error(-32600, "Duplicate header", status=400)
                return False
        host = f"127.0.0.1:{owner.port}"
        if self.headers.get("Host") != host or self.headers.get("Origin") not in (None, f"http://{host}"):
            self._reply(403)
            return False
        if self.path != "/mcp":
            self._reply(404)
            return False
        version = self.headers.get("MCP-Protocol-Version")
        if version is not None and version != PROTOCOL_VERSION:
            self._error(-32600, "Unsupported protocol version", status=400)
            return False
        session = self.headers.get("Mcp-Session-Id")
        if session is not None:
            with owner.lock:
                found = session in owner.sessions
            if not found:
                self._reply(404)
                return False
        return True

    def do_GET(self):
        if self._guard():
            self._reply(405, headers={"Allow": "POST, DELETE"})

    do_HEAD = do_GET
    do_OPTIONS = do_GET
    do_PUT = do_GET
    do_PATCH = do_GET

    def do_DELETE(self):
        if not self._guard():
            return
        if not self.mcp.owner.admit_request():
            self._reply(429, headers={"Retry-After": "1"})
            return
        session = self.headers.get("Mcp-Session-Id", "")
        if not session:
            self._reply(400)
            return
        with self.mcp.owner.lock:
            found = self.mcp.owner.sessions.pop(session, None)
        if found is not None:
            self.mcp.owner.bridge.cancel_session(session)
        self._reply(200 if found is not None else 404)

    def do_POST(self):
        if not self._guard():
            return
        if not self.mcp.owner.admit_request():
            self._reply(429, headers={"Retry-After": "1"})
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._error(-32600, "Transfer-Encoding not supported", status=400)
            return
        if self.headers.get_content_type() != "application/json":
            self._reply(415)
            return
        accepts = {part.split(";")[0].strip()
                   for part in self.headers.get("Accept", "").split(",")}
        if not {"application/json", "text/event-stream"} <= accepts:
            self._reply(406)
            return
        length = self.headers.get("Content-Length", "")
        if not length.isascii() or not length.isdigit():
            self._error(-32600, "Content-Length required", status=400)
            return
        if len(length) > 10:
            self._reply(413)
            return
        size = int(length)
        if size > MAX_BODY:
            self._reply(413)
            return
        self._body_remaining = size
        try:
            body = bytearray()
            while len(body) < size:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                self.connection.settimeout(remaining)
                chunk = self.rfile.read1(min(4096, size - len(body)))
                if not chunk:
                    if time.monotonic() >= self.deadline:
                        raise TimeoutError
                    raise ValueError("Incomplete body")
                body.extend(chunk)
                self._body_remaining -= len(chunk)
            message = json.loads(body.decode("utf-8"),
                                 parse_constant=self._invalid_constant)
        except TimeoutError:
            self._reply(408)
            return
        except (ValueError, UnicodeError, RecursionError):
            self._error(-32700, "Parse error", status=400)
            return
        self._input_timer.cancel()
        self._dispatch(message)

    @staticmethod
    def _invalid_constant(value):
        raise ValueError("Invalid JSON constant")

    def _dispatch(self, message):
        request_id = message.get("id") if isinstance(message, dict) else None
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
            or not isinstance(message.get("method"), str)
                or "result" in message or "error" in message):
            self._error(-32600, "Invalid Request", request_id, status=400)
            return
        notification = "id" not in message
        if not notification and type(request_id) not in (str, int):
            self._error(-32600, "Invalid request id", status=400)
            return
        params = message.get("params", {})
        if not isinstance(params, dict):
            if notification:
                self._reply(400)
            else:
                self._error(-32602, "Invalid params", request_id)
            return
        method = message["method"]
        owner = self.mcp.owner
        if method == "initialize" and not notification:
            if self.headers.get("Mcp-Session-Id"):
                self._error(-32600, "Initialize must not reuse a session",
                            request_id, status=400)
                return
            info = params.get("clientInfo")
            if (not isinstance(params.get("protocolVersion"), str)
                    or not isinstance(params.get("capabilities"), dict)
                    or not isinstance(info, dict)
                    or not all(isinstance(info.get(key), str) for key in ("name", "version"))):
                self._error(-32602, "Invalid initialize params", request_id)
                return
            with owner.lock:
                if owner.stopped.is_set():
                    self._reply(503)
                    return
                if len(owner.sessions) >= 32:
                    self._error(-32000,
                                "Session limit reached; restart service", request_id)
                    return
                session = secrets.token_urlsafe(24)
                owner.sessions[session] = False
            self._reply(200, {"jsonrpc": "2.0", "id": request_id, "result": {
                "protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "metasweeper-mcp", "version": "2.0.0"}}},
                {"Mcp-Session-Id": session})
            return
        session = self.headers.get("Mcp-Session-Id", "")
        with owner.lock:
            initialized = owner.sessions.get(session)
        if initialized is None:
            self._reply(404 if session else 400)
            return
        if notification:
            if method == "notifications/initialized":
                with owner.lock:
                    if session in owner.sessions:
                        owner.sessions[session] = True
            elif method == "notifications/cancelled":
                cancelled_id = params.get("requestId")
                if type(cancelled_id) in (str, int):
                    owner.bridge.cancel((session, cancelled_id))
            self._reply(202)
            return
        if method == "ping":
            result = {}
        elif not initialized:
            self._error(-32000, "Client not initialized", request_id)
            return
        elif method == "tools/list":
            if params.get("cursor") is not None:
                self._error(-32602, "Invalid cursor", request_id)
                return
            result = {"tools": owner.tools}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            if (not isinstance(name, str) or name not in {tool["name"] for tool in owner.tools}
                    or not isinstance(arguments, dict) or "task" in params):
                self._error(-32602,
                            "Unknown tool or invalid call params", request_id)
                return
            outcome = owner.bridge.call(
                name, arguments, (session, request_id), CALL_TIMEOUT)
            try:
                if not isinstance(outcome, dict) or type(outcome.get("success")) is not bool:
                    raise ValueError("Invalid callback result")
                text = json.dumps(outcome, allow_nan=False)
            except (TypeError, ValueError, OverflowError, RecursionError):
                self._error(-32603, "Invalid tool callback result", request_id)
                return
            result = {"content": [{"type": "text", "text": text}],
                      "structuredContent": outcome, "isError": not outcome["success"]}
        else:
            self._error(-32601, "Method not found", request_id)
            return
        self.connection.settimeout(IO_TIMEOUT)
        self._reply(
            200, {"jsonrpc": "2.0", "id": request_id, "result": result})
