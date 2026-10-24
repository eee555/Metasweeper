from __future__ import annotations

import copy
import http.client
import json
import queue
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import cast

import pytest
import zmq

from lib_zmq_plugins.serializer import Serializer
from lib_zmq_plugins.shared.base import BaseQueryResult, CommandResponse, peek_struct_tag
from plugin_sdk import BasePlugin
from plugin_sdk.control_auth import ControlAuthorizationManager
from plugins.llm_minesweeper_controller import plugin
from plugins.llm_minesweeper_controller import command_io
from plugins.llm_minesweeper_controller.command_io import CommandIO
from plugins.llm_minesweeper_controller.config import (
    CONFIG_IDENTITIES, LlmMinesweeperControllerConfig, sanitize_legacy_configs, valid_port,
)
from plugins.llm_minesweeper_controller.tools import MAX_BATCH_CLICKS, MinesweeperTools, STATUS_NAMES, TOOLS
from plugins.llm_minesweeper_controller import mcp_server
from plugins.llm_minesweeper_controller.mcp_server import McpServer, PendingCall, RequestBridge
from shared_types.commands import MouseClickCommand, NewGameCommand
from shared_types.queries import (
    BoardStateResult, ControlPermissions, GameContextResult, GameStatusResult,
    GetBoardStateQuery, GetGameContextQuery, GetGameStatusQuery,
    QUERY_RESULT_TYPES, QUERY_TYPES,
)
from shared_types.events import BoardUpdateEvent, GameStatusChangeEvent


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def set_board(registry, status=1):
    registry.update_status(GameStatusChangeEvent(current_status=status))
    registry.update_board(BoardUpdateEvent(rows=2, cols=3, game_board=[[10, 11, 1], [0, 10, 10]],
                                           mines_remaining=1, game_time=0.5))


@pytest.fixture
def sdk():
    state = SimpleNamespace(authorized=True, calls=[],
                            queries=[], response=True, raises=False)

    def request(command, timeout):
        assert timeout == 3.0
        state.calls.append(command)
        if state.raises:
            raise TimeoutError
        if state.response is None:
            return None
        return CommandResponse(request_id="fake", success=state.response)

    def query(value, timeout):
        # 默认让查询失败，测试走缓存回退；需要 live 的测试自行替换
        state.queries.append(value)
        return None

    state.registry = MinesweeperTools(
        lambda command: state.authorized, request, query)
    return state


@pytest.fixture
def official_auth(monkeypatch, tmp_path):
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)
    return ControlAuthorizationManager.instance(tmp_path)


@pytest.fixture
def zmq_main():
    ready, stopped = threading.Event(), threading.Event()
    state = SimpleNamespace(endpoint="", mode="confirmed", commands=[], errors=[],
                            queries=[], query_results={})

    def serve():
        context = zmq.Context()
        router = context.socket(zmq.ROUTER)
        router.setsockopt(zmq.LINGER, 0)
        serializer = Serializer()
        serializer.register_command_types(MouseClickCommand, NewGameCommand)
        serializer.register_query_types(*QUERY_TYPES)
        serializer.register_query_result_types(*QUERY_RESULT_TYPES)
        try:
            port = router.bind_to_random_port(
                "tcp://127.0.0.1", min_port=12000, max_port=65000)
            state.endpoint = f"tcp://127.0.0.1:{port - 2}"
            ready.set()
            while not stopped.is_set():
                if not router.poll(10, zmq.POLLIN):
                    continue
                identity, payload = router.recv_multipart()
                if serializer.is_query_tag(peek_struct_tag(payload)):
                    query = serializer.decode_query(payload)
                    state.queries.append(query)
                    template = state.query_results.get(type(query))
                    if isinstance(template, BaseQueryResult):
                        result = copy.copy(template)
                        result.request_id = query.request_id
                    else:
                        result = BaseQueryResult(request_id=query.request_id,
                                                 success=False, error="unavailable")
                    router.send_multipart(
                        [identity, b"", serializer.encode_query_result(result)])
                    continue
                command = serializer.decode_command(payload)
                state.commands.append(command)
                if state.mode == "missing":
                    continue
                response = CommandResponse(request_id=command.request_id, success=state.mode != "rejected",
                                           error="Main switch disabled" if state.mode == "rejected" else None)
                if state.mode == "wrong_id":
                    response.request_id = "unrelated"
                encoded = b"invalid-msgpack" if state.mode == "malformed" else serializer.encode_response(
                    response)
                frames = [identity, encoded] if state.mode == "single" else [
                    identity, b"", encoded]
                if state.mode == "bad_frame":
                    frames = [identity, b"unexpected", encoded]
                router.send_multipart(frames)
        except Exception as error:
            state.errors.append(error)
            ready.set()
        finally:
            router.close(linger=0)
            context.term()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(2) and state.endpoint and not state.errors
    try:
        yield state
    finally:
        stopped.set()
        thread.join(2)
        assert not thread.is_alive() and not state.errors


@pytest.fixture
def plugin_owner(zmq_main, official_auth, tmp_path):
    states, saved, subscriptions = [], [], []
    owner = SimpleNamespace(_server=None, _io=None, _state="stopped", _config_error="",
                            name="元扫雷 MCP 服务", other_info=LlmMinesweeperControllerConfig(),
                            client=SimpleNamespace(endpoint=zmq_main.endpoint),
                            service_state_changed=SimpleNamespace(
                                emit=states.append),
                            save_config=lambda: saved.append(True),
                            subscribe=lambda event, handler: subscriptions.append(
                                (event, handler)),
                            config_changed=SimpleNamespace(
                                connect=lambda *args: None),
                            data_dir=tmp_path / CONFIG_IDENTITIES[0], states=states, saved=saved,
                            subscriptions=subscriptions)
    owner.data_dir.mkdir()
    for name in ("_publish_state", "_request_control", "_request_query", "_on_settings_changed", "_on_board_update",
                 "_on_game_status_change", "_setup_subscriptions", "start_mcp", "stop_mcp",
                 "on_initialized", "on_shutdown"):
        method = getattr(plugin.LlmMinesweeperControllerPlugin, name)
        setattr(owner, name, method.__get__(owner))
    owner._tools = MinesweeperTools(lambda command_type: False, owner._request_control,
                                    owner._request_query)
    try:
        yield owner
    finally:
        owner.stop_mcp()


def test_plugin_full_http_zmq_official_permissions_and_restart(plugin_owner, official_auth, zmq_main):
    owner = plugin_owner
    owner._setup_subscriptions()
    owner.on_initialized()
    assert owner._state == "stopped" and owner._server is None and not zmq_main.commands
    assert [event for event, handler in owner.subscriptions] == [
        BoardUpdateEvent, GameStatusChangeEvent]
    owner._on_game_status_change(GameStatusChangeEvent(current_status=1))
    owner._on_board_update(BoardUpdateEvent(rows=1, cols=1, game_board=[[10]]))
    owner.start_mcp(free_port())
    assert owner._state == "running"
    server = owner._server
    session = initialize(server)

    def call_tool(request_id, name, arguments=None):
        message = {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                   "params": {"name": name, "arguments": arguments or {}}}
        return rpc_body(http_request(server, message, extra=session))["result"]["structuredContent"]

    assert call_tool(2, "get_board_state")["cells"] == [[-1]]
    assert not call_tool(3, "click_cell", {"row": 0, "col": 0})["success"]
    assert not zmq_main.commands
    official_auth.authorize(MouseClickCommand, owner.name)
    assert call_tool(4, "click_cell", {"row": 0, "col": 0})[
        "outcome"] == "confirmed"
    assert len(zmq_main.commands) == 1
    official_auth.revoke(MouseClickCommand)
    set_board(owner._tools)
    assert not call_tool(5, "click_cell", {"row": 0, "col": 0})["success"]
    official_auth.authorize(NewGameCommand, owner.name)
    set_board(owner._tools, 2)
    assert not call_tool(6, "start_new_game")["success"]
    set_board(owner._tools, 3)
    assert call_tool(7, "start_new_game")["outcome"] == "confirmed"
    assert isinstance(zmq_main.commands[-1], NewGameCommand)
    assert len(zmq_main.commands) == 2
    set_board(owner._tools)
    port, io_thread = server.port, owner._io.thread
    owner.stop_mcp()
    assert not io_thread.is_alive() and owner._tools.board is not None
    owner.start_mcp(port)
    assert owner._state == "running" and owner._server.port == port
    assert owner._tools.execute_function("get_board_state", {})["success"]
    assert len(zmq_main.commands) == 2


def test_plugin_read_only_tools_reach_main_process_without_control_auth(
        plugin_owner, official_auth, zmq_main):
    """只读查询必须真正经 ZMQ 到达主进程，且不进入控制授权"""
    owner = plugin_owner
    owner.on_initialized()
    zmq_main.query_results = {
        GetBoardStateQuery: BoardStateResult(
            cells=[[10, 11]], rows=1, cols=2, mines_remaining=2, game_time=7.5,
            game_status="joking", game_status_code=2),
        GetGameStatusQuery: GameStatusResult(
            game_status="joking", game_status_code=2, game_time=7.5,
            mines_remaining=2, rows=1, cols=2, mines=2, level=3,
            level_name="初级", mode=0, mode_name="标准"),
        GetGameContextQuery: GameContextResult(
            game_status="playing", bbbv=20, bbbv_solved=10, progress=0.5,
            is_official=True, is_fair=True, software="metasweeper",
            permissions=ControlPermissions(allowed_controls=["board_update"],
                                           board_update=True)),
    }
    owner.start_mcp(free_port())
    try:
        assert not official_auth.is_authorized(GetBoardStateQuery, owner.name)
        server = owner._server
        session = initialize(server)

        def call_tool(request_id, name):
            message = {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                       "params": {"name": name, "arguments": {}}}
            return rpc_body(http_request(server, message, extra=session))["result"]["structuredContent"]

        board = call_tool(2, "get_board_state")
        assert board["source"] == "live" and board["cells"] == [[-1, "F"]]
        # joking 与 playing 数值相同，必须按状态名校验，不能误判为非法而回退缓存
        status = call_tool(3, "get_game_status")
        assert status["source"] == "live" and status["game_status"] == "joking"
        assert status["level_name"] == "初级"

        context = call_tool(4, "get_game_context")
        assert context["source"] == "live" and context["progress"] == 0.5
        assert context["permissions"]["board_update"] is True

        assert sum(isinstance(q, GetBoardStateQuery)
                   for q in zmq_main.queries) == 1
        assert sum(isinstance(q, GetGameStatusQuery)
                   for q in zmq_main.queries) == 1
        assert sum(isinstance(q, GetGameContextQuery)
                   for q in zmq_main.queries) == 1
        assert not zmq_main.commands
    finally:
        owner.stop_mcp()
    assert owner._state != "running"


@pytest.mark.parametrize("mode", ["confirmed", "rejected", "timeout", "cancel", "session", "stop", "revoked"])
def test_plugin_batch_http_zmq_progress_and_stop(plugin_owner, official_auth, zmq_main, monkeypatch, mode):
    monkeypatch.setattr(mcp_server, "CALL_TIMEOUT", 1.0)
    owner = plugin_owner
    zmq_main.query_results[GetBoardStateQuery] = BoardStateResult(
        cells=[[10, 10, 10]], rows=1, cols=3,
        game_status="joking", game_status_code=2)
    owner.on_initialized()
    official_auth.authorize(MouseClickCommand, owner.name)
    owner.start_mcp(free_port())
    server = owner._server
    session = initialize(server)
    original_request = owner._io.request

    def request(command, timeout):
        response = original_request(command, timeout)
        if command.col == 0:
            if mode in ("rejected", "timeout"):
                zmq_main.mode = "missing" if mode == "timeout" else "rejected"
            elif mode == "cancel":
                assert http_request(server, {"jsonrpc": "2.0", "method": "notifications/cancelled",
                                             "params": {"requestId": "batch"}}, extra=session)[0] == 202
            elif mode == "session":
                assert http_request(server, method="DELETE", extra=session)[0] == 200
            elif mode == "stop":
                server.bridge.stop()
            elif mode == "revoked":
                official_auth.revoke(MouseClickCommand)
        return response

    owner._io.request = request
    message = {"jsonrpc": "2.0", "id": "batch", "method": "tools/call",
               "params": {"name": "click_cell", "arguments": {
                   "clicks": [{"row": 0, "col": index, "button": button}
                              for index, button in enumerate(("left", "right", "middle"))]}}}
    result = rpc_body(http_request(server, message, extra=session))["result"]
    payload = result["structuredContent"]
    assert payload["completed"] == (3 if mode == "confirmed" else 1)
    assert payload["requested"] == 3 and result["isError"] == (mode != "confirmed")
    assert payload["outcome"] == ("confirmed" if mode == "confirmed" else
                                   "unknown" if mode == "timeout" else "partial")
    assert payload["stopped_index"] == (None if mode == "confirmed" else 1)
    assert len(zmq_main.commands) == (3 if mode == "confirmed" else
                                     2 if mode in ("rejected", "timeout") else 1)
    assert [command.col for command in zmq_main.commands] == list(range(len(zmq_main.commands)))
    if mode == "confirmed":
        assert [command.button for command in zmq_main.commands] == [0, 2, 1]
    if mode in ("rejected", "timeout"):
        assert payload["unattempted"] == 1 and len(payload["results"]) == 2
    else:
        assert payload["unattempted"] == (0 if mode == "confirmed" else
                                          1 if mode == "revoked" else 2)


def test_plugin_busy_port_rolls_back_and_shutdown_releases(plugin_owner):
    owner = plugin_owner
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        owner.start_mcp(port)
        assert owner._state == "error" and owner._io is None and owner._server is None
        assert owner.states[-1]["prompt"] == "" and not owner.saved
    owner.start_mcp(port)
    assert owner._state == "running"
    server, io_thread = owner._server, owner._io.thread
    owner.start_mcp(free_port())
    assert owner._server is server
    owner.on_shutdown()
    owner.stop_mcp()
    assert owner._state == "stopped" and not io_thread.is_alive()
    with socket.socket() as replacement:
        replacement.bind(("127.0.0.1", port))


@pytest.mark.parametrize("mode", ["cleanup", "save"])
def test_plugin_configuration_failure_fails_closed(plugin_owner, monkeypatch, mode):
    def fail(*args):
        raise OSError("simulated filesystem failure")

    owner = plugin_owner
    if mode == "cleanup":
        monkeypatch.setattr(plugin, "sanitize_legacy_configs", fail)
        owner.on_initialized()
    else:
        owner.save_config = fail
    owner.start_mcp(free_port())
    assert owner._state == "error" and owner._server is None and owner._io is None
    assert owner.states[-1]["endpoint"] == "" and owner.states[-1]["prompt"] == ""


@pytest.mark.parametrize("port", [0, 1023, 65536, True, "8765"])
def test_plugin_rejects_invalid_ports_without_io(plugin_owner, port):
    plugin_owner.start_mcp(port)
    assert plugin_owner._state == "error" and plugin_owner._io is None and not plugin_owner.saved


def test_official_permission_file_default_deny_and_identity(official_auth):
    owner = SimpleNamespace(name="元扫雷 MCP 服务")
    assert callable(BasePlugin._check_control_auth)
    assert not BasePlugin.has_control_auth(owner, MouseClickCommand)
    official_auth.authorize(MouseClickCommand, "LLM反控扫雷")
    official_auth.save()
    official_auth.load()
    assert not BasePlugin.has_control_auth(owner, MouseClickCommand)
    official_auth.authorize(MouseClickCommand, owner.name)
    official_auth.save()
    official_auth.load()
    assert BasePlugin.has_control_auth(owner, MouseClickCommand)
    assert not BasePlugin.has_control_auth(owner, NewGameCommand)
    official_auth.revoke(MouseClickCommand)
    assert not BasePlugin.has_control_auth(owner, MouseClickCommand)


@pytest.mark.parametrize("mode", ["deadline", "cancel", "stop"])
def test_command_io_rechecks_after_writable_poll(monkeypatch, mode):
    clock, sent, authorized = [0.0], [], []
    monkeypatch.setattr(command_io.time, "monotonic", lambda: clock[0])
    owner = CommandIO("tcp://127.0.0.1:50000", lambda command: authorized.append(command) or True,
                      lambda *args: {})
    call = PendingCall("click", {}, ("s", 1), 1.0)
    owner.thread = threading.current_thread()
    owner.active = call

    def poll(*args):
        if mode == "deadline":
            clock[0] = 2.0
        elif mode == "cancel":
            RequestBridge._cancel(call, "cancelled")
        else:
            owner.stopped.set()
        return True

    owner._socket = SimpleNamespace(poll=poll, send=lambda *args, **kwargs: sent.append(args),
                                    close=lambda **kwargs: None)
    with pytest.raises(TimeoutError):
        owner.request(MouseClickCommand())
    assert not sent and not authorized and owner._socket is None


@pytest.mark.parametrize("mode", ["confirmed", "rejected", "single", "wrong_id", "missing", "malformed", "bad_frame"])
def test_command_io_real_mock_framing_and_confirmation(zmq_main, mode):
    zmq_main.mode = mode
    responses = []

    def execute(name, arguments):
        response = owner.request(MouseClickCommand(row=0, col=0), timeout=0.15)
        responses.append(response)
        return {"success": response.success}

    owner = CommandIO(zmq_main.endpoint, lambda command: True, execute)
    bridge = RequestBridge(owner.submit)
    owner.start()
    try:
        result = bridge.call("click", {}, ("s", 1), 1)
        assert len(zmq_main.commands) == 1
        if mode in ("confirmed", "rejected", "single"):
            assert isinstance(responses[0], CommandResponse)
            assert responses[0].request_id == zmq_main.commands[0].request_id
            assert result["success"] == (mode != "rejected")
        else:
            assert not result["success"] and result["outcome"] == "unknown" and not responses
    finally:
        bridge.stop()
        owner.stop()
    assert not owner.thread.is_alive() and owner._socket is None and owner._context is None


def test_command_io_all_socket_lifecycle_on_one_owner(monkeypatch, zmq_main):
    operations = []
    original_context = zmq.Context

    class TrackedSocket:
        def __init__(self, socket):
            self.socket = socket

        def __getattr__(self, name):
            def invoke(*args, **kwargs):
                operations.append((name, threading.get_ident()))
                return getattr(self.socket, name)(*args, **kwargs)
            return invoke

    class TrackedContext:
        def __init__(self):
            operations.append(("context", threading.get_ident()))
            self.context = original_context()

        def socket(self, kind):
            operations.append(("socket", threading.get_ident()))
            return TrackedSocket(self.context.socket(kind))

        def term(self):
            operations.append(("term", threading.get_ident()))
            self.context.term()

    monkeypatch.setattr(command_io.zmq, "Context", TrackedContext)

    def execute(name, arguments):
        return {"success": owner.request(MouseClickCommand()).success}

    owner = CommandIO(zmq_main.endpoint, lambda command: True, execute)
    bridge = RequestBridge(owner.submit)
    owner.start()
    try:
        assert bridge.call("click", {}, ("s", 1), 2)["success"]
        with pytest.raises(RuntimeError, match="private I/O owner"):
            owner.request(MouseClickCommand())
    finally:
        owner.stop()
        bridge.stop()
    assert {thread for operation, thread in operations} == {owner.thread.ident}
    assert {operation for operation, thread in operations} >= {
        "context", "socket", "setsockopt", "connect", "poll", "send", "recv_multipart", "close", "term"}


def test_zmq_server_client_query_roundtrip():
    """真实 ZMQ 服务器/客户端：查询协议独立于命令与授权"""
    from lib_zmq_plugins.client.zmq_client import ZMQClient
    from lib_zmq_plugins.server.zmq_server import ZMQServer

    base_port = free_port()
    endpoint = f"tcp://127.0.0.1:{base_port}"
    server = ZMQServer(endpoint)
    server.register_query_types(*QUERY_TYPES)
    server.register_query_result_types(*QUERY_RESULT_TYPES)
    server.register_query_handler(
        GetBoardStateQuery,
        lambda q: BoardStateResult(
            request_id=q.request_id, cells=[[10, 11]], rows=1, cols=2,
            mines_remaining=1, game_time=2.5, game_status="playing",
            game_status_code=2))
    server.start()
    client = ZMQClient(endpoint)
    client.register_query_types(
        *QUERY_TYPES, result_types=tuple(QUERY_RESULT_TYPES))
    client.connect()
    try:
        result = client.query(GetBoardStateQuery(), timeout=5.0)
        assert isinstance(result, BoardStateResult)
        assert result.success and result.cells == [
            [10, 11]] and result.game_time == 2.5
        # 未注册处理器的查询返回基类错误响应，而不是超时
        missing = client.query(GetGameContextQuery(), timeout=5.0)
        assert type(missing) is BaseQueryResult and not missing.success
        assert "No handler" in (missing.error or "")
    finally:
        client.disconnect()
        server.stop()


@pytest.mark.parametrize("mode", ["deadline", "cancel", "stop"])
def test_command_io_queued_work_never_runs_after_end(zmq_main, mode):
    entered, release = threading.Event(), threading.Event()
    executed = []

    def execute(name, arguments):
        executed.append(name)
        entered.set()
        assert release.wait(2)
        return {"success": True}

    owner = CommandIO(zmq_main.endpoint, lambda command: False, execute)
    first = PendingCall("block", {}, ("s", 1), time.monotonic() + 5)
    queued = PendingCall("queued", {}, ("s", 2), time.monotonic() + 5)
    owner.start()
    try:
        owner.submit(first)
        assert entered.wait(1)
        owner.submit(queued)
        if mode == "deadline":
            queued.deadline = time.monotonic() - 1
        elif mode == "cancel":
            RequestBridge._cancel(queued, "cancelled")
        else:
            owner.stop()
        release.set()
        assert queued.future.result(timeout=1)["outcome"] == "not_executed"
    finally:
        release.set()
        owner.stop()
    assert executed == [
        "block"] and not zmq_main.commands and not owner.thread.is_alive()
    with pytest.raises(RuntimeError, match="stopped"):
        owner.submit(queued)


def test_command_io_rechecks_revocation_before_send(zmq_main):
    permissions = []

    def authorize(command):
        permissions.append(type(command))
        return False

    def execute(name, arguments):
        return {"success": owner.request(MouseClickCommand(), timeout=0.2).success}

    owner = CommandIO(zmq_main.endpoint, authorize, execute)
    bridge = RequestBridge(owner.submit)
    owner.start()
    try:
        assert not bridge.call("click", {}, ("s", 1), 1)["success"]
        assert permissions == [MouseClickCommand] and not zmq_main.commands
    finally:
        bridge.stop()
        owner.stop()


def test_visible_board_only_and_copy(sdk):
    registry = sdk.registry
    assert not registry.execute_function("get_board_state", {})["success"]
    registry.update_board(BoardUpdateEvent(rows=1, cols=9, game_board=[
                          [10, 11, 12, 14, 15, 16, -1, 99, 8]]))
    assert not registry.execute_function("get_board_state", {})["success"]
    registry.update_status(GameStatusChangeEvent(current_status=1))
    result = registry.execute_function("get_board_state", {})
    assert result["cells"] == [[-1, "F", -1, "X", "M", "m", -1, -1, 8]]
    result["cells"][0][0] = 8
    assert registry.board["cells"][0][0] == -1
    assert sdk.queries and all(isinstance(
        q, GetBoardStateQuery) for q in sdk.queries)
    assert not sdk.calls


@pytest.mark.parametrize("status", list(STATUS_NAMES))
def test_actual_event_state_map(sdk, status):
    set_board(sdk.registry, status)
    assert sdk.registry.execute_function("get_board_state", {})[
        "game_status"] == STATUS_NAMES[status]


@pytest.mark.parametrize("tool,query_type", [
    ("get_board_state", GetBoardStateQuery),
    ("get_game_status", GetGameStatusQuery),
    ("get_game_context", GetGameContextQuery),
])
def test_read_only_tools_actively_request_snapshot(tool, query_type):
    calls = []
    base = dict(game_status="playing", game_status_code=2, game_time=1.0,
                rtime=0.0, mines_remaining=3, rows=1, cols=2, mines=3,
                level=3, level_name="初级", mode=0, mode_name="标准")
    payloads = {
        "get_board_state": dict(rows=1, cols=2, mines_remaining=3, game_time=1.0,
                                cells=[[10, 11]], game_status="playing",
                                game_status_code=2),
        "get_game_status": base,
        "get_game_context": dict(base, bbbv=4, bbbv_solved=1, progress=0.25),
    }
    templates = {
        "get_board_state": BoardStateResult,
        "get_game_status": GameStatusResult,
        "get_game_context": GameContextResult,
    }

    def query(value, timeout):
        calls.append(value)
        assert timeout == 3.0
        return templates[tool](request_id="r", **payloads[tool])

    registry = MinesweeperTools(
        lambda command_type: False, lambda *a: None, query)
    result = registry.execute_function(tool, {})
    assert isinstance(calls[0], query_type)
    assert result["success"] and result["source"] == "live"
    if tool == "get_board_state":
        assert result["cells"] == [[-1, "F"]]


def test_read_only_tool_falls_back_to_cache_and_reports_source():
    registry = MinesweeperTools(lambda command_type: False, lambda *a: None,
                                lambda query, timeout: None)
    registry.update_status(GameStatusChangeEvent(current_status=2))
    registry.update_board(BoardUpdateEvent(rows=1, cols=2, game_board=[[10, 11]],
                                           mines_remaining=1, game_time=4.0))
    board = registry.execute_function("get_board_state", {})
    assert board["success"] and board["source"] == "cache" and board["cells"] == [
        [-1, "F"]]
    status = registry.execute_function("get_game_status", {})
    assert status["source"] == "cache" and status["game_status"] == "playing"
    context = registry.execute_function("get_game_context", {})
    assert not context["success"] and context["outcome"] == "unknown"


def test_read_only_tool_rejects_arguments():
    registry = MinesweeperTools(
        lambda command_type: False, lambda command, timeout: None)
    for tool in ("get_board_state", "get_game_status", "get_game_context"):
        assert not registry.execute_function(tool, {"extra": 1})["success"]


def _ready_board_query(calls):
    def query(value, timeout):
        calls.append(type(value).__name__)
        return BoardStateResult(request_id="r", cells=[[10, 11]], rows=1, cols=2,
                                mines_remaining=1, game_time=0.0,
                                game_status="ready", game_status_code=1)
    return query


def test_board_query_syncs_status_for_control_tools():
    """插件晚于对局启动、没收到状态事件时，读取棋盘也应同步状态"""
    commands, calls = [], []

    def request(command, timeout):
        commands.append(command)
        return CommandResponse(request_id="r", success=True)

    registry = MinesweeperTools(
        lambda t: True, request, _ready_board_query(calls))
    assert registry.status is None
    snapshot = registry.execute_function("get_board_state", {})
    assert snapshot["success"] and snapshot["game_status"] == "ready"
    assert registry.status == 1, "查询后应同步状态"
    assert commands == []

    result = registry.execute_function("click_cell", {"row": 0, "col": 0})
    assert result["success"] and isinstance(commands[0], MouseClickCommand)
    assert calls.count("GetBoardStateQuery") == 1, "状态已同步，不应再额外刷新"


def test_control_tool_refreshes_when_cache_is_empty():
    """控制命令遇到未知状态时主动刷新一次，而不是直接判为不可用"""
    calls, commands = [], []

    def request(command, timeout):
        commands.append(command)
        return CommandResponse(request_id="r", success=True)

    registry = MinesweeperTools(
        lambda t: True, request, _ready_board_query(calls))
    result = registry.execute_function("click_cell", {"row": 0, "col": 1})
    assert result["success"] and result["outcome"] == "confirmed"
    assert "GetBoardStateQuery" in calls
    assert isinstance(commands[0], MouseClickCommand)
    assert registry.status == 1


def test_control_tool_still_rejects_when_refresh_unavailable():
    """没有查询通道时保持原有拒绝语义"""
    registry = MinesweeperTools(lambda t: True, lambda *a: None)
    result = registry.execute_function("click_cell", {"row": 0, "col": 0})
    assert not result["success"]
    assert "No actionable visible board" in result["error"]


def test_start_new_game_allowed_after_refresh_in_ready_state():
    calls, commands = [], []

    def request(command, timeout):
        commands.append(command)
        return CommandResponse(request_id="r", success=True)

    registry = MinesweeperTools(
        lambda t: True, request, _ready_board_query(calls))
    result = registry.execute_function(
        "start_new_game", {"difficulty": "easy"})
    assert result["success"], result
    assert isinstance(commands[0], NewGameCommand) and commands[0].level == 3


@pytest.mark.parametrize("arguments", [
    {"row": True, "col": 0}, {"row": 0, "col": False}, {"row": "0", "col": 0},
    {"row": 0.0, "col": 0}, {"row": -1, "col": 0}, {"row": 2, "col": 0},
    {"row": 0, "col": 3}, {"row": 0, "col": 0, "button": "LEFT"},
    {"row": 0, "col": 0, "button": None}, {
        "row": 0, "col": 0, "hidden": True}, {},
])
def test_reject_click_inputs_without_sending(sdk, arguments):
    set_board(sdk.registry)
    assert not sdk.registry.execute_function(
        "click_cell", arguments)["success"]
    assert not sdk.calls


@pytest.mark.parametrize("button,value", [("left", 0), ("middle", 1), ("right", 2)])
def test_click_requires_confirmation_and_fresh_board(sdk, button, value):
    set_board(sdk.registry)
    result = sdk.registry.execute_function(
        "click_cell", {"row": 0, "col": 0, "button": button})
    assert result["outcome"] == "confirmed"
    assert isinstance(sdk.calls[0], MouseClickCommand)
    assert sdk.calls[0].button == value
    assert not sdk.registry.execute_function(
        "click_cell", {"row": 0, "col": 0})["success"]
    assert len(sdk.calls) == 1


def test_batch_clicks_are_validated_before_any_command(sdk):
    sdk.registry.query = lambda *args: BoardStateResult(
        cells=[[10, 10]], rows=1, cols=2, game_status="playing", game_status_code=2)
    for invalid in ({"row": 0, "col": 2}, {"row": True, "col": 0},
                    {"row": 0, "col": 0, "button": "bad"}, None):
        result = sdk.registry.execute_function("click_cell", {
            "clicks": [{"row": 0, "col": 0}, invalid]})
        assert not result["success"] and result["invalid_index"] == 1
        assert result["outcome"] == "not_executed" and not sdk.calls
        assert result["completed"] == 0 and result["results"] == []
        assert result["requested"] == result["unattempted"] == 2


@pytest.mark.parametrize("arguments", [
    {"clicks": []}, {"clicks": None}, {"clicks": {}}, {"clicks": "bad"},
    {"clicks": [{"row": 0, "col": 0}] * (MAX_BATCH_CLICKS + 1)},
    {"clicks": [{"row": 0, "col": 0}], "row": 0, "col": 0},
    {"clicks": [{"row": 0, "col": 0}], "button": "left"},
    {"clicks": [{"row": 0}]}, {"clicks": [{"row": 0, "col": -1}]},
    {"clicks": [{"row": 0.0, "col": 0}]},
    {"clicks": [{"row": 0, "col": 0, "extra": True}]},
])
def test_batch_rejects_invalid_envelopes_without_io(sdk, arguments):
    result = sdk.registry.execute_function("click_cell", arguments)
    assert not result["success"] and result["outcome"] == "not_executed"
    assert result["completed"] == 0 and result["results"] == []
    assert result["stopped_index"] == 0
    assert result["unattempted"] == result["requested"]
    assert not sdk.calls and not sdk.queries


def test_batch_accepts_limit_and_publishes_independent_progress(sdk):
    sdk.registry.query = lambda *args: BoardStateResult(
        cells=[[10]], rows=1, cols=1, game_status="playing", game_status_code=2)
    retained = []
    sdk.registry.report_progress = retained.append
    result = sdk.registry.execute_function("click_cell", {
        "clicks": [{"row": 0, "col": 0}] * MAX_BATCH_CLICKS})
    assert result["success"] and result["completed"] == MAX_BATCH_CLICKS
    assert len(sdk.calls) == MAX_BATCH_CLICKS
    assert len(retained) == MAX_BATCH_CLICKS + 1
    assert retained[0]["results"] == [] and retained[1]["completed"] == 1
    result["results"][0]["success"] = False
    assert retained[-1]["results"][0]["success"] is True


@pytest.mark.parametrize("reason", [
    "revoked", "unavailable", "finished", "ready", "dimensions", "time_reset",
    "reset", "status_event", "invalid_board_event",
])
def test_batch_stops_after_permission_or_board_changes(sdk, reason):
    def query(value, timeout):
        snapshot = BoardStateResult(cells=[[10, 10]], rows=1, cols=2, game_time=5.0,
                                    game_status="playing", game_status_code=2)
        if sdk.calls:
            if reason == "unavailable":
                return None
            if reason == "finished":
                snapshot.game_status, snapshot.game_status_code = "win", 3
            elif reason == "ready":
                snapshot.game_status, snapshot.game_status_code = "ready", 1
            elif reason == "dimensions":
                snapshot.cells, snapshot.cols = [[10]], 1
            elif reason == "time_reset":
                snapshot.game_time = 0.0
        return snapshot

    def request(command, timeout):
        sdk.calls.append(command)
        if reason == "revoked":
            sdk.authorized = False
        elif reason == "reset":
            sdk.registry.reset()
        elif reason == "status_event":
            sdk.registry.update_status(GameStatusChangeEvent(current_status=1))
            sdk.registry.update_status(GameStatusChangeEvent(current_status=2))
        elif reason == "invalid_board_event":
            sdk.registry.update_board(BoardUpdateEvent(rows=1, cols=2, game_board=[]))
        return CommandResponse(request_id="first", success=True)

    sdk.registry.query, sdk.registry.request = query, request
    result = sdk.registry.execute_function("click_cell", {
        "clicks": [{"row": 0, "col": 0}, {"row": 0, "col": 1}]})
    assert not result["success"] and result["outcome"] == "partial"
    assert result["completed"] == 1 and result["stopped_index"] == 1
    assert len(sdk.calls) == 1


def test_batch_ready_right_clicks_restore_visible_board(sdk):
    def query(value, timeout):
        flagged = len(sdk.calls) % 2
        return BoardStateResult(cells=[[11 if flagged else 10]], rows=1, cols=1,
                                mines_remaining=1 - flagged,
                                game_status="ready", game_status_code=1)

    sdk.registry.query = query
    before = sdk.registry.execute_function("get_board_state", {})
    result = sdk.registry.execute_function("click_cell", {
        "clicks": [{"row": 0, "col": 0, "button": "right"}] * 2})
    after = sdk.registry.execute_function("get_board_state", {})
    assert result["success"] and result["outcome"] == "confirmed"
    assert result["requested"] == result["completed"] == 2
    assert result["stopped_index"] is None and result["unattempted"] == 0
    assert [entry["outcome"] for entry in result["results"]] == ["confirmed"] * 2
    assert len(sdk.calls) == 2 and all(command.button == 2 for command in sdk.calls)
    assert before["cells"] == after["cells"] == [[-1]]
    assert before["mines_remaining"] == after["mines_remaining"] == 1


@pytest.mark.parametrize("statuses", [
    ("playing", "ready"), ("joking", "ready"),
    ("ready", "playing", "ready"), ("ready", "joking", "ready"),
])
def test_batch_stops_when_observed_active_game_returns_to_ready(sdk, statuses):
    def query(value, timeout):
        status = statuses[len(sdk.calls)]
        return BoardStateResult(cells=[[10]], rows=1, cols=1,
                                game_status=status, game_status_code=1 if status == "ready" else 2)

    sdk.registry.query = query
    result = sdk.registry.execute_function("click_cell", {
        "clicks": [{"row": 0, "col": 0, "button": "right"}] * len(statuses)})
    assert not result["success"] and result["outcome"] == "partial"
    assert result["completed"] == result["stopped_index"] == len(statuses) - 1
    assert len(sdk.calls) == len(statuses) - 1
    assert result["results"][-1]["outcome"] == "not_executed"
    assert result["error"] == "Game returned to ready state; batch stopped"


def test_batch_clicks_confirm_in_order_and_refresh_each_step(sdk):
    operations = []

    def query(value, timeout):
        operations.append("query")
        return BoardStateResult(cells=[[10, 10, 10]], rows=1, cols=3,
                                game_status="playing", game_status_code=2)

    def request(command, timeout):
        operations.append(command.col)
        return CommandResponse(request_id=str(command.col), success=True)

    sdk.registry.query, sdk.registry.request = query, request
    arguments = {"clicks": [{"row": 0, "col": 0},
                            {"row": 0, "col": 1, "button": "right"},
                            {"row": 0, "col": 2, "button": "middle"}]}
    original = copy.deepcopy(arguments)
    result = sdk.registry.execute_function("click_cell", arguments)
    assert result["success"] and result["outcome"] == "confirmed"
    assert result["requested"] == result["completed"] == 3
    assert result["stopped_index"] is None and result["unattempted"] == 0
    assert [entry["request_id"] for entry in result["results"]] == ["0", "1", "2"]
    assert operations == ["query", 0, "query", 1, "query", 2]
    assert arguments == original


@pytest.mark.parametrize("invalid", [
    {"game_status_code": 99}, {"game_status_code": True},
    {"game_status": "jowin"}, {"game_time": float("nan")},
])
def test_batch_stops_on_invalid_live_snapshot(sdk, invalid):
    snapshots = [0]

    def query(value, timeout):
        snapshots[0] += 1
        snapshot = BoardStateResult(cells=[[10, 10]], rows=1, cols=2,
                                    game_status="playing", game_status_code=2)
        if snapshots[0] > 1:
            for field, value in invalid.items():
                setattr(snapshot, field, value)
        return snapshot

    sdk.registry.query = query
    result = sdk.registry.execute_function("click_cell", {
        "clicks": [{"row": 0, "col": 0}, {"row": 0, "col": 1}]})
    assert not result["success"] and result["completed"] == 1
    assert result["stopped_index"] == 1 and len(sdk.calls) == 1


@pytest.mark.parametrize("outcome", ["rejected", "timeout"])
def test_batch_clicks_stop_after_first_unconfirmed_action(sdk, outcome):
    sdk.registry.query = lambda *args: BoardStateResult(
        cells=[[10, 10, 10]], rows=1, cols=3, game_status="playing", game_status_code=2)

    def request(command, timeout):
        sdk.calls.append(command)
        if len(sdk.calls) == 2 and outcome == "timeout":
            raise TimeoutError
        return CommandResponse(request_id=str(command.col), success=len(sdk.calls) == 1,
                               error="Rejected" if len(sdk.calls) == 2 else None)

    sdk.registry.request = request
    result = sdk.registry.execute_function("click_cell", {
        "clicks": [{"row": 0, "col": index} for index in range(3)]})
    assert not result["success"] and result["completed"] == 1
    assert result["outcome"] == ("unknown" if outcome == "timeout" else "partial")
    assert result["stopped_index"] == 1 and result["unattempted"] == 1
    assert len(sdk.calls) == 2 and len(result["results"]) == 2


@pytest.mark.parametrize("stage", ["before_click", "after_confirmation", "in_flight"])
def test_batch_cancellation_preserves_confirmed_progress(sdk, stage):
    call = PendingCall("click_cell", {"clicks": [{"row": 0, "col": 0},
                                                {"row": 0, "col": 1}]},
                       ("session", 1), time.monotonic() + 5)
    owner = CommandIO("tcp://127.0.0.1:50000", lambda command: True,
                      sdk.registry.execute_function)
    owner.thread, owner.active = threading.current_thread(), call
    sdk.registry.report_progress = owner.report_progress
    sdk.registry.query = lambda *args: BoardStateResult(
        cells=[[10, 10]], rows=1, cols=2, game_status="playing", game_status_code=2)

    def send(payload, flags):
        sdk.calls.append(payload)

    def request(command, timeout):
        if command.col == 0:
            return CommandResponse(request_id="first", success=True)
        if stage == "in_flight":
            owner._socket = SimpleNamespace(
                poll=lambda *args: True, send=send,
                recv_multipart=lambda **kwargs: RequestBridge._cancel(call, "cancelled"))
            return owner.request(command, timeout)
        raise AssertionError("Second click must not be sent")

    def report(result):
        owner.report_progress(result)
        if (stage == "before_click" and result["completed"] == 0
                or stage == "after_confirmation" and result["completed"] == 1):
            RequestBridge._cancel(call, "cancelled")
            raise TimeoutError

    sdk.registry.request, sdk.registry.report_progress = request, report
    RequestBridge.execute(call, sdk.registry.execute_function)
    result = call.future.result()
    assert not result["success"]
    assert result["completed"] == (0 if stage == "before_click" else 1)
    assert result["outcome"] == {"before_click": "not_executed",
                                 "after_confirmation": "partial", "in_flight": "unknown"}[stage]
    assert result["stopped_index"] == (0 if stage == "before_click" else 1)
    assert len(sdk.calls) == (1 if stage == "in_flight" else 0)
    assert result["unattempted"] == {"before_click": 2, "after_confirmation": 1,
                                     "in_flight": 0}[stage]


@pytest.mark.parametrize("confirmed", [True, False])
def test_batch_cancellation_after_response_keeps_confirmation(sdk, confirmed):
    call = PendingCall("click_cell", {"clicks": [{"row": 0, "col": 0},
                                                {"row": 0, "col": 1}]},
                       ("session", 1), time.monotonic() + 5)
    owner = CommandIO("tcp://127.0.0.1:50000", lambda command: True,
                      sdk.registry.execute_function)
    owner.thread, owner.active = threading.current_thread(), call
    sdk.registry.report_progress = owner.report_progress
    sdk.registry.query = lambda *args: BoardStateResult(
        cells=[[10, 10]], rows=1, cols=2, game_status="playing", game_status_code=2)
    sent = []
    owner._serializer.register_command_types(MouseClickCommand)

    def send(payload, flags):
        sent.append(owner._serializer.decode_command(payload))

    def receive(flags):
        return [owner._serializer.encode_response(CommandResponse(
            request_id=sent[-1].request_id, success=confirmed, error=None if confirmed else "Rejected"))]

    owner._socket = cast(zmq.Socket, SimpleNamespace(poll=lambda *args: True, send=send,
                                                    recv_multipart=receive))

    def request(command, timeout):
        response = owner.request(command, timeout)
        RequestBridge._cancel(call, "cancelled after response")
        return response

    sdk.registry.request = request
    RequestBridge.execute(call, sdk.registry.execute_function)
    result = call.future.result()
    assert len(sent) == 1 and not result["success"]
    assert result["completed"] == int(confirmed)
    assert result["outcome"] == ("partial" if confirmed else "not_executed")
    assert result["results"][0]["success"] is confirmed
    assert result["stopped_index"] == int(confirmed) and result["unattempted"] == 1


@pytest.mark.parametrize("confirmed", [0, 1])
@pytest.mark.parametrize("stage", ["timeout", "backpressure"])
def test_batch_unsent_command_is_not_unknown(sdk, monkeypatch, confirmed, stage):
    call = PendingCall("click_cell", {"clicks": [{"row": 0, "col": index}
                                                for index in range(3)]},
                       ("session", 1), time.monotonic() + 30)
    owner = CommandIO("tcp://127.0.0.1:50000", lambda command: True,
                      sdk.registry.execute_function)
    owner.thread, owner.active = threading.current_thread(), call
    sdk.registry.report_progress = owner.report_progress
    sdk.registry.query = lambda *args: BoardStateResult(
        cells=[[10, 10, 10]], rows=1, cols=3, game_status="playing", game_status_code=2)
    clock = [time.monotonic()]
    monkeypatch.setattr(command_io, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    attempts = []

    def poll(*args):
        if stage == "timeout":
            clock[0] += 4
            return False
        return True

    def send(payload, flags):
        attempts.append(payload)
        raise zmq.Again()

    owner._socket = cast(zmq.Socket, SimpleNamespace(
        poll=poll, send=send, close=lambda **kwargs: None))

    def request(command, timeout):
        if command.col < confirmed:
            sdk.calls.append(command)
            return CommandResponse(request_id=str(command.col), success=True)
        return owner.request(command, timeout)

    sdk.registry.request = request
    RequestBridge.execute(call, sdk.registry.execute_function)
    result = call.future.result()
    assert not result["success"] and result["completed"] == confirmed
    assert result["outcome"] == ("partial" if confirmed else "not_executed")
    assert result["results"][-1]["outcome"] == "not_executed"
    assert result["stopped_index"] == confirmed and result["unattempted"] == 2 - confirmed
    assert len(result["results"]) == confirmed + 1
    assert len(sdk.calls) == confirmed and len(attempts) == int(stage == "backpressure")


@pytest.mark.parametrize("difficulty,level", [("easy", 3), ("medium", 4), ("hard", 5)])
def test_new_game_and_no_automatic_restart(sdk, difficulty, level):
    set_board(sdk.registry, 3)
    result = sdk.registry.execute_function(
        "start_new_game", {"difficulty": difficulty})
    assert result["success"] and isinstance(sdk.calls[0], NewGameCommand)
    assert sdk.calls[0].level == level
    assert sdk.registry.board is None and sdk.registry.status is None
    assert not sdk.registry.execute_function("start_new_game", {})["success"]


@pytest.mark.parametrize("status", [None, 0, 2, 5, 6, 7, 8, 99])
def test_never_overwrite_active_or_unknown_game(sdk, status):
    set_board(sdk.registry)
    sdk.registry.status = status
    assert not sdk.registry.execute_function("start_new_game", {})["success"]
    assert not sdk.calls


@pytest.mark.parametrize("difficulty", ["expert", "", None, True, 3, []])
def test_reject_difficulty(sdk, difficulty):
    set_board(sdk.registry)
    assert not sdk.registry.execute_function(
        "start_new_game", {"difficulty": difficulty})["success"]
    assert not sdk.calls


@pytest.mark.parametrize("name,args", [("click_cell", {"row": 0, "col": 0}), ("start_new_game", {})])
def test_official_authorization_and_main_switch(sdk, name, args):
    set_board(sdk.registry)
    sdk.authorized = False
    assert not sdk.registry.execute_function(name, args)["success"]
    assert not sdk.calls
    sdk.authorized = True
    sdk.response = False
    assert not sdk.registry.execute_function(name, args)["success"]
    assert len(sdk.calls) == 1


@pytest.mark.parametrize("mode", ["timeout", "no_response"])
def test_unknown_command_result_not_success_or_retry(sdk, mode):
    set_board(sdk.registry)
    sdk.raises = mode == "timeout"
    sdk.response = None
    result = sdk.registry.execute_function("click_cell", {"row": 0, "col": 0})
    assert result["outcome"] == "unknown" and not result["success"]
    assert "retry" in result["error"]
    assert not sdk.registry.execute_function(
        "click_cell", {"row": 0, "col": 0})["success"]
    assert len(sdk.calls) == 1


def test_invalid_board_and_new_ready_invalidates_cache(sdk):
    set_board(sdk.registry, 2)
    sdk.registry.update_status(
        GameStatusChangeEvent(last_status=2, current_status=1))
    assert sdk.registry.board is None
    sdk.registry.update_board(BoardUpdateEvent(
        rows=2, cols=3, game_board=[[10]]))
    assert sdk.registry.board is None
    sdk.registry.update_board(BoardUpdateEvent(
        rows=1, cols=1, game_board=[[True]]))
    assert sdk.registry.board is None
    sdk.registry.update_board(BoardUpdateEvent(
        rows=1, cols=1, game_board=[[10]], game_time=float("nan")))
    assert sdk.registry.board is None


@pytest.mark.parametrize("response", [None, True, {"success": True}, SimpleNamespace(success=True),
                                      CommandResponse(request_id="fake", success=cast(bool, 1))])
def test_tools_require_actual_typed_confirmation(sdk, response):
    set_board(sdk.registry)
    sdk.registry.request = lambda *args, **kwargs: response
    result = sdk.registry.execute_function("click_cell", {"row": 0, "col": 0})
    assert result["outcome"] == "unknown" and not result["success"]


@pytest.mark.parametrize("outcome", ["timeout", "rejected", "confirmed"])
def test_tools_preserve_new_events_received_during_command(sdk, outcome):
    set_board(sdk.registry)

    def request(command, timeout):
        set_board(sdk.registry, 2)
        if outcome == "timeout":
            raise TimeoutError
        return CommandResponse(request_id="fake", success=outcome == "confirmed")

    sdk.registry.request = request
    result = sdk.registry.execute_function("click_cell", {"row": 0, "col": 0})
    assert result["success"] == (outcome == "confirmed")
    assert sdk.registry.execute_function("get_board_state", {})[
        "game_status"] == STATUS_NAMES[2]


def http_request(server, message=None, *, extra=None, raw=None, method="POST", path="/mcp"):
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": mcp_server.PROTOCOL_VERSION}
    headers.update(extra or {})
    body = raw if raw is not None else json.dumps(
        message) if message is not None else None
    connection = http.client.HTTPConnection(
        "127.0.0.1", server.port, timeout=2)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        return response.status, dict(response.getheaders()), json.loads(data) if data else None
    finally:
        connection.close()


def rpc_body(response) -> dict:
    body = response[2]
    assert isinstance(body, dict)
    return body


def initialize(server, version=mcp_server.PROTOCOL_VERSION, initialized=True):
    status, headers, body = http_request(server, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "tests", "version": "1"}}})
    assert isinstance(body, dict)
    assert status == 200 and body["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSION
    session = {"Mcp-Session-Id": headers["Mcp-Session-Id"]}
    if initialized:
        assert http_request(server, {
                            "jsonrpc": "2.0", "method": "notifications/initialized"}, extra=session)[0] == 202
    return session


PROTOCOL_TOOLS = [{"name": "echo", "inputSchema": {"type": "object"}}]


@pytest.fixture
def protocol_service():
    executed = []

    def callback(name, arguments):
        executed.append((name, arguments))
        return {"success": True, "echo": arguments}

    server = McpServer(0, PROTOCOL_TOOLS,
                       dispatcher=lambda call: RequestBridge.execute(call, callback))
    server.start()
    try:
        yield server, executed
    finally:
        server.stop()


def test_protocol_mock_roundtrip_and_idempotent_start(protocol_service):
    server, executed = protocol_service
    port, thread = server.port, server.thread
    server.start()
    assert (server.port, server.thread) == (port, thread)
    assert server.endpoint == f"http://127.0.0.1:{port}/mcp"
    session = initialize(server)
    assert session["Mcp-Session-Id"].isascii()
    for request_id in [0, "", -1, "echo-request"]:
        status, headers, body = http_request(server, {
            "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": "echo", "arguments": {"value": request_id}}}, extra=session)
        assert isinstance(body, dict)
        assert status == 200 and headers["Content-Type"] == "application/json"
        assert body["id"] == request_id and not body["result"]["isError"]
        assert body["result"]["structuredContent"]["echo"] == {
            "value": request_id}
        assert json.loads(body["result"]["content"][0]["text"])["success"]
    listing = rpc_body(http_request(
        server, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, extra=session))
    assert listing["result"]["tools"] == PROTOCOL_TOOLS
    assert len(executed) == 4


def test_protocol_restart_invalidates_sessions(protocol_service):
    server, _ = protocol_service
    session = initialize(server)
    thread = server.thread
    server.stop()
    server.stop()
    assert not thread.is_alive() and not server.sessions and server.http is None
    server.start()
    ping = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
    assert http_request(server, ping, extra=session)[0] == 404
    assert rpc_body(http_request(server, ping, extra=initialize(server)))[
        "result"] == {}


@pytest.mark.parametrize("extra,status", [
    ({"Host": "localhost"}, 403),
    ({"Origin": "https://evil.example"}, 403), ({"Origin": "null"}, 403),
    ({"MCP-Protocol-Version": "2026-01-01"},
     400), ({"Accept": "application/json"}, 406),
    ({"Content-Type": "text/plain"},
     415), ({"Content-Length": str(mcp_server.MAX_BODY + 1)}, 413),
    ({"Transfer-Encoding": "chunked"}, 400),
])
def test_protocol_security(protocol_service, extra, status):
    server, executed = protocol_service
    assert http_request(server, {}, extra=extra)[0] == status
    assert not executed


@pytest.mark.parametrize("raw,code", [
    ("{", -32700), ('{"value":NaN}', -32700), ("[]", -32600),
    ('{"jsonrpc":"2.0","method":"ping","id":null}', -32600),
    ('{"jsonrpc":"2.0","method":"ping","id":true}', -32600),
    ('{"jsonrpc":"2.0","method":"ping","id":1.5}', -32600),
])
def test_protocol_invalid_jsonrpc(protocol_service, raw, code):
    response = http_request(protocol_service[0], raw=raw)
    assert response[0] == 400 and rpc_body(response)["error"]["code"] == code


def test_protocol_sessions_notifications_and_errors(protocol_service):
    server, executed = protocol_service
    ping = {"jsonrpc": "2.0", "id": "ping", "method": "ping"}
    assert http_request(server, ping)[0] == 400
    assert http_request(server, ping, extra={
                        "Mcp-Session-Id": "unknown"})[0] == 404
    session = initialize(server, version="2099-01-01", initialized=False)
    listing = {"jsonrpc": "2.0", "id": "list", "method": "tools/list"}
    assert rpc_body(http_request(server, listing, extra=session))[
        "error"]["code"] == -32000
    for method in ["notifications/initialized", "notifications/unknown", "tools/call"]:
        response = http_request(server, {"jsonrpc": "2.0", "method": method,
                                         "params": {"name": "echo"}}, extra=session)
        assert response[0] == 202 and response[2] is None and response[1]["Content-Length"] == "0"
    assert not executed
    assert rpc_body(http_request(server, ping, extra=session))["result"] == {}
    for method, params, code in [("unknown", {}, -32601), ("tools/list", {"cursor": "bad"}, -32602),
                                 ("tools/call", {"name": "unknown"}, -32602),
                                 ("tools/call", {"name": "echo",
                                  "arguments": []}, -32602),
                                 ("ping", [], -32602)]:
        body = rpc_body(http_request(server, {"jsonrpc": "2.0", "id": "error-id", "method": method,
                                              "params": params}, extra=session))
        assert body["id"] == "error-id" and body["error"]["code"] == code
    assert http_request(server, method="GET", extra=session)[0] == 405
    assert http_request(server, method="DELETE", extra=session)[0] == 200
    assert http_request(server, ping, extra=session)[0] == 404
    assert http_request(server, method="GET", extra=session)[0] == 404


def test_protocol_missing_version_header_and_matching_origin(protocol_service):
    server, _ = protocol_service
    connection = http.client.HTTPConnection(
        "127.0.0.1", server.port, timeout=2)
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream", "Origin": f"http://127.0.0.1:{server.port}"}
    try:
        connection.request("POST", "/mcp", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": mcp_server.PROTOCOL_VERSION, "capabilities": {},
                                      "clientInfo": {"name": "mock", "version": "1"}}}), headers)
        response = connection.getresponse()
        assert response.status == 200
        session = response.getheader("Mcp-Session-Id")
        assert session
        response.read()
    finally:
        connection.close()
    headers["Mcp-Session-Id"] = session
    connection = http.client.HTTPConnection(
        "127.0.0.1", server.port, timeout=2)
    try:
        connection.request(
            "POST", "/mcp", json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}), headers)
        response = connection.getresponse()
        assert response.status == 200 and json.loads(response.read())[
            "result"] == {}
    finally:
        connection.close()


@pytest.mark.parametrize("outcome", [None, {"success": "yes"}, {"success": True, "value": float("nan")},
                                     {"success": True, "value": object()}])
def test_protocol_invalid_callback_results(protocol_service, outcome):
    server, _ = protocol_service
    server.bridge.dispatch = lambda call: RequestBridge.execute(
        call, lambda *args: outcome)
    session = initialize(server)
    response = http_request(server, {"jsonrpc": "2.0", "id": "bad-result", "method": "tools/call",
                                     "params": {"name": "echo"}}, extra=session)
    body = rpc_body(response)
    assert response[0] == 200 and body["id"] == "bad-result" and body["error"]["code"] == -32603


def test_protocol_blocking_dispatch_timeout_and_bounded_stop(monkeypatch):
    monkeypatch.setattr(mcp_server, "CALL_TIMEOUT", 0.05)
    monkeypatch.setattr(mcp_server, "STOP_TIMEOUT", 0.1)
    entered, release = threading.Event(), threading.Event()
    executed = []

    def dispatch(call):
        entered.set()
        release.wait(2)
        RequestBridge.execute(
            call, lambda *args: executed.append(args) or {"success": True})

    server = McpServer(0, PROTOCOL_TOOLS, dispatcher=dispatch)
    server.start()
    try:
        session = initialize(server)
        start = time.monotonic()
        result = rpc_body(http_request(server, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                                "params": {"name": "echo"}}, extra=session))["result"]
        assert entered.is_set() and time.monotonic() - start < 1
        assert result["isError"] and result["structuredContent"]["outcome"] == "not_executed"
        for request_id in range(3, mcp_server.MAX_CONNECTIONS + 2):
            result = rpc_body(http_request(server, {"jsonrpc": "2.0", "id": request_id,
                              "method": "tools/call", "params": {"name": "echo"}}, extra=session))["result"]
            assert result["isError"]
        result = rpc_body(http_request(server, {"jsonrpc": "2.0", "id": "overflow",
                          "method": "tools/call", "params": {"name": "echo"}}, extra=session))["result"]
        assert "queue full" in result["structuredContent"]["error"]
        assert len(server.bridge.workers) == mcp_server.MAX_CONNECTIONS
        bridge = server.bridge
        start = time.monotonic()
        server.stop()
        assert time.monotonic() - start < 0.5 and not server.sessions and not bridge.pending
        with pytest.raises(RuntimeError, match="Previous dispatchers"):
            server.start()
        release.set()
        bridge._wait_until(time.monotonic() + 1)
        assert not executed and not bridge.workers
    finally:
        release.set()
        server.stop()


@pytest.mark.parametrize("duplicate", ["Host", "Origin", "Content-Length"])
def test_protocol_duplicate_security_headers(protocol_service, duplicate):
    server, executed = protocol_service
    values = {"Host": f"127.0.0.1:{server.port}", "Origin": f"http://127.0.0.1:{server.port}",
              "Content-Length": "2"}
    headers = "".join(f"{name}: {value}\r\n" for name, value in values.items())
    request = (f"POST /mcp HTTP/1.1\r\n{headers}{duplicate}: {values[duplicate]}\r\n"
               "Content-Type: application/json\r\nAccept: application/json, text/event-stream\r\n\r\n{}")
    with socket.create_connection(("127.0.0.1", server.port), timeout=1) as connection:
        connection.sendall(request.encode("ascii"))
        response = http.client.HTTPResponse(connection)
        response.begin()
        assert response.status == 400
        response.read()
    assert not executed


def test_protocol_slow_body_deadline(monkeypatch, protocol_service):
    monkeypatch.setattr(mcp_server, "IO_TIMEOUT", 0.1)
    server, executed = protocol_service
    request = (f"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n"
               "Content-Type: application/json\r\n"
               "Accept: application/json, text/event-stream\r\nContent-Length: 64\r\n\r\n{")
    with socket.create_connection(("127.0.0.1", server.port), timeout=1) as connection:
        start = time.monotonic()
        connection.sendall(request.encode("ascii"))
        response = http.client.HTTPResponse(connection)
        response.begin()
        assert response.status == 408
        response.read()
        assert time.monotonic() - start < 1
    assert not executed


@pytest.fixture
def http_service(sdk):
    calls = queue.Queue()
    threads = []
    set_board(sdk.registry)

    def execute():
        while True:
            call = calls.get()
            if call is None:
                return
            threads.append(threading.get_ident())
            RequestBridge.execute(call, sdk.registry.execute_function)

    worker = threading.Thread(target=execute, daemon=True)
    worker.start()
    server = McpServer(free_port(), TOOLS, RequestBridge(calls.put))
    server.start()
    try:
        yield server, sdk, threads, worker
    finally:
        server.stop()
        calls.put(None)
        worker.join(2)
        assert not worker.is_alive()


def test_http_lifecycle_tools_and_serial_execution(http_service):
    server, sdk, threads, worker = http_service
    session = initialize(server)
    status, headers, body = http_request(
        server, {"jsonrpc": "2.0", "id": 2, "method": "ping"}, extra=session)
    assert isinstance(body, dict)
    assert status == 200 and body["result"] == {
    } and headers["MCP-Protocol-Version"] == "2025-11-25"
    listing = rpc_body(http_request(
        server, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, extra=session))
    assert {tool["name"] for tool in listing["result"]["tools"]} == {
        "get_board_state", "get_game_status", "get_game_context",
        "click_cell", "start_new_game",
    }

    def read_board(request_id):
        return rpc_body(http_request(server, {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                                              "params": {"name": "get_board_state"}}, extra=session))

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(read_board, [4, 5, 6]))
    assert all(result["result"]["structuredContent"]
               ["cells"][0][0] == -1 for result in results)
    assert set(threads) == {
        worker.ident} and worker.ident != threading.get_ident()
    result = rpc_body(http_request(server, {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                                            "params": {"name": "click_cell", "arguments": {"row": True, "col": 0}}}, extra=session))
    assert result["result"]["isError"]
    assert not [call for call in sdk.calls if isinstance(
        call, MouseClickCommand)]
    assert http_request(server, method="GET", extra=session)[0] == 405
    assert http_request(server, method="DELETE", extra=session)[0] == 200
    assert http_request(
        server, {"jsonrpc": "2.0", "id": 8, "method": "ping"}, extra=session)[0] == 404


@pytest.mark.parametrize("extra,status", [
    ({"Host": "evil.example"}, 403),
    ({"Origin": "https://evil.example"}, 403), ({"Origin": "null"}, 403),
    ({"MCP-Protocol-Version": "2099-01-01"},
     400), ({"Accept": "application/json"}, 406),
    ({"Content-Type": "text/plain"},
     415), ({"Content-Length": str(mcp_server.MAX_BODY + 1)}, 413),
    ({"Content-Length": "9" * 5000}, 413), ({"Transfer-Encoding": "chunked"}, 400),
])
def test_http_security_headers(http_service, extra, status):
    server, sdk, _, _ = http_service
    assert http_request(server, {}, extra=extra)[0] == status
    assert not sdk.calls


@pytest.mark.parametrize("raw,code", [("{", -32700), ('{"value":NaN}', -32700),
                                      ("[]", -32600), ("{}", -32600),
                                      ('{"jsonrpc":"2.0","method":"ping","id":true}', -32600)])
def test_jsonrpc_invalid_requests(http_service, raw, code):
    server = http_service[0]
    status, _, body = http_request(server, raw=raw)
    assert isinstance(body, dict)
    assert status == 400 and body["error"]["code"] == code


@pytest.mark.parametrize("method,params,code", [("missing", {}, -32601),
                                                ("tools/call", {"name": "missing"}, -32602), ("tools/call", {
                                                    "name": "click_cell", "arguments": []}, -32602),
                                                ("tools/list", {"cursor": "bad"}, -32602), ("ping", [], -32602)])
def test_jsonrpc_errors_preserve_id(http_service, method, params, code):
    server = http_service[0]
    session = initialize(server)
    status, _, body = http_request(server, {
                                   "jsonrpc": "2.0", "id": "request", "method": method, "params": params}, extra=session)
    assert isinstance(body, dict)
    assert status == 200 and body["id"] == "request" and body["error"]["code"] == code


def test_initialize_negotiation_and_notifications_do_not_execute(http_service):
    server, sdk, _, _ = http_service
    session = initialize(server, version="2099-01-01", initialized=False)
    assert rpc_body(http_request(server, {
                    "jsonrpc": "2.0", "id": 2, "method": "tools/list"}, extra=session))["error"]["code"] == -32000
    status, _, body = http_request(server, {"jsonrpc": "2.0", "method": "tools/call", "params": {
        "name": "click_cell", "arguments": {"row": 0, "col": 0}}}, extra=session)
    assert status == 202 and body is None
    assert http_request(server, {
                        "jsonrpc": "2.0", "method": "notifications/initialized"}, extra=session)[0] == 202
    assert not sdk.calls


def test_rate_limit_and_port_release(http_service):
    server = http_service[0]
    with server.lock:
        server.arrivals.extend([time.monotonic()] * 32)
    assert http_request(server, {})[0] == 429
    port = server.port
    server.stop()
    replacement = McpServer(port, TOOLS, RequestBridge(lambda call: None))
    try:
        replacement.start()
        assert replacement.port == port
    finally:
        replacement.stop()


@pytest.mark.parametrize("mode", ["timeout", "stop", "cancel", "session"])
def test_pending_request_never_executes_after_cancellation(mode):
    waiting = threading.Event()
    queued = []

    def dispatch(call):
        queued.append(call)
        waiting.set()

    bridge = RequestBridge(dispatch)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            bridge.call, "fake", {}, ("session", 1), 0.05 if mode == "timeout" else 2)
        assert waiting.wait(1)
        if mode == "stop":
            bridge.stop()
        elif mode == "cancel":
            bridge.cancel(("session", 1))
        elif mode == "session":
            bridge.cancel_session("session")
        result = future.result(timeout=1)
    executed = []
    RequestBridge.execute(
        queued[0], lambda *args: executed.append(args) or {"success": True})
    assert not executed and result["outcome"] == "not_executed"


@pytest.mark.parametrize("mode", ["deadline", "cancel", "stop", "session"])
def test_queued_batch_end_preserves_zero_progress(mode):
    call = PendingCall("click_cell", {"clicks": [{"row": 0, "col": 0},
                                                {"row": 0, "col": 1}]},
                       ("session", 1), time.monotonic() + 5)
    bridge = RequestBridge(lambda pending: None)
    bridge.pending[call.key] = call
    executed = []
    if mode == "deadline":
        call.deadline = time.monotonic() - 1
    elif mode == "cancel":
        bridge.cancel(call.key)
    elif mode == "stop":
        bridge.stop()
    else:
        bridge.cancel_session("session")
    RequestBridge.execute(call, lambda *args: executed.append(args) or {"success": True})
    result = call.future.result(timeout=1)
    assert not result["success"] and result["outcome"] == "not_executed"
    assert result["requested"] == result["unattempted"] == 2
    assert result["completed"] == 0 and result["results"] == []
    assert result["stopped_index"] == 0 and not executed


def test_inflight_timeout_is_unknown_not_retried():
    started, release = threading.Event(), threading.Event()
    executed = []
    workers = []

    def execute(name, arguments):
        executed.append(name)
        started.set()
        assert release.wait(2)
        return {"success": True}

    def dispatch(call):
        worker = threading.Thread(
            target=RequestBridge.execute, args=(call, execute))
        workers.append(worker)
        worker.start()

    bridge = RequestBridge(dispatch)
    try:
        result = bridge.call("fake", {}, ("session", 1), 0.05)
        assert started.is_set(
        ) and result["outcome"] == "unknown" and not result["success"]
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
    assert executed == ["fake"]


def test_pending_bound():
    bridge = RequestBridge(lambda call: None)
    bridge.pending = {("s", index): PendingCall("fake", {}, ("s", index), time.monotonic() + 2)
                      for index in range(mcp_server.MAX_CONNECTIONS)}
    assert not bridge.call("fake", {}, ("other", 1), 1)["success"]
    bridge.stop()


def test_slow_header_deadline_and_stop_close_connections(monkeypatch):
    monkeypatch.setattr(mcp_server, "IO_TIMEOUT", 0.15)
    server = McpServer(free_port(), TOOLS, RequestBridge(lambda call: None))
    server.start()
    connection = socket.create_connection(
        ("127.0.0.1", server.port), timeout=2)
    try:
        start = time.monotonic()
        connection.sendall(b"POST /mcp HTTP/1.1\r\nX-Incomplete: ")
        assert connection.recv(4096) == b""
        assert time.monotonic() - start < 1.5
    finally:
        connection.close()
        server.stop()


def test_plugin_contract_without_gui_or_real_control(monkeypatch, zmq_main, official_auth):
    monkeypatch.setattr(plugin, "make_plugin_icon", lambda *args: None)
    info = plugin.LlmMinesweeperControllerPlugin.plugin_info()
    assert info.name == "元扫雷 MCP 服务"
    assert info.required_controls == [NewGameCommand, MouseClickCommand]
    assert LlmMinesweeperControllerConfig().port == 8765
    assert "plugins.llm_minesweeper_controller.widgets" not in sys.modules
    states, queued = [], []
    owner = cast(plugin.LlmMinesweeperControllerPlugin,
                 SimpleNamespace(_server=None, _io=None, _state="stopped", _config_error="",
                                 other_info=SimpleNamespace(port=8765),
                                 name=info.name, client=SimpleNamespace(
                                     endpoint=zmq_main.endpoint),
                                 _tools=MinesweeperTools(
                                     lambda command: False, lambda *args: queued.append(args)),
                                 save_config=lambda: None,
                                 service_state_changed=SimpleNamespace(emit=states.append)))
    owner._publish_state = lambda error="": plugin.LlmMinesweeperControllerPlugin._publish_state(
        owner, error)
    owner._publish_state()
    assert states[-1]["state"] == "stopped" and states[-1]["prompt"] == ""
    try:
        plugin.LlmMinesweeperControllerPlugin.start_mcp(owner, free_port())
        assert states[-1]["state"] == "running"
        assert f"endpoint: http://127.0.0.1:{states[-1]['port']}/mcp" in states[-1]["prompt"]
        assert "Bearer" not in states[-1]["prompt"]
        assert "不安装任何包" in states[-1]["prompt"]
        assert not queued
    finally:
        plugin.LlmMinesweeperControllerPlugin.stop_mcp(owner)
    assert [state["state"] for state in states] == [
        "stopped", "starting", "running", "stopping", "stopped"]
    assert states[-1]["prompt"] == "" and owner._server is None


@pytest.mark.parametrize("value,expected", [
    (1024, 1024), (65535, 65535), (8765, 8765), (0, 8765), (1023, 8765),
    (65536, 8765), (True, 8765), ("8765", 8765), (8765.0, 8765), (None, 8765),
])
def test_config_only_accepts_valid_integer_port(value, expected):
    config = LlmMinesweeperControllerConfig()
    config.from_dict(
        {"port": value, "api_key": "must-not-survive", "model_name": "old"})
    assert config.to_dict() == {"port": expected}
    assert valid_port(value) == (type(value) is int and 1024 <= value <= 65535)


def test_widget_wiring_round_trip(qapp, qtbot, tmp_path):
    from PySide6.QtCore import QObject, Signal, Slot
    from plugins.llm_minesweeper_controller.widgets import McpControlWidget

    class Host(QObject):
        service_state_changed = Signal(object)

        def __init__(self):
            super().__init__()
            self.other_info = SimpleNamespace(port=8765)
            self._widget = None
            self.started, self.stopped = [], 0

        @Slot(int)
        def start_mcp(self, port):
            self.started.append(port)

        @Slot()
        def stop_mcp(self):
            self.stopped += 1

        def _publish_state(self, error=""):
            pass

    host = Host()
    widget = cast(McpControlWidget,
                  plugin.LlmMinesweeperControllerPlugin._create_widget(host))
    qtbot.addWidget(widget)
    assert host._widget is widget
    assert widget.port_spin.value() == 8765
    assert widget.prompt_edit.isReadOnly() and not widget.copy_button.isEnabled()
    assert not widget.prompt_edit.toPlainText()

    widget.action_button.click()
    qtbot.waitUntil(lambda: host.started == [8765])
    assert host.stopped == 0

    host.service_state_changed.emit({
        "state": "starting", "port": 8765, "endpoint": "", "prompt": "", "error": ""})
    qtbot.waitUntil(lambda: not widget.action_button.isEnabled())
    assert not widget.port_spin.isEnabled()

    host.service_state_changed.emit({
        "state": "running", "port": 8765, "error": "",
        "endpoint": "http://127.0.0.1:8765/mcp", "prompt": "endpoint + Bearer 说明"})
    qtbot.waitUntil(lambda: widget.action_button.text() == "停止MCP")
    assert "http://127.0.0.1:8765/mcp" in widget.status_label.text()
    assert widget.prompt_edit.toPlainText() == "endpoint + Bearer 说明"
    assert widget.copy_button.isEnabled()
    assert not widget.port_spin.isEnabled()

    widget.action_button.click()
    qtbot.waitUntil(lambda: host.stopped == 1)

    host.service_state_changed.emit({
        "state": "error", "port": 8765, "endpoint": "", "prompt": "", "error": "端口占用"})
    qtbot.waitUntil(lambda: "端口占用" in widget.status_label.text())
    assert widget.action_button.isEnabled() and widget.port_spin.isEnabled()
    assert not widget.copy_button.isEnabled() and not widget.prompt_edit.toPlainText()


def test_config_cleanup_whitelist_and_no_secret_migration(tmp_path):
    current = tmp_path / CONFIG_IDENTITIES[0]
    for name in CONFIG_IDENTITIES:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "config.json").write_text(json.dumps(
            {"port": 9000, "api_key": "old-secret"}), encoding="utf-8")
    nested = current / CONFIG_IDENTITIES[1]
    nested.mkdir()
    (nested /
     "config.json").write_text('{"api_key":"nested-secret"}', encoding="utf-8")
    unrelated = current / "another-plugin"
    unrelated.mkdir()
    untouched = '{"api_key":"another-plugin-secret","other":42}'
    (unrelated / "config.json").write_text(untouched, encoding="utf-8")
    (tmp_path / "config.json").write_text(untouched, encoding="utf-8")
    sanitize_legacy_configs(current)
    for name in CONFIG_IDENTITIES:
        assert json.loads(
            (tmp_path / name / "config.json").read_text(encoding="utf-8")) == {"port": 9000}
    assert json.loads(
        (nested / "config.json").read_text(encoding="utf-8")) == {"port": 8765}
    assert (unrelated / "config.json").read_text(encoding="utf-8") == untouched
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == untouched
    assert not list(tmp_path.rglob(".mcp-config-*"))


@pytest.mark.parametrize("content", ["not-json", "[]", '{"port":true,"api_key":"old"}'])
def test_config_cleanup_invalid_json_defaults(tmp_path, content):
    (tmp_path / "config.json").write_text(content, encoding="utf-8")
    sanitize_legacy_configs(tmp_path)
    assert json.loads(
        (tmp_path / "config.json").read_text(encoding="utf-8")) == {"port": 8765}


def test_plugin_stop_preserves_official_event_cache(sdk):
    set_board(sdk.registry)
    owner = cast(plugin.LlmMinesweeperControllerPlugin,
                 SimpleNamespace(_server=None, _io=None, _tools=sdk.registry,
                                 _publish_state=lambda *args: None))
    plugin.LlmMinesweeperControllerPlugin.stop_mcp(owner)
    assert owner._state == "stopped"
    assert sdk.registry.execute_function("get_board_state", {})["success"]


def test_http_control_waits_for_fake_main_confirmation(http_service):
    server, sdk, _, _ = http_service
    session = initialize(server)
    sdk.response = False
    message = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": "click_cell", "arguments": {"row": 0, "col": 0}}}
    assert rpc_body(http_request(server, message, extra=session))[
        "result"]["isError"]
    sdk.response = True
    message["id"] = 3
    result = rpc_body(http_request(server, message, extra=session))["result"]
    assert not result["isError"] and result["structuredContent"]["outcome"] == "confirmed"
    assert len(sdk.calls) == 2


def test_http_connection_bound(monkeypatch):
    admitted = threading.Event()
    original = mcp_server._HttpServer.process_request

    def record(server, request, address):
        original(server, request, address)
        with server.active_lock:
            if len(server.active) == mcp_server.MAX_CONNECTIONS:
                admitted.set()

    monkeypatch.setattr(mcp_server._HttpServer, "process_request", record)
    server = McpServer(free_port(), TOOLS, RequestBridge(lambda call: None))
    server.start()
    connections = []
    try:
        for index in range(mcp_server.MAX_CONNECTIONS):
            connection = socket.create_connection(
                ("127.0.0.1", server.port), timeout=1)
            connection.sendall(b"P")
            connections.append(connection)
        assert admitted.wait(1)
        with socket.create_connection(("127.0.0.1", server.port), timeout=1) as overflow:
            try:
                assert overflow.recv(1) == b""
            except ConnectionResetError:
                pass
    finally:
        server.stop()
        for connection in connections:
            connection.close()
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", server.port))
