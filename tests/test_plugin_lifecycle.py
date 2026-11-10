"""插件生命周期回归测试；不连接游戏进程或真实 ZMQ。"""
import threading

import pytest
from loguru import logger
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from plugin_manager.event_dispatcher import EventDispatcher
from plugin_manager.plugin_state import PluginState, PluginStateManager
from plugin_manager.plugin_manager import PluginManager
from plugin_sdk.plugin_base import BasePlugin, PluginInfo, PluginLifecycle


def wait_until(predicate):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    timer.start()
    deadline.start(3000)
    if not predicate():
        loop.exec()
    timer.stop()
    deadline.stop()
    assert predicate(), "plugin lifecycle transition timed out"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "plugin_manager.logging_setup.get_plugin_logger",
        lambda *args, **kwargs: (logger, None),
    )
    return instance


class ProbePlugin(BasePlugin):
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="lifecycle-probe", other_info=None)

    def __init__(self):
        super().__init__(self.plugin_info())
        self.fail = False
        self.cleanups = 0
        self.set_event_dispatcher(EventDispatcher())

    def _setup_subscriptions(self):
        self._event_dispatcher.subscribe("probe", lambda event: None, plugin=self)

    def _create_widget(self):
        return QWidget()

    def on_initialized(self):
        if self.fail:
            raise RuntimeError("intentional initialization failure")

    def on_shutdown(self):
        self.cleanups += 1


def test_gui_dispatch_survives_disable_and_enable(app):
    plugin = ProbePlugin()
    calls = []
    try:
        for _ in range(2):
            plugin.enable()
            wait_until(lambda: plugin.is_ready)
            plugin.run_on_gui(calls.append, plugin.widget)
            wait_until(lambda: len(calls) == plugin.cleanups + 1)
            plugin.disable()
            assert plugin.lifecycle == PluginLifecycle.STOPPED
            assert plugin.widget is None
        assert plugin.cleanups == 2
    finally:
        plugin.shutdown()


def test_failed_initialization_rolls_back_and_can_retry(app):
    plugin = ProbePlugin()
    plugin.fail = True
    try:
        plugin.initialize()
        wait_until(lambda: plugin.lifecycle == PluginLifecycle.STOPPED)
        assert not plugin.is_enabled
        assert not plugin._thread.isRunning()
        assert plugin.widget is None
        assert not plugin._event_dispatcher.get_handlers("probe")
        assert plugin.cleanups == 1
        plugin.fail = False
        plugin.enable()
        wait_until(lambda: plugin.is_ready)
    finally:
        plugin.shutdown()


def test_tab_close_destroys_widget_and_reopen_creates_new_widget(app):
    from plugin_manager.main_window import DetachableTabWidget

    plugin = ProbePlugin()
    tabs = DetachableTabWidget()
    destroyed = []
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        old_widget = plugin.widget
        old_widget.destroyed.connect(lambda: destroyed.append(True))
        tabs.add_detachable_tab(old_widget, plugin.name)
        tabs.tabCloseRequested.emit(0)
        tabs.tab_close_requested.connect(plugin.close_widget)
        # 模拟管理器接线后的第二次关闭，验证延迟删除已完成。
        plugin.close_widget()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert tabs.count() == 0
        assert plugin.widget is None
        assert plugin.is_ready and plugin._thread.isRunning()
        assert destroyed == [True]

        plugin.run_on_widget(lambda widget: destroyed.append("stale"))
        QCoreApplication.processEvents()
        assert destroyed == [True]

        reopened = plugin.ensure_widget()
        assert reopened is not None and reopened is not old_widget
        assert plugin.widget is reopened
        assert plugin.cleanups == 0
        assert plugin.is_ready and plugin._thread.isRunning()
        plugin.run_on_widget(lambda widget: destroyed.append(widget))
        QCoreApplication.processEvents()
        assert destroyed[-1] is reopened
    finally:
        plugin.shutdown()
        tabs.deleteLater()


def test_widget_signal_reconnect_survives_close_reopen_cycles(app):
    from PySide6.QtCore import QObject, Signal

    class Sender(QObject):
        updated = Signal(int)

    sender = Sender()
    received = []

    class View(QWidget):
        def __init__(self):
            super().__init__()
            sender.updated.connect(self.record)

        def record(self, value):
            received.append((self, value))

    widgets = []
    try:
        for cycle in range(3):
            widget = View()
            widgets.append(widget)
            sender.updated.emit(cycle)
            QCoreApplication.processEvents()
            assert [value for _, value in received] == list(range(cycle + 1))
            widget.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert sender.receivers("updated(int)") == 0
    finally:
        import shiboken6
        for widget in widgets:
            if shiboken6.isValid(widget):
                widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_previous_generation_events_do_not_run_after_restart(app):
    plugin = ProbePlugin()
    received = []
    plugin._enqueue_event(received.append, "stale")
    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        plugin._enqueue_event(received.append, "current")
        wait_until(lambda: bool(received))
        assert received == ["current"]
    finally:
        plugin.shutdown()


def test_blocked_callback_does_not_prevent_shutdown_timeout(app):
    plugin = ProbePlugin()
    entered = threading.Event()
    release = threading.Event()

    def block(event):
        entered.set()
        release.wait(10)

    try:
        plugin.initialize()
        wait_until(lambda: plugin.is_ready)
        plugin._enqueue_event(block, None)
        assert entered.wait(3)
        plugin.disable()
        assert plugin.lifecycle == PluginLifecycle.SHUTTING_DOWN
        assert plugin._thread.isRunning()
        plugin.enable()
        assert not plugin.is_enabled
        release.set()
        wait_until(lambda: plugin.lifecycle == PluginLifecycle.STOPPED)
        assert plugin.cleanups == 1
        assert plugin.widget is None
    finally:
        release.set()
        plugin._thread.wait(3000)
        QCoreApplication.processEvents()
        plugin.shutdown()


@pytest.mark.parametrize("saved_enabled", [False, True])
def test_saved_state_applies_before_initialization(app, tmp_path, monkeypatch, saved_enabled):
    plugin = ProbePlugin()
    plugin.info.enabled = not saved_enabled
    monkeypatch.setattr(plugin, "set_log_level", lambda level: None)
    manager = PluginManager.__new__(PluginManager)
    manager._plugins = {plugin.name: plugin}
    manager.state_manager = PluginStateManager(tmp_path / "states.json")
    manager.state_manager.set(plugin.name, PluginState(enabled=saved_enabled))
    manager._apply_saved_plugin_states()
    assert plugin.is_enabled == saved_enabled
    assert plugin.lifecycle == PluginLifecycle.NEW
    assert plugin.widget is None
    assert not plugin._thread.isRunning()