"""Deterministic synchronous coverage of lifecycle and validation edge cases."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from plugin_sdk.plugin_base import BasePlugin, PluginInfo, PluginLifecycle


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr("plugin_manager.logging_setup.get_plugin_logger", lambda *a, **k: (logger, None))
    monkeypatch.setattr("plugin_manager.logging_setup.set_plugin_log_level", lambda *a, **k: None)
    return application


class EdgePlugin(BasePlugin):
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="edge-probe", other_info=None)

    def _setup_subscriptions(self):
        pass


@pytest.fixture
def plugin(app):
    return EdgePlugin(EdgePlugin.plugin_info())


def test_config_path_delegates_and_base_subscription_hook(plugin, tmp_path):
    from plugin_manager.config_manager import PluginConfigManager
    from plugin_sdk.config_types import OtherInfoBase

    manager = PluginConfigManager(tmp_path)
    plugin._config_manager = manager
    expected = tmp_path / "edge-probe" / "config.json"
    assert plugin.config_file_path == expected
    manager.save(plugin.name, OtherInfoBase())
    assert expected.is_file()
    assert BasePlugin._setup_subscriptions(plugin) is None


def test_initialization_failure_unsubscribes_and_stops(plugin, monkeypatch):
    original_name = threading.current_thread().name
    unsubscribe = Mock()
    stop = Mock()
    monkeypatch.setattr(plugin, "on_initialized", Mock(side_effect=ValueError("init failure")))
    monkeypatch.setattr(plugin, "_unsubscribe_resources", unsubscribe)
    monkeypatch.setattr(plugin, "_do_shutdown", stop)
    plugin._lifecycle = PluginLifecycle.INITIALIZING
    try:
        plugin._on_thread_started()
    finally:
        threading.current_thread().name = original_name
    assert plugin.lifecycle is PluginLifecycle.SHUTTING_DOWN
    assert not plugin.is_enabled
    unsubscribe.assert_called_once_with()
    stop.assert_called_once_with()


def test_initialization_marks_ready_and_emits_signal(plugin):
    original_name = threading.current_thread().name
    ready = []
    plugin.ready.connect(ready.append, Qt.ConnectionType.DirectConnection)
    plugin._lifecycle = PluginLifecycle.INITIALIZING
    try:
        plugin._on_thread_started()
    finally:
        threading.current_thread().name = original_name
    assert plugin.is_ready
    assert ready == [plugin]
    plugin.shutdown()
    assert plugin.lifecycle is PluginLifecycle.STOPPED


def test_shutdown_in_own_thread_queues_cleanup_without_waiting(plugin, monkeypatch):
    from plugin_sdk import plugin_base
    stop = Mock()
    monkeypatch.setattr(plugin._thread, "isRunning", lambda: True)
    monkeypatch.setattr(plugin_base.QThread, "currentThread", lambda: plugin._thread)
    monkeypatch.setattr(plugin, "_do_shutdown", stop)
    plugin.shutdown()
    stop.assert_not_called()
    assert plugin.lifecycle is PluginLifecycle.SHUTTING_DOWN


def test_shutdown_hook_exception_does_not_escape(plugin, monkeypatch):
    stop = Mock()
    monkeypatch.setattr(plugin, "on_shutdown", Mock(side_effect=ValueError("cleanup failure")))
    monkeypatch.setattr(plugin._thread, "quit", stop)
    plugin._do_shutdown()
    stop.assert_called_once_with()


def test_event_delivery_checks_generation(plugin):
    handlers = []
    plugin._event_dispatch.connect(lambda callback, event: handlers.append((callback, event)),
                                   Qt.ConnectionType.DirectConnection)
    received = []
    assert plugin._enqueue_event(received.append, "fresh") is True
    callback, event = handlers.pop()
    callback(event)
    assert received == ["fresh"]
    plugin._enqueue_event(received.append, "stale")
    callback, event = handlers.pop()
    plugin._generation += 1
    callback(event)
    assert received == ["fresh"]


def test_validation_queued_callback_success_and_failure(plugin, monkeypatch):
    monkeypatch.setattr(plugin._thread, "isRunning", lambda: True)
    enqueue = Mock(side_effect=lambda handler, event: handler(event))
    monkeypatch.setattr(plugin, "_enqueue_event", enqueue)
    validate = Mock(return_value={"field": "invalid"})
    monkeypatch.setattr(plugin, "validate_config", validate)
    assert plugin.run_validate_config({"field": 2}, timeout=0.1) == {"field": "invalid"}
    validate.assert_called_once_with({"field": 2})
    validate.return_value = "invalid type"
    assert plugin.run_validate_config({}, timeout=0.1) == {}
    validate.side_effect = ValueError("invalid configuration")
    assert plugin.run_validate_config({}, timeout=0.1) == {"_plugin": "invalid configuration"}
    assert enqueue.call_count == 3
    assert all(call.args[1] is None for call in enqueue.call_args_list)


def test_shutdown_timeout_retains_stopping_state(plugin, monkeypatch):
    monkeypatch.setattr(plugin._thread, "isRunning", lambda: True)
    wait = Mock(return_value=False)
    monkeypatch.setattr(plugin._thread, "wait", wait)
    plugin.shutdown()
    wait.assert_called_once_with(2000)
    assert plugin.lifecycle is PluginLifecycle.SHUTTING_DOWN


def test_validation_rejected_when_plugin_is_stopping(plugin, monkeypatch):
    """_enqueue_event 返回 False（插件正在停止）时应直接返回错误，不等待 Future。"""
    monkeypatch.setattr(plugin._thread, "isRunning", lambda: True)
    monkeypatch.setattr(plugin, "_enqueue_event", lambda handler, event: False)
    validate = Mock()
    monkeypatch.setattr(plugin, "validate_config", validate)
    result = plugin.run_validate_config({"field": 1}, timeout=5.0)
    assert result == {"_plugin": "Plugin is stopping: edge-probe"}
    validate.assert_not_called()
