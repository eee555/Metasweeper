"""启动事件窗口测试：不连接真实 ZMQ，也不启动 Qt 插件线程。"""
from __future__ import annotations

import threading
from concurrent.futures import Future
from types import SimpleNamespace

import pytest

from lib_zmq_plugins.shared.base import get_event_tag
from plugin_manager import plugin_manager as module
from shared_types.events import GameFinishedEvent, LanguageChangeEvent


class FakeClient:
    def __init__(self, **kwargs):
        self.handlers = {}
        self.connected = False
        self.disconnects = 0
        self.on_connect = lambda: None

    def register_event_types(self, *args):
        pass

    def register_command_types(self, *args):
        pass

    def register_query_types(self, *args, **kwargs):
        pass

    def subscribe(self, event_type, callback):
        self.handlers[event_type] = callback

    def connect(self):
        self.connected = True
        self.on_connect()

    def disconnect(self):
        self.connected = False
        self.disconnects += 1

    def emit(self, event):
        callback = self.handlers.get(type(event))
        if callback is not None:
            callback(event)


class FakePlugin:
    name = "startup-test"
    is_enabled = True

    def __init__(self):
        self.received = []
        self.on_initialize = lambda: None
        self.shutdowns = 0

    def set_client(self, client):
        self.client = client

    def set_event_dispatcher(self, dispatcher):
        self.dispatcher = dispatcher

    def initialize(self):
        self.on_initialize()
        # 模拟 BasePlugin.initialize 同步完成 _setup_subscriptions 的契约。
        self.dispatcher.subscribe(
            get_event_tag(GameFinishedEvent), self.received.append, plugin=self,
        )

    def _enqueue_event(self, handler, event):
        handler(event)
        return True

    def shutdown(self):
        self.shutdowns += 1


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(module, "ZMQClient", FakeClient)
    monkeypatch.setattr(module, "_TranslatorInstaller", lambda: SimpleNamespace(
        install=lambda language: None,
    ))
    monkeypatch.setattr(module.PluginManager, "_register_shutdown_handlers", lambda self: None)
    monkeypatch.setattr(module.PluginManager, "_validate_control_authorizations", lambda self: None)
    # 此处仅测试启动事件缓冲，隔离依赖真实 PluginInfo 的持久化状态恢复。
    monkeypatch.setattr(module.PluginManager, "_apply_saved_plugin_states", lambda self: None)
    previous = module.PluginManager._instance
    instance = module.PluginManager("inproc://startup-test", plugin_dirs=[])
    plugin = FakePlugin()
    monkeypatch.setattr(instance._loader, "load_all", lambda: [plugin])
    yield instance, plugin
    instance.stop()
    module.PluginManager._instance = previous


def launch(action):
    errors = []

    def run():
        try:
            action()
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


def finish(worker):
    thread, errors = worker
    thread.join(3)
    assert not thread.is_alive(), "event callback or startup deadlocked"
    assert not errors, errors


def test_connect_and_initialize_events_reach_late_registered_handler(manager):
    instance, plugin = manager
    first, second, third = GameFinishedEvent(), GameFinishedEvent(), GameFinishedEvent()
    instance.client.on_connect = lambda: instance.client.emit(first)

    def initialize():
        assert instance.client.connected
        assert not plugin.received
        instance.client.emit(second)
        assert not plugin.received

    plugin.on_initialize = initialize
    instance.start()
    instance.client.emit(third)
    assert plugin.received == [first, second, third]
    assert all(actual is expected for actual, expected in zip(
        plugin.received, [first, second, third],
    ))
    instance.start()  # 幂等，不重复注册订阅或重放。
    assert plugin.received == [first, second, third]


def test_initialization_query_can_finish_on_receiver_thread(manager):
    instance, plugin = manager
    event = GameFinishedEvent()
    workers = []

    def initialize():
        response = Future()

        def receive():
            instance.client.emit(event)
            # 模拟同一接收线程继续解析并完成查询响应。
            response.set_result("query-result")

        workers.append(launch(receive))
        assert response.result(timeout=3) == "query-result"
        assert not plugin.received

    plugin.on_initialize = initialize
    instance.start()
    for worker in workers:
        finish(worker)
    assert plugin.received == [event]


def test_arrivals_during_drain_cannot_overtake_buffer(manager, monkeypatch):
    instance, _ = manager
    first, second, third, live = [GameFinishedEvent() for _ in range(4)]
    entered, release = threading.Event(), threading.Event()
    received = []

    def dispatch(tag, event):
        if event is first:
            entered.set()
            assert release.wait(3)
        received.append(event)

    monkeypatch.setattr(instance.dispatcher, "dispatch", dispatch)
    instance.client.on_connect = lambda: instance.client.emit(first)
    worker = launch(instance.start)
    try:
        assert entered.wait(3)
        arrivals = launch(lambda: (
            instance.client.emit(second), instance.client.emit(third),
        ))
        finish(arrivals)  # 分发阻塞时接收仍可返回。
        assert not received
    finally:
        release.set()
        finish(worker)
    instance.client.emit(live)
    assert all(actual is expected for actual, expected in zip(
        received, [first, second, third, live], strict=True,
    ))


def test_reentrant_arrival_is_serialized_outside_lock(manager, monkeypatch):
    instance, _ = manager
    first, second = GameFinishedEvent(), GameFinishedEvent()
    received = []

    def dispatch(tag, event):
        if event is first:
            instance.client.emit(second)
        received.append(event)

    monkeypatch.setattr(instance.dispatcher, "dispatch", dispatch)
    instance.client.on_connect = lambda: instance.client.emit(first)
    finish(launch(instance.start))
    assert len(received) == 2
    assert received[0] is first and received[1] is second


def test_language_event_uses_same_startup_order(manager, monkeypatch):
    instance, plugin = manager
    first, language, last = GameFinishedEvent(), LanguageChangeEvent(), GameFinishedEvent()
    received = []
    monkeypatch.setattr(instance, "_install_translator", lambda value: received.append(value))
    monkeypatch.setattr(instance.dispatcher, "dispatch", lambda tag, event: received.append(event))

    def initialize():
        instance.client.emit(first)
        instance.client.emit(language)
        instance.client.emit(last)
        assert not received

    plugin.on_initialize = initialize
    instance.start()
    assert received == [first, language.language, language, last]


@pytest.mark.parametrize("stage", ["_load_plugins", "connect", "_initialize_plugins",
                                   "_validate_control_authorizations"])
def test_fatal_startup_failure_discards_buffer_and_closes(manager, monkeypatch, stage):
    instance, plugin = manager
    event = GameFinishedEvent()

    def fail():
        instance._queue_zmq_event(get_event_tag(GameFinishedEvent), event)
        raise RuntimeError("startup failed")

    target = instance.client if stage == "connect" else instance
    monkeypatch.setattr(target, stage, fail)
    with pytest.raises(RuntimeError, match="startup failed"):
        instance.start()
    assert not plugin.received
    assert not instance._pending_events
    assert not instance._started and not instance._starting
    assert instance._shutdown_requested
    assert instance.client.disconnects == 1
    assert not instance.dispatcher.get_handlers(get_event_tag(GameFinishedEvent))
    instance._queue_zmq_event(get_event_tag(GameFinishedEvent), event)
    assert not instance._pending_events
    instance.stop()
    assert instance.client.disconnects == 1
    with pytest.raises(RuntimeError, match="Cannot restart"):
        instance.start()


def test_shutdown_during_initialization_drops_buffer(manager):
    instance, plugin = manager
    event = GameFinishedEvent()
    instance.client.on_connect = lambda: instance.client.emit(event)
    plugin.on_initialize = instance.stop
    instance.start()
    assert not plugin.received
    assert not instance._started
    assert not instance._pending_events
    instance.client.emit(GameFinishedEvent())
    assert not plugin.received


def test_shutdown_from_dispatch_callback_does_not_deadlock(manager, monkeypatch):
    instance, _ = manager
    first, second = GameFinishedEvent(), GameFinishedEvent()
    received = []

    def dispatch(tag, event):
        received.append(event)
        instance.stop()

    monkeypatch.setattr(instance.dispatcher, "dispatch", dispatch)
    instance.client.on_connect = lambda: (
        instance.client.emit(first), instance.client.emit(second),
    )
    finish(launch(instance.start))
    assert received == [first]
    assert not instance._started
    assert not instance._pending_events


def test_dispatch_failure_does_not_strand_following_events(manager, monkeypatch):
    instance, _ = manager
    first, second, live = GameFinishedEvent(), GameFinishedEvent(), GameFinishedEvent()
    received = []

    def dispatch(tag, event):
        if event is first:
            raise RuntimeError("broken dispatcher")
        received.append(event)

    monkeypatch.setattr(instance.dispatcher, "dispatch", dispatch)
    instance.client.on_connect = lambda: (
        instance.client.emit(first), instance.client.emit(second),
    )
    instance.start()
    instance.client.emit(live)
    assert received == [second, live]


def test_concurrent_shutdown_discards_waiting_events_but_allows_inflight(manager, monkeypatch):
    instance, _ = manager
    first, second, last = [GameFinishedEvent() for _ in range(3)]
    entered, release = threading.Event(), threading.Event()
    received = []

    def dispatch(tag, event):
        entered.set()
        assert release.wait(3)
        received.append(event)

    monkeypatch.setattr(instance.dispatcher, "dispatch", dispatch)
    instance.client.on_connect = lambda: (
        instance.client.emit(first), instance.client.emit(second),
    )
    worker = launch(instance.start)
    try:
        assert entered.wait(3)
        finish(launch(instance.stop))
        instance.client.emit(last)
        assert not instance._pending_events
    finally:
        release.set()
        finish(worker)
    assert len(received) == 1 and received[0] is first
    assert not instance._started and not instance._events_draining


def test_real_zmq_initialization_query_preserves_early_finished_event(manager):
    from lib_zmq_plugins.client.zmq_client import ZMQClient
    from lib_zmq_plugins.server.zmq_server import ZMQServer
    from lib_zmq_plugins.shared.base import BaseQuery, BaseQueryResult
    from shared_types import EVENT_TYPES

    class StartupQuery(BaseQuery, tag="startup.query"):
        pass

    server = ZMQServer("tcp://127.0.0.1", bind_to_random_port=True)
    server.register_event_types(*EVENT_TYPES)
    server.register_query_types(StartupQuery)
    instance, plugin = manager
    event_queued = threading.Event()
    original_queue = instance._queue_zmq_event

    def queue(tag, event):
        original_queue(tag, event)
        if isinstance(event, GameFinishedEvent):
            event_queued.set()

    instance._queue_zmq_event = queue
    # 快照经真实 DEALER 响应到达；其后的查询在同一 I/O 线程上继续处理。
    server.register_snapshot_provider(GameFinishedEvent, GameFinishedEvent)

    def answer(query):
        assert event_queued.wait(3)
        return BaseQueryResult(request_id=query.request_id)

    server.register_query_handler(StartupQuery, answer)
    server.start()
    client = ZMQClient(server.endpoint, pub_endpoint=server.pub_endpoint,
                       ctrl_endpoint=server.ctrl_endpoint)
    client.register_event_types(*EVENT_TYPES)
    client.register_query_types(StartupQuery)
    instance._client = client

    def initialize():
        assert event_queued.wait(3)
        assert client.query(StartupQuery(), timeout=3).success
        assert not plugin.received

    plugin.on_initialize = initialize
    try:
        instance.start()
        assert len(plugin.received) == 1
        assert isinstance(plugin.received[0], GameFinishedEvent)
        assert not instance._pending_events
    finally:
        instance.stop()
        server.stop()