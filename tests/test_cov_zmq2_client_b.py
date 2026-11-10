"""第二轮定点补测（client B）：消息收发、订阅分发、pending 解析、
首次活动/连接回调、探测、重连、属性。

全程伪造：FakeSocket / FakeFuture / FakeEvent / FakePoller / FakeContext /
InlineThread。不创建真实 ZMQ 对象、不绑定端口、不启动 OS 线程。
"""
from __future__ import annotations

import errno

import pytest
import zmq as real_zmq

from lib_zmq_plugins.client import zmq_client as client_module
from lib_zmq_plugins.client.zmq_client import ZMQClient, _Outgoing
from lib_zmq_plugins.shared.base import (
    BaseQueryResult, CommandResponse, SyncCommand,
)
from tests.test_cov_zmq2_common import (
    CovCommand, CovEvent, CovQuery, CovResult, FakeEvent, FakeFuture,
    FakeSocket, RecLog, encode, fake_time, fake_uuid, fake_zmq, tagged,
)


@pytest.fixture
def log() -> RecLog:
    return RecLog()


def _new_client(log: RecLog, **kwargs) -> ZMQClient:
    client = ZMQClient("tcp://127.0.0.1:5555", log_handler=log, **kwargs)
    client.register_event_types(CovEvent)
    client.register_command_types(CovCommand)
    client.register_query_types(CovQuery, result_types=(CovResult,))
    return client


def _resp_payload(**kwargs) -> bytes:
    return client_module.Serializer().encode_response(
        CommandResponse(**kwargs))


def _result_payload(result: BaseQueryResult) -> bytes:
    return client_module.Serializer().encode_query_result(result)


# ── _on_first_activity / _notify_connection ──

def test_on_first_activity_transitions_and_notifies_once(log):
    events = []
    client = _new_client(log, on_connected=lambda: events.append("up"))
    client._is_connected = False
    client._has_ever_connected = False
    client._last_activity = 0.0

    client._on_first_activity()
    assert client._is_connected is True
    assert client._has_ever_connected is True
    assert client._last_activity >= 0.0
    assert events == ["up"]
    assert "Server connection confirmed (first activity)" in log.messages()

    # 再次调用：已连接 -> 早退，不重复通知
    client._on_first_activity()
    assert events == ["up"]


def test_notify_connection_callback_exception_is_logged(log):
    def boom():
        raise RuntimeError("callback broke")

    client = _new_client(log)
    client._notify_connection(boom)
    assert "Connection callback error" in log.messages()
    # None 回调是 no-op
    client._notify_connection(None)
    assert log.levels().count("error") == 1


def test_notify_connection_callback_runs(log):
    calls = []
    client = _new_client(log)
    client._notify_connection(lambda: calls.append("ok"))
    assert calls == ["ok"]


# ── _probe_connection ──

def test_probe_connection_without_dealer_returns_false(monkeypatch, log):
    client = _new_client(log)
    client._dealer_socket = None
    assert client._probe_connection() is False


def test_probe_connection_success_sends_sync_with_noblock(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _new_client(log)
    client._dealer_socket = dealer
    monkeypatch.setattr(client_module, "uuid", fake_uuid("probe-id"))
    assert client._probe_connection() is True
    sent = [a for a in dealer.log if a[1] == "send"][0]
    assert sent[3] == real_zmq.NOBLOCK
    cmd = client._serializer.decode_command(sent[2])
    assert isinstance(cmd, SyncCommand)
    assert cmd.request_id == "probe-id" and cmd.topic == "__probe__"


def test_probe_connection_zmq_error_returns_false(monkeypatch, log):
    dealer = FakeSocket("dealer")
    dealer.send_error = real_zmq.ZMQError(errno.EIO)
    client = _new_client(log)
    client._dealer_socket = dealer
    assert client._probe_connection() is False


def test_probe_connection_encode_failure_not_caught(monkeypatch, log):
    dealer = FakeSocket("dealer")
    client = _new_client(log)
    client._dealer_socket = dealer
    monkeypatch.setattr(client._serializer, "encode_command",
                        lambda cmd: (_ for _ in ()).throw(ValueError("encode broke")))
    # 源码只捕获 ZMQError/Again；编码异常会冒泡（如实记录此行为）
    with pytest.raises(ValueError, match="encode broke"):
        client._probe_connection()
    assert not any(a[1] == "send" for a in dealer.log)


# ── _handle_sub_message ──

def test_handle_sub_message_zmq_again_returns(monkeypatch, log):
    sub = FakeSocket("sub")
    sub.recv_error = real_zmq.Again()
    client = _new_client(log)
    client._sub_socket = sub
    client._handle_sub_message()


def test_handle_sub_message_short_frame_returns(log):
    sub = FakeSocket("sub")
    sub.recv_messages = [[b"only-topic"]]
    client = _new_client(log)
    client._sub_socket = sub
    client._handle_sub_message()


def test_handle_sub_message_invalid_payload_logs_warning(log):
    sub = FakeSocket("sub")
    sub.recv_messages = [[b"covz.evt", b"not-msgpack"]]
    client = _new_client(log)
    client._sub_socket = sub
    received = []
    client.subscribe(CovEvent, received.append)
    client._handle_sub_message()
    assert any("Failed to decode event for topic" in m for m in log.messages())
    assert received == []


def test_handle_sub_message_dispatches_event_with_decode_errors_replace(log):
    sub = FakeSocket("sub")
    payload = client_module.Serializer().encode_event(CovEvent(value=11))
    sub.recv_messages = [[b"covz.evt", payload]]
    client = _new_client(log)
    client._sub_socket = sub
    received = []
    client.subscribe(CovEvent, received.append)
    client._handle_sub_message()
    assert len(received) == 1 and received[0].value == 11


def test_handle_sub_message_invalid_utf8_topic_is_replaced(log):
    sub = FakeSocket("sub")
    payload = client_module.Serializer().encode_event(CovEvent(value=1))
    # topic 含非法 UTF-8 字节，decode(errors="replace") 不应抛异常
    sub.recv_messages = [[b"\xff\xfe", payload]]
    client = _new_client(log)
    client._sub_socket = sub
    client._handle_sub_message()
    # 无订阅者匹配，仅验证不抛异常且解码成功路径被执行


def test_notify_subscribers_callback_error_is_logged(log):
    client = _new_client(log)
    client.subscribe(CovEvent, lambda e: (_ for _ in ()).throw(
        RuntimeError("subscriber broke")))
    client.subscribe(CovEvent, lambda e: log.info("second ran"))
    client._notify_subscribers("covz.evt", CovEvent(value=1))
    assert "Subscriber callback error" in log.messages()
    assert "second ran" in log.messages()  # 一个回调失败不影响其余回调


# ── _handle_dealer_message ──

def test_handle_dealer_message_zmq_again_returns(log):
    dealer = FakeSocket("dealer")
    dealer.recv_error = real_zmq.Again()
    client = _new_client(log)
    client._dealer_socket = dealer
    client._handle_dealer_message()


def test_handle_dealer_message_short_frame_returns(log):
    dealer = FakeSocket("dealer")
    dealer.recv_messages = [[b""]]
    client = _new_client(log)
    client._dealer_socket = dealer
    client._handle_dealer_message()


def test_handle_dealer_message_query_result_resolves_pending(monkeypatch, log):
    dealer = FakeSocket("dealer")
    payload = _result_payload(CovResult(request_id="q1", value=77))
    dealer.recv_messages = [[b"", payload]]
    client = _new_client(log)
    client._dealer_socket = dealer
    future = FakeFuture()
    client._pending_queries["q1"] = future
    client._handle_dealer_message()
    assert len(future.set_results) == 1
    assert future.set_results[0].value == 77
    assert "q1" not in client._pending_queries


def test_handle_dealer_message_query_result_decode_failure_logs(log):
    dealer = FakeSocket("dealer")
    # tag 合法但字段类型错误 -> decode_query_result 抛 ValidationError
    payload = tagged("covz.result", value="not-an-int")
    dealer.recv_messages = [[b"", payload]]
    client = _new_client(log)
    client._dealer_socket = dealer
    client._handle_dealer_message()
    assert "Failed to decode query result" in log.messages()


def test_handle_dealer_message_response_decode_failure_logs(log):
    dealer = FakeSocket("dealer")
    dealer.recv_messages = [[b"", b"not-msgpack"]]
    client = _new_client(log)
    client._dealer_socket = dealer
    client._handle_dealer_message()
    assert "Failed to decode response" in log.messages()


def test_handle_dealer_message_response_without_empty_delimiter_uses_last(log):
    dealer = FakeSocket("dealer")
    payload = _resp_payload(request_id="r1", success=True)
    # 首帧非空 -> payload = msg[-1]
    dealer.recv_messages = [[b"identity", b"junk", payload]]
    client = _new_client(log)
    client._dealer_socket = dealer
    future = FakeFuture()
    client._pending_requests["r1"] = future
    client._handle_dealer_message()
    assert len(future.set_results) == 1
    assert future.set_results[0].success is True


def test_handle_dealer_message_snapshot_success_notifies_subscribers(log):
    dealer = FakeSocket("dealer")
    snapshot = client_module.Serializer().encode_event(CovEvent(value=55))
    payload = _resp_payload(request_id="s1", success=True, data=snapshot)
    dealer.recv_messages = [[b"", payload]]
    client = _new_client(log)
    client._dealer_socket = dealer
    received = []
    client.subscribe(CovEvent, received.append)
    client._sync_topics["s1"] = "covz.evt"
    client._sync_deadlines["s1"] = 999.0
    client._handle_dealer_message()
    assert len(received) == 1 and received[0].value == 55
    assert "s1" not in client._sync_topics
    assert "s1" not in client._sync_deadlines


def test_handle_dealer_message_snapshot_decode_failure_logs(log):
    dealer = FakeSocket("dealer")
    payload = _resp_payload(request_id="s1", success=True, data=b"bad-event")
    dealer.recv_messages = [[b"", payload]]
    client = _new_client(log)
    client._dealer_socket = dealer
    client._sync_topics["s1"] = "covz.evt"
    client._sync_deadlines["s1"] = 999.0
    client._handle_dealer_message()
    assert "Failed to decode snapshot" in log.messages()
    assert "s1" not in client._sync_topics  # 仍会清理映射


def test_handle_dealer_message_failure_response_cleans_sync_maps(log):
    dealer = FakeSocket("dealer")
    payload = _resp_payload(request_id="s2", success=False, error="nope")
    dealer.recv_messages = [[b"", payload]]
    client = _new_client(log)
    client._dealer_socket = dealer
    client._sync_topics["s2"] = "covz.evt"
    client._sync_deadlines["s2"] = 999.0
    future = FakeFuture()
    client._pending_requests["s2"] = future
    client._handle_dealer_message()
    assert "s2" not in client._sync_topics
    assert "s2" not in client._sync_deadlines
    assert len(future.set_results) == 1
    assert future.set_results[0].success is False


def test_handle_dealer_message_snapshot_no_matching_topic(log):
    dealer = FakeSocket("dealer")
    snapshot = client_module.Serializer().encode_event(CovEvent(value=1))
    payload = _resp_payload(request_id="s3", success=True, data=snapshot)
    dealer.recv_messages = [[b"", payload]]
    client = _new_client(log)
    client._dealer_socket = dealer
    received = []
    client.subscribe(CovEvent, received.append)
    # 没有 _sync_topics 记录 -> topic 为 None，不触发订阅者
    client._handle_dealer_message()
    assert received == []
    assert "Failed to decode snapshot" not in log.messages()


# ── _resolve_pending / _resolve_query_result ──

def test_resolve_pending_sets_result_only_for_known_request(log):
    client = _new_client(log)
    future = FakeFuture()
    client._pending_requests["r1"] = future
    client._resolve_pending(CommandResponse(request_id="r1", success=True))
    assert future.set_results[0].request_id == "r1"
    assert client._pending_requests == {}
    # 未知 request_id 是 no-op
    client._resolve_pending(CommandResponse(request_id="missing", success=True))


def test_resolve_query_result_sets_result_only_for_known_request(log):
    client = _new_client(log)
    future = FakeFuture()
    client._pending_queries["q1"] = future
    client._resolve_query_result(CovResult(request_id="q1", value=3))
    assert future.set_results[0].value == 3
    assert client._pending_queries == {}
    client._resolve_query_result(CovResult(request_id="missing"))


# ── _fail_pending / _discard_outgoing / _handle_reconnect ──

def test_fail_pending_fails_all_and_clears_both_dicts(log):
    client = _new_client(log)
    f1, f2, done = FakeFuture(), FakeFuture(), FakeFuture(done=True)
    client._pending_requests["r1"] = f1
    client._pending_queries["q1"] = f2
    client._pending_requests["r2"] = done
    error = ConnectionError("boom")
    client._fail_pending(error)
    assert client._pending_requests == {} and client._pending_queries == {}
    assert f1.set_exceptions == [error]
    assert f2.set_exceptions == [error]
    assert done.set_exceptions == []  # 已完成的不重复设置


def test_discard_outgoing_empties_queue_and_deferred(monkeypatch, log):
    client = _new_client(log)
    client._accepting = True
    client._enqueue(_Outgoing(b"p1", 10.0))
    client._enqueue(_Outgoing(b"p2", 10.0))
    client._deferred_send = _Outgoing(b"p3", 10.0)
    client._discard_outgoing()
    assert client._deferred_send is None
    assert client._outgoing.empty()


def test_handle_reconnect_was_not_connected(monkeypatch, log):
    sub, dealer = FakeSocket("sub"), FakeSocket("dealer")
    client = _new_client(log)
    client._sub_socket = sub
    client._dealer_socket = dealer
    client._is_connected = False
    client._accepting = True
    client._enqueue(_Outgoing(b"payload", 10.0))
    f = FakeFuture()
    client._pending_queries["q1"] = f
    client._snapshot_waiting = {"covz.evt"}
    client._sync_topics = {"s1": "covz.evt"}
    client._sync_deadlines = {"s1": 1.0}
    client._stopped = FakeEvent(flag=False)

    client._handle_reconnect(0.1)

    assert client.reconnect_count == 0  # 未连接过不计数
    assert client._is_connected is False
    assert not client._pending_queries
    assert len(f.set_exceptions) == 1
    assert "Server connection lost" in str(f.set_exceptions[0])
    assert client._outgoing.empty()
    assert sub.closed and dealer.closed
    assert client._sub_socket is None and client._dealer_socket is None
    assert not client._snapshot_waiting
    assert not client._sync_topics and not client._sync_deadlines
    assert client._stopped.waits == [0.1]


def test_handle_reconnect_was_connected_notifies_disconnected(monkeypatch, log):
    events = []
    client = _new_client(log, on_disconnected=lambda: events.append("down"))
    client._is_connected = True
    client._has_ever_connected = True
    client._stopped = FakeEvent(flag=False)
    client._sub_socket = FakeSocket("sub")
    client._dealer_socket = FakeSocket("dealer")

    client._handle_reconnect(0.05)

    assert events == ["down"]
    assert client.reconnect_count == 1
    assert client._is_connected is False
    assert client._stopped.waits == [0.05]


def test_handle_reconnect_disconnect_callback_error_is_logged(log):
    def boom():
        raise RuntimeError("down broke")

    client = _new_client(log, on_disconnected=boom)
    client._is_connected = True
    client._stopped = FakeEvent(flag=False)
    client._handle_reconnect(0.0)
    assert "Connection callback error" in log.messages()
    assert client.reconnect_count == 1


# ── 属性 ──

def test_properties_expose_internal_state(log):
    client = _new_client(log)
    assert client.is_connected is False
    assert client.reconnect_count == 0
    assert client.endpoint == "tcp://127.0.0.1:5555"
    assert client.pub_endpoint == "tcp://127.0.0.1:5556"
    assert client.ctrl_endpoint == "tcp://127.0.0.1:5557"
    client._is_connected = True
    client._reconnect_count = 4
    assert client.is_connected is True
    assert client.reconnect_count == 4
