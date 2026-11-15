from __future__ import annotations

from concurrent.futures import Future
from types import SimpleNamespace

import pytest

import plugin_sdk.server_bridge as bridge_module
from lib_zmq_plugins.shared.base import BaseCommand, BaseEvent, BaseQuery, BaseQueryResult, CommandResponse
from plugin_sdk.server_bridge import GameServerBridge


class BridgeCommand(BaseCommand, tag="bridge-test-command"):
    value: int = 0


class BridgeEvent(BaseEvent, tag="bridge-test-event"):
    value: int = 0


class BridgeQuery(BaseQuery, tag="bridge-test-query"):
    value: int = 0


class BridgeResult(BaseQueryResult, tag="bridge-test-result"):
    value: int = 0


class FakeServer:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.events = []
        self.commands = []
        self.queries = []
        self.results = []
        self.handlers = {}
        self.query_handlers = {}
        self._pub_socket = None
        self.pub_endpoint = "tcp://127.0.0.1:2001"
        self.ctrl_endpoint = "tcp://127.0.0.1:2002"
        self.started = 0
        self.stopped = 0
        type(self).instances.append(self)

    def register_event_types(self, *values): self.events.extend(values)
    def register_command_types(self, *values): self.commands.extend(values)
    def register_query_types(self, *values): self.queries.extend(values)
    def register_query_result_types(self, *values): self.results.extend(values)
    def register_handler(self, command_type, handler): self.handlers[command_type] = handler
    def register_query_handler(self, query_type, handler): self.query_handlers[query_type] = handler
    def start(self): self.started += 1
    def stop(self): self.stopped += 1
    def publish(self, event_type, event): self.events.append((event_type, event))


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.setattr(GameServerBridge, "_instance", None)
    monkeypatch.setattr(bridge_module, "ZMQServer", FakeServer)
    FakeServer.instances.clear()
    result = GameServerBridge("tcp://localhost:5555", bind_to_random_port=False)
    yield result
    result.stop()
    monkeypatch.setattr(GameServerBridge, "_instance", None)


def test_singleton_endpoint_server_registration_and_lifecycle(bridge, monkeypatch):
    assert bridge is GameServerBridge.instance()
    assert bridge.endpoint == "tcp://localhost:5555"
    assert bridge.pub_endpoint == "tcp://127.0.0.1:2001"
    assert bridge.ctrl_endpoint == "tcp://127.0.0.1:2002"
    assert bridge.server is FakeServer.instances[0]
    assert bridge.server.kwargs["bind_to_random_port"] is False
    assert bridge.server.events
    assert bridge.server.commands
    assert bridge.server.queries
    assert bridge.server.results
    bridge.start()
    bridge.stop()
    assert bridge.server.started == 1
    assert bridge.server.stopped == 1


def test_execute_handler_resolves_and_fails_future(bridge):
    future = Future()
    bridge._on_execute(lambda cmd: cmd.value + 1, BridgeCommand(value=4), future)
    assert future.result() == 5

    failed = Future()
    bridge._on_execute(lambda _cmd: (_ for _ in ()).throw(ValueError("handler failed")), BridgeCommand(), failed)
    with pytest.raises(ValueError, match="handler failed"):
        failed.result()


def test_command_handlers_dispatch_sync_and_async(bridge, monkeypatch):
    calls = []
    emitted = []
    handler = lambda cmd: calls.append(cmd) or CommandResponse(request_id=cmd.request_id or "", success=True)
    bridge.register_handler(BridgeCommand, handler)
    wrapped = bridge.server.handlers[BridgeCommand]
    assert len(bridge._handlers) == 1
    assert bridge._handlers["bridge-test-command"] is handler

    # Exercise synchronous dispatch by resolving the queued future inline.
    sync_future = Future()
    def emit_sync(fn, cmd, future):
        emitted.append((fn, cmd, future))
        bridge._on_execute(fn, cmd, future)
    monkeypatch.setattr(bridge, "_execute_signal", SimpleNamespace(emit=emit_sync))
    sync_cmd = BridgeCommand(request_id="sync")
    result = wrapped(sync_cmd)
    assert result.success is True
    assert calls == [sync_cmd]

    monkeypatch.setattr(bridge, "_execute_signal", SimpleNamespace(emit=lambda *args: emitted.append(args)))
    assert wrapped(BridgeCommand()) is None
    assert emitted[-1][2] is None


def test_query_handler_dispatches_and_send_event_guard(bridge, monkeypatch):
    def emit_inline(handler, query, future):
        bridge._on_execute(handler, query, future)
    monkeypatch.setattr(bridge, "_execute_signal", SimpleNamespace(emit=emit_inline))
    bridge.register_query_handler(BridgeQuery, lambda query: BridgeResult(value=query.value * 2))
    wrapped = bridge.server.query_handlers[BridgeQuery]
    assert wrapped(BridgeQuery(value=6)) == BridgeResult(value=12)

    event = BridgeEvent(value=3)
    bridge.send_event(event)
    assert all(not isinstance(item, tuple) for item in bridge.server.events)
    bridge.server._pub_socket = object()
    bridge.send_event(event)
    assert bridge.server.events[-1] == (BridgeEvent, event)


def test_default_endpoint_uses_environment(monkeypatch):
    monkeypatch.setattr(GameServerBridge, "_instance", None)
    monkeypatch.setattr(bridge_module, "ZMQServer", FakeServer)
    monkeypatch.setenv("METASWEEPER_ZMQ_ENDPOINT", "tcp://env:7777")
    instance = GameServerBridge.instance()
    assert instance.endpoint == "tcp://env:7777"
    monkeypatch.setattr(GameServerBridge, "_instance", None)
