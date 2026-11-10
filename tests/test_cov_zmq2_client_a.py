"""第二轮定点补测（client A）：端点派生、连接生命周期、socket 管理、
订阅、入队/等待、发送队列、轮询循环。

全程伪造：FakeSocket / FakePoller / FakeContext / InlineThread / StubThread /
FakeEvent / FakeFuture。不创建真实 ZMQ 对象、不绑定端口、不启动 OS 线程。
"""
from __future__ import annotations

import errno
import threading as _real_threading
import time as _real_time
from concurrent.futures import TimeoutError as FutureTimeoutError
from types import SimpleNamespace

import pytest
import zmq as real_zmq

from lib_zmq_plugins.client import zmq_client as client_module
from lib_zmq_plugins.client.zmq_client import (
    ZMQClient, _Outgoing, _derive_endpoints,
)
from lib_zmq_plugins.shared.base import (
    BaseQueryResult, CommandResponse, SyncCommand,
)
from tests.test_cov_zmq2_common import (
    CovCommand, CovEvent, CovQuery, CovResult, FakeContext, FakeEvent,
    FakeFuture, FakePoller, FakeSocket, InlineThread, RecLog, StubThread,
    encode, fake_threading, fake_time, fake_uuid, fake_zmq, tagged,
)


# ── 局部 fixture / helper ──

@pytest.fixture
def log() -> RecLog:
    return RecLog()


def _new_client(log: RecLog, endpoint: str = "tcp://127.0.0.1:5555", **kwargs) -> ZMQClient:
    client = ZMQClient(endpoint, log_handler=log, **kwargs)
    client.register_event_types(CovEvent)
    client.register_command_types(CovCommand)
    client.register_query_types(CovQuery, result_types=(CovResult,))
    return client


def _patch_zmq(monkeypatch, *, context=None, poller=None) -> None:
    monkeypatch.setattr(client_module, "zmq", fake_zmq(
        real_zmq, context=context, poller=poller))


def _patch_threading(monkeypatch, thread_cls=None) -> None:
    monkeypatch.setattr(
        client_module, "threading",
        fake_threading(thread_cls or InlineThread))


def _patch_time(monkeypatch, *, monotonic=None, wall=None) -> None:
    monkeypatch.setattr(client_module, "time", fake_time(
        monotonic=monotonic, wall=wall))


def _patch_uuid(monkeypatch, value: str = "rid") -> None:
    monkeypatch.setattr(client_module, "uuid", fake_uuid(value))


def _dealer(client: ZMQClient, **kwargs) -> FakeSocket:
    sock = FakeSocket("dealer", **kwargs)
    client._dealer_socket = sock
    return sock


# ── 端点派生 ──

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


def test_explicit_endpoints_override_derived(log):
    client = ZMQClient(
        "tcp://127.0.0.1:5555", log_handler=log,
        pub_endpoint="tcp://127.0.0.1:6001",
        ctrl_endpoint="tcp://127.0.0.1:6002")
    assert client.pub_endpoint == "tcp://127.0.0.1:6001"
    assert client.ctrl_endpoint == "tcp://127.0.0.1:6002"
    assert client.endpoint == "tcp://127.0.0.1:5555"


# ── 类型注册 ──

def test_registration_methods_delegate_to_serializer(log):
    client = _new_client(log)
    assert "covz.evt" in [c.__struct_config__.tag for c in client._serializer._event_types]
    assert "covz.cmd" in [c.__struct_config__.tag for c in client._serializer._command_types]
    assert "covz.query" in client._serializer._query_tags
    assert "covz.result" in client._serializer._query_result_tags


# ── connect ──

def test_connect_when_thread_alive_and_accepting_returns_immediately(log):
    client = _new_client(log)
    thread = StubThread(alive=True)
    client._thread = thread
    client._accepting = True
    client.connect()
    assert thread.started is False
    assert client._accepting is True


def test_connect_when_thread_alive_and_stopping_raises(log):
    client = _new_client(log)
    client._thread = StubThread(alive=True)
    client._accepting = False
    with pytest.raises(RuntimeError, match="Client is still stopping"):
        client.connect()


def test_connect_ready_timeout_disconnects_and_raises(monkeypatch, log):
    _patch_threading(monkeypatch, InlineThread)
    client = _new_client(log)
    # _run no-op：避免同步 InlineThread 触发真实 zmq.Context / socket
    client._run = lambda: None
    client._ready = FakeEvent(wait_result=False)
    with pytest.raises(TimeoutError, match="Client I/O initialization timed out"):
        client.connect()
    assert client._accepting is False
    assert client._stopped.is_set() is True


def test_connect_startup_error_disconnects_and_reraises(monkeypatch, log):
    _patch_threading(monkeypatch, InlineThread)
    boom = RuntimeError("startup failed")
    client = _new_client(log)

    def fake_run():
        client._startup_error = boom
        client._ready.set()

    client._run = fake_run
    with pytest.raises(RuntimeError, match="startup failed") as exc:
        client.connect()
    assert exc.value is boom
    assert client._accepting is False


def test_connect_success_sets_accepting_and_ready(monkeypatch, log):
    sub, dealer = FakeSocket("sub"), FakeSocket("dealer")
    ctx = FakeContext(socket_map={real_zmq.SUB: sub, real_zmq.DEALER: dealer})
    _patch_zmq(monkeypatch, context=lambda: ctx)
    _patch_threading(monkeypatch, InlineThread)
    _patch_time(monkeypatch, monotonic=lambda: 0.0)
    _patch_uuid(monkeypatch, "abc123")

    client = _new_client(log)
    stopped = FakeEvent(flag=False)
    client._stopped = stopped
    # poller 第一次 poll 抛 ZMQError -> 记录警告并调用重连；第二次耗尽时
    # 自动置 stopped，使 _poll_loop 自然退出（纯内存，无真实线程）。
    poller = FakePoller(
        results=[real_zmq.ZMQError(errno.EIO)], stop_event=stopped)
    monkeypatch.setattr(client_module.zmq, "Poller", lambda: poller)
    client._handle_reconnect = lambda backoff: None

    client.connect()
    assert client._accepting is False  # _run finally 恢复
    assert client._ctx is None  # 已 term 并清空
    assert sub.closed and dealer.closed
    assert ctx.terminated is True
    assert ("dealer", "setsockopt_string", real_zmq.IDENTITY, "abc123") in dealer.log
    assert sub.connected == ["tcp://127.0.0.1:5556"]
    assert dealer.connected == ["tcp://127.0.0.1:5557"]
    assert poller.registered == [
        (sub, real_zmq.POLLIN), (dealer, real_zmq.POLLIN)]
    assert "Client transport error" in log.messages()


# ── disconnect ──

def test_disconnect_from_io_thread_returns_after_failing_pending(monkeypatch, log):
    client = _new_client(log)
    client._thread = _real_threading.current_thread()
    client._accepting = True
    future = FakeFuture()
    client._pending_requests["r1"] = future
    client.disconnect()
    assert client._accepting is False
    assert client._stopped.is_set() is True
    assert len(future.set_exceptions) == 1
    assert "Client disconnected" in str(future.set_exceptions[0])
    assert not client._pending_requests


def test_disconnect_raises_if_io_thread_does_not_stop(log):
    client = _new_client(log)
    thread = StubThread(alive=True, join_keeps_alive=True)
    client._thread = thread
    with pytest.raises(RuntimeError, match="Client I/O thread did not stop"):
        client.disconnect()
    assert thread.joined == [3.0]
    assert client._accepting is False


def test_disconnect_joins_and_clears_state(log):
    client = _new_client(log)
    thread = StubThread(alive=True)
    client._thread = thread
    client._is_connected = True
    client.disconnect()
    assert thread.joined == [3.0]
    assert client._thread is None
    assert client._is_connected is False
    assert client._accepting is False


# ── _run ──

def test_run_poll_loop_failure_after_ready_logs_error(monkeypatch, log):
    _patch_threading(monkeypatch, InlineThread)
    client = _new_client(log)
    client._ctx = FakeContext()
    client._create_sockets = lambda: None
    client._ready = FakeEvent()
    client._stopped = FakeEvent()

    def boom():
        raise RuntimeError("poll loop crashed")

    client._poll_loop = boom
    client._run()
    assert "Client I/O failed" in log.messages()
    assert client._startup_error is None
    assert client._ready.is_set() is True
    assert client._stopped.is_set() is True


def test_run_startup_failure_records_startup_error(monkeypatch, log):
    """_ready 尚未置位时抛错 -> 记录 _startup_error（而非写日志）。"""
    ctx = FakeContext()
    _patch_zmq(monkeypatch, context=lambda: ctx)
    client = _new_client(log)
    boom = RuntimeError("socket setup failed")

    def fail_create():
        raise boom

    client._create_sockets = fail_create
    client._ready = FakeEvent(flag=False)
    client._stopped = FakeEvent(flag=False)
    client._run()
    assert client._startup_error is boom
    assert "Client I/O failed" not in log.messages()
    assert ctx.terminated is True  # finally 仍清理 context
    assert client._ctx is None
    assert client._ready.is_set() is True


# ── _create_sockets ──

def test_create_sockets_ctx_none_returns(log):
    client = _new_client(log)
    client._ctx = None
    client._create_sockets()
    assert client._sub_socket is None and client._dealer_socket is None


def test_create_sockets_dealer_none_returns_before_connect(monkeypatch, log):
    sub = FakeSocket("sub")
    ctx = FakeContext(socket_map={real_zmq.SUB: sub, real_zmq.DEALER: None})
    _patch_zmq(monkeypatch, context=lambda: ctx)
    client = _new_client(log)
    client._ctx = ctx
    client._create_sockets()
    assert client._dealer_socket is None
    assert sub.connected == []
    assert not any(a[1] == "setsockopt" for a in sub.log)


def test_create_sockets_sub_none_returns_before_connect(monkeypatch, log):
    dealer = FakeSocket("dealer")
    ctx = FakeContext(socket_map={real_zmq.SUB: None, real_zmq.DEALER: dealer})
    _patch_zmq(monkeypatch, context=lambda: ctx)
    client = _new_client(log)
    client._ctx = ctx
    client._create_sockets()
    assert client._sub_socket is None
    assert dealer.connected == []
    assert client._poller is None
    # DEALER 心跳设置已完成
    assert [a[3] for a in dealer.log if a[1] == "setsockopt"] == [
        1, 0, 5000, 5000, 10000]


# ── _close_sockets ──

def test_close_sockets_closes_both_and_clears_all_state(monkeypatch, log):
    sub, dealer = FakeSocket("sub"), FakeSocket("dealer")
    client = _new_client(log)
    client._sub_socket = sub
    client._dealer_socket = dealer
    client._poller = FakePoller()
    client._active_topics = {"covz.evt"}
    client._active_versions = {"covz.evt": 1}
    client._snapshot_waiting = {"covz.evt"}
    client._sync_topics = {"r1": "covz.evt"}
    client._sync_deadlines = {"r1": 12.0}
    client._close_sockets()
    assert sub.closed and dealer.closed
    assert sub.close_linger == 0 and dealer.close_linger == 0
    assert client._sub_socket is None and client._dealer_socket is None
    assert client._poller is None
    assert not client._active_topics and not client._active_versions
    assert not client._snapshot_waiting
    assert not client._sync_topics and not client._sync_deadlines


# ── 订阅 ──

def test_subscribe_unsubscribe_and_update_subscriptions(monkeypatch, log):
    sub = FakeSocket("sub")
    client = _new_client(log)
    client._sub_socket = sub
    cb1, cb2 = lambda e: None, lambda e: None  # noqa: E731

    client.subscribe(CovEvent, cb1)
    assert client._subscribers["covz.evt"] == [cb1]
    assert client._subscription_versions["covz.evt"] == 1
    client.subscribe(CovEvent, cb2)
    assert client._subscription_versions["covz.evt"] == 2

    client._update_subscriptions()
    assert ("sub", "setsockopt_string", real_zmq.SUBSCRIBE, "covz.evt") in sub.log
    assert client._snapshot_waiting == {"covz.evt"}
    assert client._active_versions == {"covz.evt": 2}

    # 再调用一次，版本一致 -> 不再新增快照等待
    client._snapshot_waiting.clear()
    client._update_subscriptions()
    assert client._snapshot_waiting == set()

    client.unsubscribe(CovEvent)
    assert "covz.evt" not in client._subscribers
    assert "covz.evt" not in client._subscription_versions
    client._snapshot_waiting = {"covz.evt"}
    client._update_subscriptions()
    assert ("sub", "setsockopt_string", real_zmq.UNSUBSCRIBE, "covz.evt") in sub.log
    assert client._snapshot_waiting == set()
    assert client._active_topics == set()


def test_update_subscriptions_without_sub_socket_returns(log):
    client = _new_client(log)
    client._sub_socket = None
    client.subscribe(CovEvent, lambda e: None)
    client._update_subscriptions()
    assert client._snapshot_waiting == set()  # 未进入订阅协调


# ── _request_snapshot ──

def test_request_snapshot_without_dealer_returns_false(log):
    client = _new_client(log)
    assert client._request_snapshot("covz.evt") is False
    assert not client._sync_topics


def test_request_snapshot_zmq_again_returns_false(monkeypatch, log):
    dealer = _dealer(_new_client(log))
    dealer.send_error = real_zmq.Again()
    client = _new_client(log)
    client._dealer_socket = dealer
    _patch_uuid(monkeypatch, "snap1")
    assert client._request_snapshot("covz.evt") is False
    assert not client._sync_topics
    assert not client._sync_deadlines


def test_request_snapshot_success_tracks_topic_and_deadline(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _new_client(log)
    client._dealer_socket = dealer
    _patch_uuid(monkeypatch, "snap1")
    _patch_time(monkeypatch, monotonic=lambda: 100.0)
    assert client._request_snapshot("covz.evt") is True
    sent = [a for a in dealer.log if a[1] == "send"][0]
    assert sent[3] == real_zmq.NOBLOCK
    assert client._serializer.decode_command(sent[2]).topic == "covz.evt"
    assert client._sync_topics == {"snap1": "covz.evt"}
    assert client._sync_deadlines == {"snap1": 100.0 + client._SEND_TIMEOUT}


# ── _enqueue / _wait_for_response / request / query ──

def test_enqueue_rejects_when_not_accepting(log):
    client = _new_client(log)
    client._accepting = False
    with pytest.raises(RuntimeError, match="Client is not connected"):
        client._enqueue(_Outgoing(b"x", 10.0))


def test_enqueue_rejects_when_stopped(log):
    client = _new_client(log)
    client._accepting = True
    client._stopped.set()
    with pytest.raises(RuntimeError, match="Client is not connected"):
        client._enqueue(_Outgoing(b"x", 10.0))


def test_send_command_queue_full_raises_buffer_error(monkeypatch, log):
    from queue import Queue
    client = _new_client(log)
    client._accepting = True
    client._outgoing = Queue(1)
    client._enqueue(_Outgoing(b"first", 10.0))
    with pytest.raises(BufferError, match="Client send queue is full"):
        client.send_command(CovCommand(value=1))
    assert client._outgoing.qsize() == 1


def test_wait_for_response_on_io_thread_raises(monkeypatch, log):
    _patch_threading(monkeypatch, InlineThread)
    client = _new_client(log)
    # 伪造：把 client._thread 设为当前线程
    client._thread = _real_threading.current_thread()
    with pytest.raises(RuntimeError, match="Cannot wait for a response on the client I/O thread"):
        client._wait_for_response(b"x", "r1", 10.0, {})


def test_wait_for_response_not_accepting_raises(log):
    client = _new_client(log)
    client._accepting = False
    with pytest.raises(RuntimeError, match="Client is not connected"):
        client._wait_for_response(b"x", "r1", 10.0, {})


def test_wait_for_response_enqueue_failure_cleans_pending(log):
    client = _new_client(log)
    client._accepting = True
    pending: dict = {}

    def fail_enqueue(item):
        raise ValueError("enqueue broke")

    client._enqueue = fail_enqueue
    with pytest.raises(ValueError, match="enqueue broke"):
        client._wait_for_response(b"x", "r1", 10.0, pending)
    assert pending == {}


def test_request_and_query_success_cleanup_pending(monkeypatch, log):
    client = _new_client(log)
    client._accepting = True
    resp = CommandResponse(request_id="r1", success=True)
    query_result = CovResult(request_id="q1", value=8)
    expected = {"req": resp, "qry": query_result}

    def fake_wait(payload, request_id, deadline, pending):
        assert payload
        assert request_id
        assert deadline > 0
        assert pending is client._pending_requests or pending is client._pending_queries
        return expected["req"] if pending is client._pending_requests else expected["qry"]

    client._wait_for_response = fake_wait
    _patch_uuid(monkeypatch, "fixed")
    cmd = CovCommand(value=1)
    assert client.request(cmd, timeout=2.0) is resp
    assert cmd.request_id == "fixed"
    q = CovQuery(value=2)
    assert client.query(q, timeout=3.0) is query_result
    assert q.request_id == "fixed"


def test_wait_for_response_timeout_and_finally_cleanup(monkeypatch, log):
    client = _new_client(log)
    client._accepting = True
    from concurrent.futures import Future
    pending: dict = {}

    def fake_result(timeout=None):
        assert timeout is not None and timeout >= 0
        raise FutureTimeoutError("timed out")

    monkeypatch.setattr(Future, "result", lambda self, timeout=None: fake_result(timeout))
    _patch_time(monkeypatch, monotonic=lambda: 5.0)
    with pytest.raises(FutureTimeoutError):
        client._wait_for_response(b"x", "r1", 6.0, pending)
    assert pending == {}


# ── _send_queued ──

def test_send_queued_no_dealer_returns(log):
    client = _new_client(log)
    client._dealer_socket = None
    client._send_queued()


def _ready_send_client(log, dealer: FakeSocket) -> ZMQClient:
    client = _new_client(log)
    client._dealer_socket = dealer
    client._accepting = True
    return client


def test_send_queued_stopped_before_send_returns(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _ready_send_client(log, dealer)
    client._enqueue(_Outgoing(b"payload", 100.0))
    client._stopped.set()
    client._send_queued()
    assert not any(a[1] == "send" for a in dealer.log)
    # 该项已从队列取出并暂存为 deferred_send，stopped 检查阻止了实际发送
    assert client._outgoing.qsize() == 0
    assert client._deferred_send is not None


def test_send_queued_cancels_inactive_future(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _ready_send_client(log, dealer)
    future = FakeFuture()
    client._enqueue(_Outgoing(b"payload", 100.0, "r1", future))
    client._send_queued()
    assert not any(a[1] == "send" for a in dealer.log)
    assert client._deferred_send is None
    assert future.set_results == []


def test_send_queued_expires_async_command_with_warning(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _ready_send_client(log, dealer)
    client._enqueue(_Outgoing(b"payload", deadline=0.0))
    # time.monotonic() >= deadline -> 过期
    _patch_time(monkeypatch, monotonic=lambda: 10.0)
    client._send_queued()
    assert "Queued command expired before sending" in log.messages()
    assert not any(a[1] == "send" for a in dealer.log)
    assert client._deferred_send is None


def test_send_queued_expires_future_without_warning(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _ready_send_client(log, dealer)
    future = FakeFuture()
    client._pending_requests["r1"] = future
    client._enqueue(_Outgoing(b"payload", deadline=0.0, request_id="r1", future=future))
    _patch_time(monkeypatch, monotonic=lambda: 10.0)
    client._send_queued()
    assert "Queued command expired before sending" not in log.messages()
    assert client._pending_requests["r1"] is future  # 由 waiter 自行清理


def test_send_queued_zmq_again_keeps_deferred(monkeypatch, log):
    dealer = FakeSocket("dealer")
    dealer.send_error = real_zmq.Again()
    client = _ready_send_client(log, dealer)
    client._enqueue(_Outgoing(b"payload", 100.0))
    _patch_time(monkeypatch, monotonic=lambda: 0.0)
    client._send_queued()
    assert client._deferred_send is not None
    assert client._outgoing.qsize() == 0
    assert len([a for a in dealer.log if a[1] == "send"]) == 1


def test_send_queued_active_future_sends_with_noblock(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _ready_send_client(log, dealer)
    future = FakeFuture()
    client._pending_queries["q1"] = future
    client._enqueue(_Outgoing(b"payload", 100.0, "q1", future))
    _patch_time(monkeypatch, monotonic=lambda: 0.0)
    client._send_queued()
    sent = [a for a in dealer.log if a[1] == "send"]
    assert len(sent) == 1
    assert sent[0][2] == b"payload" and sent[0][3] == real_zmq.NOBLOCK
    assert client._deferred_send is None


# ── _poll_loop ──
#
# 统一约定：_stopped 用 FakeEvent，poller 的 stop_event 指向它；
# results 里最后一项固定为 ZMQError，使循环退出前有确定的一轮，
# 且 results 耗尽时 FakePoller 自动 set(stop_event)，避免纯内存死循环。

def _poll_client(log, poller: FakePoller) -> tuple[ZMQClient, FakeEvent]:
    client = _new_client(log)
    stopped = FakeEvent(flag=False)
    poller.stop_event = stopped
    client._stopped = stopped
    client._poller = poller
    return client, stopped


def test_poll_loop_poller_none_raises_runtime_error(monkeypatch, log):
    client = _new_client(log)
    client._poller = None
    recreated = []
    client._create_sockets = lambda: recreated.append(True)
    client._stopped = FakeEvent(flag=False)
    client._log = log
    # RuntimeError 不是 zmq.ZMQError，不会被轮询循环吞掉，直接冒泡
    with pytest.raises(RuntimeError, match="Client poller is not initialized"):
        client._poll_loop()
    assert recreated == [True]
    assert "Client transport error" not in log.messages()


def test_poll_loop_sub_and_dealer_events_and_snapshot_expiry(monkeypatch, log):
    sub, dealer = FakeSocket("sub"), FakeSocket("dealer")
    poller = FakePoller(results=[
        [(sub, real_zmq.POLLIN), (dealer, real_zmq.POLLIN)],
        real_zmq.ZMQError(errno.EIO),
    ])
    client, stopped = _poll_client(log, poller)
    client._sub_socket = sub
    client._dealer_socket = dealer
    client._is_connected = True
    client._probe_connection = lambda: True
    client._handle_sub_message = lambda: log.info("sub-handled")
    client._handle_dealer_message = lambda: log.info("dealer-handled")
    client._on_first_activity = lambda: log.info("activity")
    client._snapshot_waiting = {"covz.evt"}
    client._request_snapshot = lambda topic: True
    client._last_activity = 100.0
    client._sync_deadlines = {"expired": 0.0}
    client._sync_topics = {"expired": "covz.evt"}
    client._handle_reconnect = lambda backoff: None
    _patch_time(monkeypatch, monotonic=lambda: 100.0)
    client._poll_loop()
    assert "sub-handled" in log.messages()
    assert "dealer-handled" in log.messages()
    assert "activity" in log.messages()
    assert client._snapshot_waiting == set()
    assert client._sync_deadlines == {} and client._sync_topics == {}
    assert "Client transport error" in log.messages()
    assert stopped.is_set() is True  # 循环已退出，不会空转


def test_poll_loop_break_when_stopped_during_events(monkeypatch, log):
    sub = FakeSocket("sub")
    poller = FakePoller(results=[
        [(sub, real_zmq.POLLIN)],
        real_zmq.ZMQError(errno.EIO),
    ])
    client, stopped = _poll_client(log, poller)
    client._sub_socket = sub
    client._dealer_socket = FakeSocket("dealer")
    client._probe_connection = lambda: True
    # poll 返回事件后立即置 stopped -> for 循环第一个事件就 break
    original_poll = poller.poll

    def poll_then_stop(timeout):
        events = original_poll(timeout)
        stopped.set()
        return events

    poller.poll = poll_then_stop
    client._handle_sub_message = lambda: pytest.fail("should not handle after stop")
    client._send_queued = lambda: None
    client._update_subscriptions = lambda: None
    client._handle_reconnect = lambda backoff: None
    _patch_time(monkeypatch, monotonic=lambda: 0.0)
    client._last_activity = 0.0
    client._poll_loop()
    assert poller.poll_calls == [client._POLL_INTERVAL_MS]


def test_poll_loop_dealer_event_only_and_connection_timeout(monkeypatch, log):
    sub, dealer = FakeSocket("sub"), FakeSocket("dealer")
    poller = FakePoller(results=[
        [(dealer, real_zmq.POLLIN)],
        real_zmq.ZMQError(errno.EIO),
    ])
    client, stopped = _poll_client(log, poller)
    client._sub_socket = sub
    client._dealer_socket = dealer
    client._probe_connection = lambda: True
    client._handle_dealer_message = lambda: None
    client._on_first_activity = lambda: None
    client._last_activity = 0.0
    reconnects = []
    client._handle_reconnect = lambda backoff: reconnects.append(backoff)
    _patch_time(monkeypatch, monotonic=lambda: 1000.0)
    client._poll_loop()
    # 连接超时分支 + ZMQError 异常分支各触发一次重连
    assert reconnects == [0.1, 0.1]


def test_poll_loop_zmq_error_from_poll_triggers_reconnect(monkeypatch, log):
    poller = FakePoller(results=[real_zmq.ZMQError(errno.EIO)])
    client, stopped = _poll_client(log, poller)
    reconnects = []
    client._handle_reconnect = lambda backoff: (
        reconnects.append(backoff), stopped.set())
    _patch_time(monkeypatch, monotonic=lambda: 0.0)
    client._last_activity = 0.0
    client._probe_connection = lambda: True
    client._send_queued = lambda: None
    client._update_subscriptions = lambda: None
    client._sub_socket = FakeSocket("sub")
    client._dealer_socket = FakeSocket("dealer")
    client._poll_loop()
    assert "Client transport error" in log.messages()
    assert reconnects == [0.1]
