"""第二轮定点补测：lib_zmq_plugins/server/zmq_server.py

全程伪造：FakeSocket / FakePoller / FakeContext / InlineThread / FakeEvent，
不创建真实 ZMQ Context、socket、Poller，不绑定端口，不启动 OS 线程。
"""
from __future__ import annotations

import errno
from types import SimpleNamespace

import pytest
import zmq as real_zmq

from lib_zmq_plugins.server import zmq_server as server_module
from lib_zmq_plugins.server.zmq_server import (
    ZMQServer, _derive_endpoints, _extract_host_prefix,
)
from lib_zmq_plugins.shared.base import (
    CommandResponse, SyncCommand,
)
from tests.test_cov_zmq2_common import (
    CovCommand, CovEvent, CovQuery, CovResult, FakeContext, FakeEvent,
    FakePoller, FakeSocket, InlineThread, RecLog, TagAsType, encode, fake_threading,
    fake_time, fake_zmq, tagged,
)


# ── 局部 fixture / helper ──

@pytest.fixture
def log() -> RecLog:
    return RecLog()


def _new_server(log: RecLog, endpoint: str = "tcp://127.0.0.1:5555", **kwargs) -> ZMQServer:
    server = ZMQServer(endpoint, log_handler=log, **kwargs)
    server.register_event_types(CovEvent)
    server.register_command_types(CovCommand)
    server.register_query_types(CovQuery)
    server.register_query_result_types(CovResult)
    return server


def _with_router(server: ZMQServer) -> FakeSocket:
    router = FakeSocket("router")
    server._router_socket = router
    return router


def _drive_poll(server: ZMQServer, messages: list, *, extra_events=()) -> FakeSocket:
    """让 _poll_loop 消费一轮消息后，由第二次 poll 抛 ZMQError 退出循环。"""
    router = server._router_socket
    assert isinstance(router, FakeSocket)
    router.recv_messages = list(messages)
    events = [(router, real_zmq.POLLIN)] * len(messages) + list(extra_events)
    server._poller = FakePoller(
        results=[events, real_zmq.ZMQError(errno.EIO)], default=[])
    server._stopped = FakeEvent(flag=False)
    server._poll_loop()
    return router


def _sent_payloads(socket: FakeSocket) -> list:
    return [args[2] for args in socket.log if args[1] == "send_multipart"]


class _TypeTagCommand:
    """tag 为 type 且带 request_id 的伪命令，供 _dispatch 的 type-tag 分支使用。"""
    request_id = ""
    __struct_config__ = SimpleNamespace(tag=ValueError)


# ── 端点派生 / host 前缀 ──

def test_derive_endpoints_ipc_scheme(log):
    assert _derive_endpoints("ipc:///tmp/ms") == (
        "ipc:///tmp/ms_pub", "ipc:///tmp/ms_ctrl")


def test_derive_endpoints_tcp_default_and_explicit_port(log):
    assert _derive_endpoints("tcp://127.0.0.1") == (
        "tcp://127.0.0.1:5556", "tcp://127.0.0.1:5557")
    assert _derive_endpoints("tcp://10.0.0.2:7000") == (
        "tcp://10.0.0.2:7001", "tcp://10.0.0.2:7002")


def test_derive_endpoints_rejects_unsupported_scheme(log):
    with pytest.raises(ValueError, match="Unsupported scheme: udp"):
        _derive_endpoints("udp://127.0.0.1:5555")


def test_extract_host_prefix_ipv4_and_ipv6_and_ipc(log):
    assert _extract_host_prefix("tcp://127.0.0.1:5555") == "tcp://127.0.0.1"
    assert _extract_host_prefix("tcp://127.0.0.1") == "tcp://127.0.0.1"
    # IPv6 字面量需补回方括号
    assert _extract_host_prefix("tcp://[::1]:5555") == "tcp://[::1]"
    assert _extract_host_prefix("ipc:///tmp/foo") == "ipc:///tmp/foo"


def test_extract_host_prefix_rejects_unsupported_scheme(log):
    with pytest.raises(ValueError, match="Unsupported scheme for random port: udp"):
        _extract_host_prefix("udp://127.0.0.1:5555")


# ── handler 注册 ──

def test_register_handler_with_type_tag_uses_class_name(log):
    server = _new_server(log)
    handler = lambda cmd: None  # noqa: E731
    server.register_handler(TagAsType, handler)
    assert server._handlers == {"ValueError": handler}

    # 注册结果供后续 dispatch 使用（普通字符串 tag 路径保持可用）
    server.register_handler(CovCommand, handler)
    assert "covz.cmd" in server._handlers


# ── _bind_random_ports ──

def test_bind_random_ports_requires_initialized_sockets(log):
    # endpoint 为 IPv6，顺带触发 host 前缀的方括号分支
    server = _new_server(log, endpoint="tcp://[::1]:5555")
    with pytest.raises(RuntimeError, match="Sockets are not initialized"):
        server._bind_random_ports()


# ── start / stop ──

def test_start_fixed_bind_and_publish_roundtrip(monkeypatch, log):
    pub, router = FakeSocket("pub"), FakeSocket("router")
    ctx = FakeContext(socket_map={real_zmq.PUB: pub, real_zmq.ROUTER: router})
    poller = FakePoller(results=[real_zmq.ZMQError(errno.EIO)])
    monkeypatch.setattr(server_module, "zmq", fake_zmq(
        real_zmq, context=lambda: ctx, poller=lambda: poller))
    monkeypatch.setattr(server_module, "threading", fake_threading(InlineThread))
    monkeypatch.setattr(server_module, "time", fake_time(wall=lambda: 111.0))

    server = _new_server(log)
    server.start()

    assert pub.bound == ["tcp://127.0.0.1:5556"]
    assert router.bound == ["tcp://127.0.0.1:5557"]
    # ROUTER 心跳选项被设置 3 次（log 元组为 (name, op, opt, value)）
    assert [args[3] for args in router.log if args[1] == "setsockopt"] == [
        5000, 5000, 10000]
    assert [args[2] for args in router.log if args[1] == "setsockopt"] == [
        real_zmq.HEARTBEAT_IVL, real_zmq.HEARTBEAT_TIMEOUT,
        real_zmq.HEARTBEAT_TTL]
    assert poller.registered == [(router, real_zmq.POLLIN)]
    assert poller.poll_calls == [100]
    assert "Server started: endpoint=%s, pub=%s, ctrl=%s" in log.messages()
    assert server.pub_endpoint == "tcp://127.0.0.1:5556"
    assert server.ctrl_endpoint == "tcp://127.0.0.1:5557"
    assert server.endpoint == "tcp://127.0.0.1:5555"

    event = CovEvent(value=7)
    server.publish(CovEvent, event)
    assert event.timestamp == 111.0
    parts = pub.log[-1][2]
    assert parts[0] == b"covz.evt"
    assert server._serializer.decode_event(parts[1]).value == 7

    server.stop()
    assert pub.closed and router.closed
    assert ctx.terminated is True
    assert server._pub_socket is None and server._router_socket is None
    assert server._ctx is None and server._poller is None


def test_start_random_ports_uses_two_independent_system_ports(monkeypatch, log):
    pub, router = FakeSocket("pub"), FakeSocket("router")
    pub.random_ports = [30001]
    router.random_ports = [30002]
    ctx = FakeContext(socket_map={real_zmq.PUB: pub, real_zmq.ROUTER: router})
    poller = FakePoller(results=[real_zmq.ZMQError(errno.EIO)])
    monkeypatch.setattr(server_module, "zmq", fake_zmq(
        real_zmq, context=lambda: ctx, poller=lambda: poller))
    monkeypatch.setattr(server_module, "threading", fake_threading(InlineThread))

    server = _new_server(log, endpoint="tcp://127.0.0.1",
                         bind_to_random_port=True,
                         random_port_min=21000, random_port_max=22000)
    server.start()

    assert pub.bound == [] and router.bound == []
    bind_calls = [a for a in pub.log if a[1] == "bind_to_random_port"]
    assert bind_calls == [("pub", "bind_to_random_port", "tcp://127.0.0.1",
                           21000, 22000, 100)]
    assert [a for a in router.log if a[1] == "bind_to_random_port"][0][2] == "tcp://127.0.0.1"
    assert server.pub_endpoint == "tcp://127.0.0.1:30001"
    assert server.ctrl_endpoint == "tcp://127.0.0.1:30002"


def test_start_raises_when_socket_creation_returns_none(monkeypatch, log):
    router = FakeSocket("router")
    ctx = FakeContext(socket_map={real_zmq.PUB: None, real_zmq.ROUTER: router})
    monkeypatch.setattr(server_module, "zmq", fake_zmq(
        real_zmq, context=lambda: ctx, poller=lambda: FakePoller()))
    monkeypatch.setattr(server_module, "threading", fake_threading(InlineThread))

    server = _new_server(log)
    with pytest.raises(RuntimeError, match="Failed to create socket"):
        server.start()
    # 抛错前只创建了 socket，未绑定、未启动线程
    assert ctx.created[0][1] is None
    assert not router.bound


def test_stop_joins_alive_thread_and_clears_resources(monkeypatch, log):
    """stop() 对仍存活的 I/O 线程执行 join，随后关闭 socket / term context。"""
    from tests.test_cov_zmq2_common import StubThread
    pub, router = FakeSocket("pub"), FakeSocket("router")
    ctx = FakeContext(socket_map={real_zmq.PUB: pub, real_zmq.ROUTER: router})
    server = _new_server(log)
    server._ctx = ctx
    server._pub_socket = pub
    server._router_socket = router
    server._poller = FakePoller()
    thread = StubThread(alive=True)
    server._thread = thread
    server._stopped = FakeEvent(flag=False)

    server.stop()

    assert thread.joined == [3.0]
    assert server._stopped.is_set() is True
    assert pub.closed and router.closed
    assert ctx.terminated is True
    assert server._pub_socket is None and server._router_socket is None
    assert server._ctx is None and server._poller is None
    assert server._thread is None


# ── publish ──

def test_publish_before_start_raises(log):
    server = _new_server(log)
    with pytest.raises(RuntimeError, match="Server is not started"):
        server.publish(CovEvent, CovEvent(value=1))


# ── _poll_loop ──

def test_poll_loop_transport_zmq_error_breaks(log):
    server = _new_server(log)
    _with_router(server)
    router = _drive_poll(server, [])
    assert server._poller.poll_calls == [100, 100]
    assert not _sent_payloads(router)


def test_poll_loop_recv_again_and_short_frame_are_skipped(log):
    server = _new_server(log)
    router = _with_router(server)
    router = _drive_poll(server, [real_zmq.Again(), [b"cid"]])
    assert sum(1 for a in router.log if a[1] == "recv_multipart") == 2
    assert not _sent_payloads(router)
    assert "Failed to decode command" not in " ".join(log.messages())


def test_poll_loop_invalid_query_payload_logs_and_continues(log):
    server = _new_server(log)
    router = _with_router(server)
    server.register_query_handler(
        CovQuery, lambda q: CovResult(request_id=q.request_id, value=99))
    invalid = tagged("covz.query", value="not-an-int")
    valid = encode(CovQuery(request_id="q-later", value=3))
    _drive_poll(server, [[b"cid", invalid], [b"cid", valid]])

    assert "Failed to decode query" in log.messages()
    # continue 之后仍能处理同一轮里的后续消息
    sent = _sent_payloads(router)
    assert len(sent) == 1
    assert sent[0][0] == b"cid" and sent[0][1] == b""
    assert server._serializer.decode_query_result(sent[0][2]).value == 99


def test_poll_loop_invalid_command_payload_logs_and_continues(log):
    server = _new_server(log)
    router = _with_router(server)
    server.register_handler(
        CovCommand, lambda c: CommandResponse(request_id=c.request_id, success=True))
    invalid = tagged("covz.cmd", value="not-an-int")
    valid = encode(CovCommand(request_id="r-later", value=3))
    _drive_poll(server, [[b"cid", invalid], [b"cid", valid]])

    assert "Failed to decode command" in log.messages()
    sent = _sent_payloads(router)
    assert len(sent) == 1
    assert sent[0][0] == b"cid" and sent[0][1] == b""
    assert server._serializer.decode_response(sent[0][2]).request_id == "r-later"


def test_poll_loop_dispatches_query_command_and_sync(monkeypatch, log):
    server = _new_server(log)
    router = _with_router(server)
    server.register_handler(
        CovCommand, lambda c: CommandResponse(request_id=c.request_id, success=True))
    server.register_query_handler(
        CovQuery, lambda q: CovResult(request_id=q.request_id, value=5))
    server.register_snapshot_provider(CovEvent, lambda: CovEvent(value=42))

    msgs = [
        [b"cid", encode(CovQuery(request_id="q1"))],
        [b"cid", encode(CovCommand(request_id="r1"))],
        [b"cid", encode(SyncCommand(request_id="s1", topic="covz.evt"))],
    ]
    _drive_poll(server, msgs)

    sent = _sent_payloads(router)
    assert len(sent) == 3
    assert server._serializer.decode_query_result(sent[0][2]).value == 5
    assert server._serializer.decode_response(sent[1][2]).request_id == "r1"
    sync_resp = server._serializer.decode_response(sent[2][2])
    assert sync_resp.success is True
    assert server._serializer.decode_event(sync_resp.data).value == 42


def test_poll_loop_ignores_events_from_other_socket(log):
    server = _new_server(log)
    router = _with_router(server)
    other = FakeSocket("other")
    other.recv_messages = [[b"cid", encode(CovCommand(request_id="ignored"))]]
    _drive_poll(server, [], extra_events=[(other, real_zmq.POLLIN)])
    assert not any(a[1] == "recv_multipart" for a in router.log)
    assert not _sent_payloads(router)


# ── _dispatch ──

def test_dispatch_type_tag_command_and_missing_handler(log):
    server = _new_server(log)
    router = _with_router(server)
    server._dispatch(b"cid", _TypeTagCommand())
    assert any("No handler for command" in str(m) for m in log.messages())
    assert not _sent_payloads(router)


def test_dispatch_handler_exception_sends_failure_response(log):
    server = _new_server(log)
    router = _with_router(server)

    def boom(cmd):
        raise RuntimeError("handler broke")

    server.register_handler(CovCommand, boom)
    server._dispatch(b"cid", CovCommand(request_id="r-err", value=1))

    assert any("Handler error for" in m for m in log.messages())
    sent = _sent_payloads(router)
    assert len(sent) == 1
    resp = server._serializer.decode_response(sent[0][2])
    assert resp.request_id == "r-err"
    assert resp.success is False
    assert resp.error == "handler broke"


def test_dispatch_handler_exception_without_request_id_sends_nothing(log):
    server = _new_server(log)
    router = _with_router(server)

    def boom(cmd):
        raise ValueError("no id")

    server.register_handler(CovCommand, boom)
    server._dispatch(b"cid", CovCommand(request_id="", value=1))

    assert any("Handler error for" in m for m in log.messages())
    assert not _sent_payloads(router)


def test_dispatch_sync_routes_to_snapshot_provider_and_missing_provider(log):
    server = _new_server(log)
    router = _with_router(server)
    server.register_snapshot_provider(CovEvent, lambda: CovEvent(value=17))

    server._dispatch(b"cid", SyncCommand(request_id="s-ok", topic="covz.evt"))
    ok = server._serializer.decode_response(_sent_payloads(router)[-1][2])
    assert ok.success is True
    assert server._serializer.decode_event(ok.data).value == 17

    server._dispatch(b"cid", SyncCommand(request_id="s-miss", topic="nope"))
    miss = server._serializer.decode_response(_sent_payloads(router)[-1][2])
    assert miss.success is False
    assert miss.error == "No snapshot provider for topic: nope"


# ── _dispatch_query / _send_query_result ──

def test_dispatch_query_handler_exception_returns_failure_result(log):
    server = _new_server(log)
    router = _with_router(server)

    def boom(query):
        raise RuntimeError("query broke")

    server.register_query_handler(CovQuery, boom)
    server._dispatch_query(b"cid", CovQuery(request_id="q-err"))

    assert any("Query handler error for" in m for m in log.messages())
    sent = _sent_payloads(router)
    assert len(sent) == 1
    result = server._serializer.decode_query_result(sent[0][2])
    assert result.success is False
    assert result.error == "query broke"
    assert result.request_id == "q-err"


def test_dispatch_query_without_handler_returns_explanatory_failure(log):
    server = _new_server(log)
    router = _with_router(server)
    server._dispatch_query(b"cid", CovQuery(request_id="q-none"))
    result = server._serializer.decode_query_result(_sent_payloads(router)[0][2])
    assert result.success is False
    assert result.error == "No handler for query: covz.query"


def test_dispatch_query_without_request_id_does_not_reply(log):
    server = _new_server(log)
    router = _with_router(server)
    server.register_query_handler(
        CovQuery, lambda q: CovResult(request_id=q.request_id))
    server._dispatch_query(b"cid", CovQuery(request_id=""))
    assert not _sent_payloads(router)


def test_send_query_result_no_socket_is_noop_and_zmq_error_is_logged(log):
    server = _new_server(log)
    result = CovResult(request_id="q1")

    server._router_socket = None
    server._send_query_result(b"cid", result)  # 早退分支
    assert "Failed to send query result" not in log.messages()

    router = _with_router(server)
    router.send_multipart_error = real_zmq.ZMQError(errno.EIO)
    server._send_query_result(b"cid", result)
    assert "Failed to send query result" in log.messages()


# ── _handle_sync / _send_to_client ──

def test_handle_sync_provider_exception_returns_failure_response(log):
    server = _new_server(log)
    router = _with_router(server)

    def boom():
        raise RuntimeError("snapshot unavailable")

    server.register_snapshot_provider(CovEvent, boom)
    server._handle_sync(b"cid", SyncCommand(request_id="s-err", topic="covz.evt"))

    assert any("Snapshot provider error" in m for m in log.messages())
    resp = server._serializer.decode_response(_sent_payloads(router)[0][2])
    assert resp.request_id == "s-err"
    assert resp.success is False
    assert resp.error == "snapshot unavailable"


def test_send_to_client_no_socket_is_noop_and_zmq_error_is_logged(log):
    server = _new_server(log)
    resp = CommandResponse(request_id="r1", success=True)

    server._router_socket = None
    server._send_to_client(b"cid", resp)
    assert "Failed to send response to client" not in log.messages()

    router = _with_router(server)
    router.send_multipart_error = real_zmq.ZMQError(errno.EIO)
    server._send_to_client(b"cid", resp)
    assert "Failed to send response to client" in log.messages()
