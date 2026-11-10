"""plugin_base.py 覆盖率补测：QThread 生命周期、事件投递、配置校验、控制授权。

需要真实 QApplication 与插件线程；使用 QEventLoop + QTimer 等待状态迁移，
finally 里统一 shutdown() 清理，避免 pytest 挂死。
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from loguru import logger
from PySide6.QtCore import QCoreApplication, QEventLoop, QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget

from lib_zmq_plugins.shared.base import BaseCommand, BaseEvent
from plugin_manager.event_dispatcher import EventDispatcher
from plugin_sdk.control_auth import ControlAuthorizationManager
from plugin_sdk.plugin_base import BasePlugin, PluginInfo, PluginLifecycle
from plugin_sdk.service_registry import ServiceRegistry


# ── 局部 fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "plugin_manager.logging_setup.get_plugin_logger",
        lambda *args, **kwargs: (logger, None),
    )
    monkeypatch.setattr(
        "plugin_manager.logging_setup.set_plugin_log_level",
        lambda *args, **kwargs: None,
    )
    return instance


@pytest.fixture
def auth(monkeypatch, tmp_path):
    """隔离的 ControlAuthorizationManager 单例，避免读写真实 data 目录。"""
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)
    manager = ControlAuthorizationManager.instance(tmp_path)
    manager.clear_all()
    yield manager
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)


class CovTaggedCommand(BaseCommand, tag="__cov_tagged__"):
    value: int = 0


class CovTaggedEvent(BaseEvent, tag="__cov_event__"):
    value: int = 0


class LifecyclePlugin(BasePlugin):
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="cov-lifecycle", other_info=None)

    def __init__(self):
        super().__init__(self.plugin_info())
        self.init_calls = 0
        self.shutdown_calls = 0
        self.auth_changes = []
        self.subscriptions = []
        self.validation_result: dict | None = None
        self.validation_error: Exception | None = None
        self.init_error: Exception | None = None
        self.fail_setup = False

    def _setup_subscriptions(self):
        if self.fail_setup:
            raise RuntimeError("setup failed")
        self.subscriptions.append("setup")

    def _create_widget(self):
        return QWidget()

    def on_initialized(self):
        self.init_calls += 1
        if self.init_error:
            raise self.init_error

    def on_shutdown(self):
        self.shutdown_calls += 1

    def on_control_auth_changed(self, command_type, granted):
        self.auth_changes.append((command_type, granted))

    def validate_config(self, pending):
        if self.validation_error:
            raise self.validation_error
        return self.validation_result if self.validation_result is not None else {}


def wait_until(predicate, timeout_ms=3000):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    timer.start()
    deadline.start(timeout_ms)
    if not predicate():
        loop.exec()
    timer.stop()
    deadline.stop()
    assert predicate(), "plugin lifecycle transition timed out"


def drain_gui():
    from PySide6.QtCore import QEvent
    for _ in range(5):
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


# ── 线程启动 / 状态机 ─────────────────────────────────────────────────────

def test_initialize_starts_thread_and_reaches_ready(app):
    plugin = LifecyclePlugin()
    ready_seen = []
    plugin.ready.connect(lambda p: ready_seen.append(p))
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        assert plugin.lifecycle is PluginLifecycle.READY
        assert plugin.init_calls == 1
        assert plugin._thread.isRunning()
        assert plugin.subscriptions == ["setup"]
        assert plugin.widget is not None
        assert ready_seen == [plugin]
        assert threading.current_thread().name != "plugin-cov-lifecycle"
    finally:
        plugin.shutdown()
    assert plugin.lifecycle is PluginLifecycle.STOPPED


def test_initialize_ignored_when_already_initializing_or_thread_running(app):
    plugin = LifecyclePlugin()
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        # 第二次 initialize 在 READY 状态直接早退，不重复启动
        before = plugin.init_calls
        plugin.initialize()
        assert plugin.init_calls == before
        assert plugin._generation == 1

        # 手动把生命周期改回 NEW 但线程仍在运行 -> isRunning 早退
        plugin._lifecycle = PluginLifecycle.NEW
        plugin.initialize()
        assert plugin.init_calls == before
    finally:
        plugin.shutdown()


def test_initialize_failure_rolls_back_and_disables(app):
    plugin = LifecyclePlugin()
    plugin.fail_setup = True
    with pytest.raises(RuntimeError, match="setup failed"):
        plugin.initialize()
    assert not plugin.is_enabled
    assert plugin.lifecycle is PluginLifecycle.STOPPED
    assert not plugin._thread.isRunning()
    assert plugin.widget is None
    assert plugin.shutdown_calls == 1  # shutdown() 里 _do_shutdown 执行


def test_on_thread_started_returns_early_when_lifecycle_not_initializing(app):
    plugin = LifecyclePlugin()
    try:
        # 直接调用（非线程上下文）：把状态设成 STOPPED，使 READY 赋值分支跳过
        plugin._lifecycle = PluginLifecycle.STOPPED
        plugin._on_thread_started()
        assert plugin.init_calls == 1
        assert plugin.lifecycle is PluginLifecycle.STOPPED  # 未被改成 READY
    finally:
        plugin.shutdown()


def test_on_initialized_failure_triggers_error_path(app):
    plugin = LifecyclePlugin()
    plugin.init_error = RuntimeError("init boom")
    try:
        plugin.initialize()
        wait_until(lambda: plugin.lifecycle == PluginLifecycle.STOPPED)
        assert not plugin.is_enabled
        assert plugin.init_calls == 1
        assert plugin.widget is None
        assert plugin.shutdown_calls == 1
    finally:
        plugin.shutdown()


def test_on_initialized_failure_already_stopping_skips_do_shutdown(app):
    plugin = LifecyclePlugin()
    try:
        # 直接调用，模拟「已进入 SHUTTING_DOWN」时初始化失败：不重复 _do_shutdown
        plugin._lifecycle = PluginLifecycle.SHUTTING_DOWN
        plugin.init_error = RuntimeError("init boom while stopping")
        plugin._on_thread_started()
        assert plugin.lifecycle is PluginLifecycle.SHUTTING_DOWN
        assert plugin.shutdown_calls == 0
        assert not plugin.is_enabled
    finally:
        plugin._lifecycle = PluginLifecycle.NEW
        plugin.shutdown()


def test_shutdown_called_from_plugin_thread(app):
    plugin = LifecyclePlugin()
    result = {}
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)

        def call_shutdown_from_worker():
            result["lifecycle"] = plugin.shutdown()

        plugin._enqueue_event(lambda _: call_shutdown_from_worker(), None)
        wait_until(lambda: "lifecycle" in result)
        # 在插件线程调用 shutdown 走 QThread.currentThread()==_thread 分支
        wait_until(lambda: not plugin._thread.isRunning())
    finally:
        plugin.shutdown()
    assert plugin.shutdown_calls >= 1


def test_shutdown_timeout_branch_logs_warning(app):
    plugin = LifecyclePlugin()
    entered = threading.Event()
    release = threading.Event()

    def block(_):
        entered.set()
        release.wait(5)

    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        plugin._enqueue_event(block, None)
        assert entered.wait(3)
        # 让 _do_shutdown 排队在 block 之后，wait(2000) 超时 -> warning 分支
        import plugin_sdk.plugin_base as pb
        original_wait = plugin._thread.wait

        def fast_wait(_ms=2000):
            return False

        plugin._thread.wait = fast_wait  # type: ignore[method-assign]
        plugin.shutdown()
        assert plugin.lifecycle is PluginLifecycle.SHUTTING_DOWN
        assert plugin._thread.wait is fast_wait
        del pb, original_wait
    finally:
        release.set()
        plugin._thread.wait(3000)
        drain_gui()
        plugin.shutdown()


def test_shutdown_early_returns_when_stopped_or_shutting_down(app):
    plugin = LifecyclePlugin()
    try:
        plugin._lifecycle = PluginLifecycle.STOPPED
        plugin.shutdown()  # 早退，on_shutdown 不应执行
        assert plugin.shutdown_calls == 0
        plugin._lifecycle = PluginLifecycle.SHUTTING_DOWN
        plugin.shutdown()
        assert plugin.shutdown_calls == 0
    finally:
        plugin._lifecycle = PluginLifecycle.NEW
        plugin.shutdown()


def test_do_shutdown_survives_on_shutdown_exception(app):
    plugin = LifecyclePlugin()
    plugin.on_shutdown = lambda: (_ for _ in ()).throw(RuntimeError("cleanup boom"))
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
    finally:
        plugin.shutdown()  # 异常被记录，不应向外抛
    assert plugin.lifecycle is PluginLifecycle.STOPPED


def test_finish_shutdown_early_returns_when_not_shutting_down(app):
    plugin = LifecyclePlugin()
    stopped = []
    plugin.stopped.connect(lambda p: stopped.append(p))
    plugin._finish_shutdown()  # NEW 状态 -> 早退
    assert stopped == []
    plugin.shutdown()
    assert plugin.lifecycle is PluginLifecycle.STOPPED


def test_finish_shutdown_disconnects_auth_callback_and_saves_config(app, auth, monkeypatch):
    plugin = LifecyclePlugin()
    saved = []
    monkeypatch.setattr(plugin, "save_config", lambda: saved.append(True))
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        assert plugin._auth_changed_callback is not None
        callback = plugin._auth_changed_callback
        # 触发一次信号，确认回调确实已连接（本插件名+tag 不匹配，仅验证不抛）
        auth.authorization_changed.emit("unrelated", "other", True)
        assert callback is plugin._auth_changed_callback
    finally:
        plugin.shutdown()
    assert plugin._auth_changed_callback is None
    assert saved == [True]  # _finish_shutdown 调用了 save_config
    assert plugin.widget is None


def test_finish_shutdown_propagates_save_config_error_but_emits_stopped(app, monkeypatch):
    plugin = LifecyclePlugin()
    stopped = []
    # 插件 QObject 被 moveToThread 到尚未运行的线程；默认的队列连接会把
    # 发射投递到该线程且永不执行，故显式用 DirectConnection 同步观察。
    plugin.stopped.connect(lambda p: stopped.append(p),
                           Qt.ConnectionType.DirectConnection)
    monkeypatch.setattr(
        plugin, "save_config",
        lambda: (_ for _ in ()).throw(RuntimeError("save failed")),
    )
    with pytest.raises(RuntimeError, match="save failed"):
        plugin.shutdown()
    assert stopped == [plugin]  # finally 分支仍发射 stopped


# ── 事件投递 / 处理器 ─────────────────────────────────────────────────────

def test_handle_event_runs_handler_only_when_ready_and_enabled(app):
    plugin = LifecyclePlugin()
    seen = []
    plugin._handle_event(seen.append, "not-ready")
    assert seen == []  # NEW 状态跳过

    plugin._lifecycle = PluginLifecycle.READY
    plugin._info.enabled = False
    plugin._handle_event(seen.append, "disabled")
    assert seen == []

    plugin._info.enabled = True
    plugin._handle_event(seen.append, "ok")
    assert seen == ["ok"]

    plugin._handle_event(
        lambda _: (_ for _ in ()).throw(RuntimeError("handler boom")), "bad"
    )  # 异常被记录不外抛
    assert seen == ["ok"]


def test_enqueue_event_delivers_current_generation_and_drops_stale(app):
    plugin = LifecyclePlugin()
    received = []
    try:
        plugin._enqueue_event(received.append, "stale")  # generation=0
        plugin.initialize()  # generation -> 1
        wait_until(lambda: plugin.is_ready)
        assert plugin._enqueue_event(received.append, "current") is True
        wait_until(lambda: bool(received))
        assert received == ["current"]
    finally:
        plugin.shutdown()


def test_subscribe_and_unsubscribe_use_dispatcher(app):
    plugin = LifecyclePlugin()
    dispatcher = EventDispatcher()
    plugin.set_event_dispatcher(dispatcher)
    handler = lambda event: None
    plugin.subscribe(CovTaggedEvent, handler)
    entries = dispatcher.get_handlers(CovTaggedEvent.__struct_config__.tag)
    assert len(entries) == 1
    assert entries[0].handler is handler
    assert entries[0].priority == plugin.info.priority
    assert entries[0].plugin is plugin
    dispatcher.dispatch(CovTaggedEvent.__struct_config__.tag, CovTaggedEvent())
    plugin.unsubscribe(CovTaggedEvent)
    assert dispatcher.get_handlers(CovTaggedEvent.__struct_config__.tag) == []


def test_subscribe_noop_without_dispatcher(app):
    plugin = LifecyclePlugin()
    plugin.subscribe(CovTaggedEvent, lambda e: None)  # 不应抛
    plugin.unsubscribe(CovTaggedEvent)
    assert plugin._event_dispatcher is None


# ── run_validate_config ───────────────────────────────────────────────────

def test_run_validate_config_sync_when_thread_not_running(app):
    plugin = LifecyclePlugin()
    assert plugin.run_validate_config({"a": 1}) == {}
    plugin.validation_result = {"a": "bad"}
    assert plugin.run_validate_config({"a": 1}) == {"a": "bad"}

    # 非 dict 返回值归一为 {}
    plugin.validation_result = None
    plugin.validate_config = lambda pending: "not-a-dict"
    assert plugin.run_validate_config({}) == {}

    # 同步分支异常 -> {"_plugin": 文案}
    plugin.validate_config = lambda pending: (_ for _ in ()).throw(ValueError("sync err"))
    result = plugin.run_validate_config({})
    assert result == {"_plugin": "sync err"}


def test_run_validate_config_async_on_running_thread(app):
    plugin = LifecyclePlugin()
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        plugin.validation_result = {"field": "invalid"}
        assert plugin.run_validate_config({"field": 1}) == {"field": "invalid"}

        # 异步分支返回非 dict -> {}
        plugin.validation_result = None
        plugin.validate_config = lambda pending: 42
        assert plugin.run_validate_config({}) == {}

        # 异步分支异常（Future.set_exception）-> {"_plugin": ...}
        plugin.validation_error = RuntimeError("async err")
        plugin.validate_config = LifecyclePlugin.validate_config.__get__(plugin)
        result = plugin.run_validate_config({})
        assert result == {"_plugin": "async err"}
    finally:
        plugin.shutdown()


def test_run_validate_config_timeout_returns_plugin_error(app, monkeypatch):
    plugin = LifecyclePlugin()
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        # 阻断 _enqueue_event，让 _run 永不执行，future 必然超时；
        # 避免依赖「极小 timeout 与插件线程抢跑」的不稳定竞态。
        monkeypatch.setattr(plugin, "_enqueue_event",
                            lambda handler, event: True)
        result = plugin.run_validate_config({}, timeout=0.01)
        assert "_plugin" in result
    finally:
        plugin.shutdown()


# ── 控制授权信号 ─────────────────────────────────────────────────────────

def test_connect_control_auth_signal_is_idempotent(app, auth):
    plugin = LifecyclePlugin()
    plugin._connect_control_auth_signal()
    first = plugin._auth_changed_callback
    assert first is not None
    plugin._connect_control_auth_signal()  # 第二次直接早退
    assert plugin._auth_changed_callback is first
    plugin.shutdown()


def test_auth_changed_callback_dispatches_matching_command(app, auth, monkeypatch):
    plugin = LifecyclePlugin()
    plugin._connect_control_auth_signal()
    callback = plugin._auth_changed_callback

    # 与本插件无关 -> 早退
    callback("tag", "other-plugin", True)
    assert plugin.auth_changes == []

    monkeypatch.setattr(
        auth, "get_all_control_types", lambda: [CovTaggedCommand, int]
    )
    monkeypatch.setattr(auth, "_get_tag", lambda cmd: "tag-A" if cmd is CovTaggedCommand else "tag-B")
    callback("tag-A", plugin.name, True)
    drain_gui()
    assert plugin.auth_changes == [(CovTaggedCommand, True)]

    # 未匹配 tag -> 不调用回调
    callback("unknown", plugin.name, False)
    drain_gui()
    assert plugin.auth_changes == [(CovTaggedCommand, True)]
    plugin.shutdown()


def test_auth_changed_callback_skips_types_without_tag(app, auth, monkeypatch):
    plugin = LifecyclePlugin()
    plugin._connect_control_auth_signal()
    callback = plugin._auth_changed_callback

    def raising_tag(cmd):
        if cmd is int:
            raise ValueError("no tag")
        return "tag-A"

    monkeypatch.setattr(auth, "get_all_control_types", lambda: [int, CovTaggedCommand])
    monkeypatch.setattr(auth, "_get_tag", raising_tag)
    callback("tag-A", plugin.name, False)
    drain_gui()
    assert plugin.auth_changes == [(CovTaggedCommand, False)]
    plugin.shutdown()


def test_has_control_auth_delegates_to_manager(app, auth, monkeypatch):
    plugin = LifecyclePlugin()
    calls = []
    monkeypatch.setattr(
        auth, "is_authorized",
        lambda cmd, name: calls.append((cmd, name)) or True,
    )
    assert plugin.has_control_auth(CovTaggedCommand) is True
    assert calls == [(CovTaggedCommand, plugin.name)]


# ── 权限检查 / 指令发送 ───────────────────────────────────────────────────

def test_check_control_auth_non_struct_and_missing_tag(app, auth):
    plugin = LifecyclePlugin()
    # 非结构化命令 -> 允许
    assert plugin._check_control_auth(object()) is True
    # 有 __struct_config__ 但无 tag -> 允许
    assert plugin._check_control_auth(SimpleNamespace(__struct_config__=object())) is True


def test_check_control_auth_granted_and_denied(app, auth, monkeypatch):
    plugin = LifecyclePlugin()
    # 真实 tag 路径：授权给本插件 -> True
    auth.authorize(CovTaggedCommand, plugin.name)
    assert plugin._check_control_auth(CovTaggedCommand()) is True

    # 授权给别的插件 -> False
    auth.authorize(CovTaggedCommand, "someone-else")
    assert plugin._check_control_auth(CovTaggedCommand()) is False

    # monkeypatch 验证 get_authorized_plugin 被调用（覆盖日志语句）
    seen = []
    monkeypatch.setattr(
        auth, "get_authorized_plugin",
        lambda cmd: seen.append(cmd) or "x",
    )
    assert plugin._check_control_auth(CovTaggedCommand()) is False
    assert seen == [CovTaggedCommand]


class _FakeClient:
    def __init__(self):
        self.commands = []
        self.requests = []
        self.queries = []
        self.raise_on_send = False

    def send_command(self, command):
        self.commands.append(command)
        if self.raise_on_send:
            raise RuntimeError("send failed")

    def request(self, command, timeout):
        self.requests.append((command, timeout))
        return "response"

    def query(self, query, timeout):
        self.queries.append((query, timeout))
        return "query-result"


def test_send_command_all_branches(app, auth):
    plugin = LifecyclePlugin()
    # 无 client + 允许发送 -> 走 "client 未初始化" 分支
    plugin.send_command(object())
    plugin.send_command(CovTaggedCommand())  # 未授权 -> 提前返回

    client = _FakeClient()
    plugin.set_client(client)
    # 结构化未授权 -> 不发送
    plugin.send_command(CovTaggedCommand())
    assert client.commands == []

    # 非结构化命令（绕过授权）-> 真正发送
    raw = object()
    plugin.send_command(raw)
    assert client.commands == [raw]

    # 发送抛异常 -> 被记录不外抛
    client.raise_on_send = True
    plugin.send_command(object())
    assert len(client.commands) == 2


def test_request_and_query_all_branches(app, auth):
    plugin = LifecyclePlugin()
    auth.authorize(CovTaggedCommand, plugin.name)

    # 无 client
    assert plugin.request(CovTaggedCommand(), timeout=1.0) is None
    assert plugin.query("q", timeout=1.0) is None

    client = _FakeClient()
    plugin.set_client(client)
    cmd = CovTaggedCommand()
    assert plugin.request(cmd, timeout=2.5) == "response"
    assert client.requests == [(cmd, 2.5)]
    assert plugin.query("q2", timeout=3.5) == "query-result"
    assert client.queries == [("q2", 3.5)]

    # 授权被撤销：request 返回 None，且不再访问 client
    auth.revoke(CovTaggedCommand)
    assert plugin.request(CovTaggedCommand()) is None
    assert len(client.requests) == 1
    # query 不走授权，仍可用
    assert plugin.query("q3") == "query-result"
    assert len(client.queries) == 2


# ── enable / disable / _unsubscribe_resources ────────────────────────────

def test_enable_disable_cycle(app):
    plugin = LifecyclePlugin()
    try:
        plugin.disable()
        assert not plugin.is_enabled
        assert plugin.lifecycle is PluginLifecycle.STOPPED
        assert plugin.shutdown_calls == 1  # NEW -> shutdown -> _do_shutdown

        plugin.enable()
        assert plugin.is_enabled
        wait_until(lambda: plugin.is_ready)
        assert plugin._thread.isRunning()
        plugin.disable()
        assert plugin.lifecycle is PluginLifecycle.STOPPED
        assert plugin.widget is None
    finally:
        plugin.shutdown()


def test_enable_early_returns_while_shutting_down(app):
    plugin = LifecyclePlugin()
    try:
        plugin.info.enabled = False
        plugin._lifecycle = PluginLifecycle.SHUTTING_DOWN
        plugin.enable()
        assert not plugin.is_enabled  # 未翻转
        assert plugin.init_calls == 0
    finally:
        plugin._lifecycle = PluginLifecycle.NEW
        plugin.shutdown()


def test_disable_noop_when_already_stopped(app):
    plugin = LifecyclePlugin()
    try:
        plugin._lifecycle = PluginLifecycle.STOPPED
        plugin.disable()
        assert plugin.shutdown_calls == 0
    finally:
        plugin._lifecycle = PluginLifecycle.NEW
        plugin.shutdown()


def test_unsubscribe_resources_handles_registered_services(app):
    plugin = LifecyclePlugin()
    dispatcher = EventDispatcher()
    plugin.set_event_dispatcher(dispatcher)
    dispatcher.subscribe("evt", lambda e: None, plugin=plugin)

    class ProtoA:
        pass

    class ProtoB:
        pass

    plugin._registered_protocols = [ProtoA, ProtoB]
    dispatcher.services.register(ProtoA, object(), plugin.name)
    # ProtoB 未注册，unregister 返回 False 也不抛
    plugin._unsubscribe_resources()
    assert dispatcher.get_handlers("evt") == []
    assert plugin._registered_protocols == []
    assert not dispatcher.services.has(ProtoA)

    # 让 unregister 抛异常 -> except 分支记录日志
    plugin._registered_protocols = [ProtoB]
    dispatcher.services.register(ProtoB, object(), plugin.name)
    original = dispatcher.services.unregister

    def raising(protocol):
        raise RuntimeError("unregister boom")

    dispatcher.services.unregister = raising  # type: ignore[method-assign]
    plugin._unsubscribe_resources()
    assert plugin._registered_protocols == []
    dispatcher.services.unregister = original
    dispatcher.services.unregister(ProtoB)


def test_unsubscribe_resources_noop_without_dispatcher(app):
    plugin = LifecyclePlugin()
    plugin._registered_protocols = [object]
    plugin._unsubscribe_resources()
    assert plugin._registered_protocols == [object]  # dispatcher 为 None 时不动
