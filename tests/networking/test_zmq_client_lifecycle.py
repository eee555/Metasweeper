"""真实 ZMQ 往返及受控故障：线程归属、期限、断线和恢复。"""
from __future__ import annotations

import errno
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import zmq

from lib_zmq_plugins.client import zmq_client as module
from lib_zmq_plugins.client.zmq_client import ZMQClient
from lib_zmq_plugins.server.zmq_server import ZMQServer
from lib_zmq_plugins.shared.base import (
    BaseCommand, BaseEvent, BaseQuery, BaseQueryResult, CommandResponse,
)


class Ping(BaseCommand, tag="lifecycle.ping"):
    pass


class Status(BaseQuery, tag="lifecycle.status"):
    pass


class State(BaseEvent, tag="lifecycle.state"):
    value: int = 0


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    tick = threading.Event()
    while time.monotonic() < deadline:
        if predicate():
            return
        tick.wait(0.01)
    assert predicate(), "condition did not become true"


def make_server(endpoint="tcp://127.0.0.1", *, random=True, snapshots=None):
    server = ZMQServer(endpoint, bind_to_random_port=random)
    server.register_event_types(State)
    server.register_command_types(Ping)
    server.register_query_types(Status)
    server.register_handler(Ping, lambda c: CommandResponse(
        request_id=c.request_id, success=True))
    server.register_query_handler(Status, lambda q: BaseQueryResult(
        request_id=q.request_id))
    if snapshots is not None:
        def snapshot():
            snapshots.append(True)
            return State(value=len(snapshots))
        server.register_snapshot_provider(State, snapshot)
    server.start()
    return server


def make_client(server, **kwargs):
    client = ZMQClient(server.endpoint, pub_endpoint=server.pub_endpoint,
                       ctrl_endpoint=server.ctrl_endpoint, **kwargs)
    client.register_command_types(Ping)
    client.register_query_types(Status)
    client.register_event_types(State)
    return client


def test_socket_operations_belong_to_io_thread(monkeypatch):
    operations = []

    def record(name):
        operations.append((name, threading.get_ident()))

    class TrackedSocket(zmq.Socket):
        def setsockopt(self, *args, **kwargs):
            record("setsockopt")
            return super().setsockopt(*args, **kwargs)

        def connect(self, *args, **kwargs):
            record("connect")
            return super().connect(*args, **kwargs)

        def send(self, *args, **kwargs):
            record("send")
            return super().send(*args, **kwargs)

        def recv_multipart(self, *args, **kwargs):
            record("recv")
            return super().recv_multipart(*args, **kwargs)

        def close(self, *args, **kwargs):
            record("close")
            return super().close(*args, **kwargs)

    class TrackedContext(zmq.Context):
        def socket(self, socket_type, **kwargs):
            record("socket")
            return super().socket(socket_type, socket_class=TrackedSocket, **kwargs)

        def term(self):
            record("term")
            return super().term()

    class TrackedPoller(zmq.Poller):
        def poll(self, *args, **kwargs):
            record("poll")
            return super().poll(*args, **kwargs)

    # 仅替换客户端模块的 zmq 引用，不改变服务端或已加载模块。
    monkeypatch.setattr(module, "zmq", SimpleNamespace(
        **{**vars(zmq), "Context": TrackedContext, "Poller": TrackedPoller}))
    server = make_server()
    client = make_client(server)
    client.connect()
    worker = client._thread
    try:
        received = threading.Event()
        server.register_snapshot_provider(State, lambda: State(value=42))
        client.subscribe(State, lambda event: received.set())
        assert received.wait(3)
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(client.request, Ping()) for _ in range(12)]
            futures += [pool.submit(client.query, Status()) for _ in range(12)]
            assert all(f.result(3).success for f in futures)
        client.unsubscribe(State)
        wait_until(lambda: not client._active_topics)
    finally:
        client.disconnect()
        server.stop()
    assert worker is not None and not worker.is_alive()
    assert {ident for _, ident in operations} == {worker.ident}
    assert {name for name, _ in operations} >= {
        "socket", "setsockopt", "connect", "send", "recv", "poll", "close", "term"}


def test_real_disconnect_reconnect_resynchronizes_without_replaying_commands():
    snapshots, connection_events = [], []
    server = make_server(snapshots=snapshots)
    # 恢复时绑定同一对随机获得的端口。
    endpoints = (server.pub_endpoint, server.ctrl_endpoint)
    client = make_client(server,
                         on_connected=lambda: connection_events.append("up"),
                         on_disconnected=lambda: connection_events.append("down"))
    client._PROBE_INTERVAL = 0.03
    client._CONNECTION_TIMEOUT = 0.3
    received = []
    client.subscribe(State, received.append)
    client.connect()
    try:
        wait_until(lambda: len(received) == 1)
        server.stop()
        wait_until(lambda: connection_events == ["up", "down"])
        assert not client.is_connected and client.reconnect_count == 1
        with pytest.raises(TimeoutError):
            client.request(Ping(), timeout=0.04)
        # 固定模式基准仅用于构造，显式设置恢复端点以保留随机端口对。
        server = ZMQServer("tcp://127.0.0.1")
        server._pub_endpoint, server._ctrl_endpoint = endpoints
        server.register_event_types(State)
        server.register_command_types(Ping)
        executed = []
        server.register_handler(Ping, lambda c: executed.append(c))
        server.register_snapshot_provider(State, lambda: State(value=99))
        server.start()
        wait_until(lambda: connection_events == ["up", "down", "up"])
        wait_until(lambda: any(event.value == 99 for event in received))
        assert not executed
        assert not client._pending_requests
    finally:
        client.disconnect()
        server.stop()


def test_socket_recreation_failure_retries_and_recovers(monkeypatch):
    server = make_server()
    client = make_client(server)
    original_create = client._create_sockets
    original_send = client._send_queued
    attempts = []
    trigger = threading.Event()

    def create():
        attempts.append(True)
        if len(attempts) in (2, 3):
            raise zmq.ZMQError(errno.EMFILE)
        original_create()

    def send():
        if trigger.is_set():
            trigger.clear()
            raise zmq.ZMQError(errno.EIO)
        original_send()

    monkeypatch.setattr(client, "_create_sockets", create)
    monkeypatch.setattr(client, "_send_queued", send)
    client.connect()
    try:
        assert client.query(Status()).success
        trigger.set()
        wait_until(lambda: len(attempts) >= 4)
        assert client.query(Status()).success
        assert client._thread is not None and client._thread.is_alive()
    finally:
        client.disconnect()
        server.stop()


@pytest.mark.parametrize("method,message,pending", [
    ("request", Ping, "_pending_requests"),
    ("query", Status, "_pending_queries"),
])
def test_timeout_cleans_pending_and_never_sends_expired_work(method, message, pending):
    server = make_server()
    client = make_client(server)
    client.connect()
    try:
        wait_until(lambda: client.is_connected)
        with pytest.raises(TimeoutError):
            getattr(client, method)(message(), timeout=0)
        assert not getattr(client, pending)
        assert getattr(client, method)(message(), timeout=2).success
    finally:
        client.disconnect()
        server.stop()


def test_disconnect_immediately_finishes_waiters_and_allows_reconnect():
    server = make_server()
    server.register_handler(Ping, lambda c: None)  # 保持请求无响应。
    client = make_client(server)
    client.connect()
    worker = client._thread
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(client.request, Ping(), 30)
            wait_until(lambda: bool(client._pending_requests))
            client.disconnect()
            with pytest.raises(ConnectionError):
                waiting.result(timeout=1)
        assert not client._pending_requests and not client._pending_queries
        assert worker is not None and not worker.is_alive()
        client.connect()
        assert client.query(Status(), timeout=2).success
    finally:
        client.disconnect()
        server.stop()


def test_saturated_transport_keeps_deadline_and_bounded_queue(monkeypatch):
    """强制所有发送返回 EAGAIN，模拟 HWM；请求及 GUI 异步入口必须有界。"""
    server = make_server()
    client = make_client(server)
    client._QUEUE_LIMIT = 3
    from queue import Queue
    client._outgoing = Queue(3)
    original_create = client._create_sockets

    class SaturatedSocket:
        def __init__(self, socket):
            self.socket = socket

        def send(self, payload, flags=0):
            assert flags & zmq.NOBLOCK
            raise zmq.Again()

        def close(self, **kwargs):
            self.socket.close(**kwargs)

    def create():
        original_create()
        client._dealer_socket = SaturatedSocket(client._dealer_socket)

    monkeypatch.setattr(client, "_create_sockets", create)
    client.connect()
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            client.query(Status(), timeout=0.05)
        assert time.monotonic() - started < 0.5
        assert not client._pending_queries
        started = time.monotonic()
        for _ in range(4):
            try:
                client.send_command(Ping())
            except BufferError:
                break
        with pytest.raises(BufferError):
            # I/O 最多保留一条待重试消息；其余队列不允许无限增长。
            for _ in range(5):
                client.send_command(Ping())
        assert time.monotonic() - started < 0.5
        assert client._outgoing.qsize() <= 3
    finally:
        client.disconnect()
        server.stop()


def test_encoding_and_enqueue_failure_leave_no_pending(monkeypatch):
    server = make_server()
    client = make_client(server)
    client.connect()
    try:
        def fail(*args):
            raise ValueError("cannot encode")
        with monkeypatch.context() as patch:
            patch.setattr(client._serializer, "encode_command", fail)
            with pytest.raises(ValueError, match="cannot encode"):
                client.request(Ping())
        assert not client._pending_requests
        with monkeypatch.context() as patch:
            patch.setattr(client, "_enqueue", fail)
            with pytest.raises(ValueError, match="cannot encode"):
                client.query(Status())
        assert not client._pending_queries
    finally:
        client.disconnect()
        server.stop()


def test_snapshot_records_expire_without_response():
    server = make_server()
    # 收到同步请求后不响应，用于验证快照映射的到期清理。
    server._handle_sync = lambda identity, command: None
    client = make_client(server)
    client._SEND_TIMEOUT = 0.05
    client.connect()
    try:
        # 该测试服务端故意不回应探测，手动进入已确认状态以触发订阅同步。
        client._is_connected = True
        client.subscribe(State, lambda event: None)
        wait_until(lambda: bool(client._sync_topics))
        wait_until(lambda: not client._sync_topics)
        assert not client._sync_deadlines
    finally:
        client.disconnect()
        server.stop()


def test_existing_topic_new_callback_and_fast_resubscribe_get_snapshot():
    server = make_server(snapshots=[])
    client = make_client(server)
    first, second, third = [], [], []
    client.subscribe(State, first.append)
    client.connect()
    try:
        wait_until(lambda: len(first) == 1)
        client.subscribe(State, second.append)
        wait_until(lambda: len(second) == 1)
        assert second[0].value == 2
        # 把更新固定在同一轮订阅协调之前，集合仍相同但版本发生变化。
        with client._subscribers_lock:
            client._subscribers.pop("lifecycle.state")
            client._subscription_versions.pop("lifecycle.state")
            client._subscribers["lifecycle.state"] = [third.append]
            client._subscription_revision += 1
            client._subscription_versions["lifecycle.state"] = client._subscription_revision
        wait_until(lambda: len(third) == 1)
        assert third[0].value == 3
    finally:
        client.disconnect()
        server.stop()


def test_disconnect_cannot_cancel_then_send_already_dequeued_work():
    client = ZMQClient("tcp://127.0.0.1")
    checked, release, cancelling = threading.Event(), threading.Event(), threading.Event()
    future = Future()
    request_id = "cancel-race"
    order = []
    errors = []
    client._accepting = True
    client._pending_requests[request_id] = future
    client._enqueue(module._Outgoing(b"payload", time.monotonic() + 5,
                                     request_id, future))

    class GateLock:
        def __init__(self):
            self.lock = threading.Lock()

        def __enter__(self):
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()
            if threading.current_thread().name == "race-sender":
                checked.set()
                assert release.wait(3)

    class Socket:
        def send(self, payload, flags):
            assert not client._stopped.is_set()
            assert not future.done()
            order.append("send")

    client._pending_lock = GateLock()
    client._dealer_socket = Socket()

    def send():
        try:
            client._send_queued()
        except BaseException as exc:
            errors.append(exc)

    def cancel():
        cancelling.set()
        client.disconnect()
        order.append("cancel")

    sender = threading.Thread(target=send, name="race-sender", daemon=True)
    stopper = threading.Thread(target=cancel, daemon=True)
    sender.start()
    try:
        assert checked.wait(3)
        stopper.start()
        assert cancelling.wait(3)
    finally:
        release.set()
        sender.join(3)
        if stopper.ident is not None:
            stopper.join(3)
    assert not sender.is_alive() and not stopper.is_alive()
    assert not errors
    assert order == ["send", "cancel"]
    assert isinstance(future.exception(), ConnectionError)


def test_partial_socket_creation_failure_closes_and_retries(monkeypatch):
    server = make_server()
    client = make_client(server)
    original_create = client._create_sockets
    original_send = client._send_queued
    trigger = threading.Event()
    allocated = []
    attempts = []

    def create():
        attempts.append(True)
        if len(attempts) == 2:
            client._sub_socket = client._ctx.socket(zmq.SUB)
            allocated.append(client._sub_socket)
            raise zmq.ZMQError(errno.EMFILE)
        original_create()

    def send():
        if trigger.is_set():
            trigger.clear()
            raise zmq.ZMQError(errno.EIO)
        original_send()

    monkeypatch.setattr(client, "_create_sockets", create)
    monkeypatch.setattr(client, "_send_queued", send)
    client.connect()
    try:
        assert client.query(Status()).success
        trigger.set()
        wait_until(lambda: len(attempts) >= 3)
        assert client.query(Status()).success
        assert allocated[0].closed
    finally:
        client.disconnect()
        server.stop()


def test_io_callback_rejects_sync_wait_and_can_disconnect_itself():
    server = make_server()
    errors, finished = [], threading.Event()
    client = make_client(server)

    def callback():
        try:
            client.query(Status())
        except RuntimeError as exc:
            errors.append(str(exc))
        client.disconnect()
        finished.set()

    client.on_connected = callback
    client.connect()
    try:
        assert finished.wait(3)
        client.disconnect()
        assert len(errors) == 1 and "I/O thread" in errors[0]
        assert client._ctx is None and client._dealer_socket is None
    finally:
        client.disconnect()
        server.stop()