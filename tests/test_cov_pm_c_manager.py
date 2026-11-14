"""Coverage tests for PluginManager lifecycle, events, state and GUI helpers."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from plugin_manager import plugin_manager as module
from plugin_manager.plugin_state import PluginState, PluginStateManager
from shared_types.events import (
    GameFinishedEvent,
    LanguageChangeEvent,
    ShowPluginManagerEvent,
)

from test_cov_pm_c_fakes import (  # noqa: F401  (fixtures and constants)
    APPLY_SAVED_STATES,
    INITIALIZE_PLUGINS,
    SHUTDOWN_PLUGINS,
    SHUTDOWN_REGISTRATION,
    VALIDATE_AUTHORIZATIONS,
    FakeAuthManager,
    FakeClient,
    FakePlugin,
    FakeWindow,
    base_env,
    manager,
    queue_event,
)


def test_init_all_params_and_properties(manager):
    assert manager.client.kwargs["endpoint"] == "inproc://coverage"
    assert manager.client.kwargs["pub_endpoint"] == "tcp://pub"
    assert manager.client.kwargs["ctrl_endpoint"] == "tcp://ctrl"
    assert manager.client.kwargs["log_handler"] is manager._log
    assert manager.client.kwargs["on_connected"].__self__ is manager
    assert manager.client.kwargs["on_disconnected"].__self__ is manager
    assert [r[0] for r in manager.client.registrations] == [
        "events", "commands", "queries"]
    assert manager.dispatcher is manager._dispatcher
    assert manager.plugins == {}
    assert manager.main_window is None
    assert manager.is_connected is True
    assert manager.reconnect_count == 7
    assert manager.connection_endpoint == "inproc://coverage"
    assert repr(manager) == "<PluginManager: 0 plugins, started=False>"
    assert module.PluginManager._instance is manager


def test_init_default_plugin_dirs_and_no_optional_params(base_env, tmp_path):
    assert module.get_all_plugin_dirs() == [tmp_path / "plugins"]
    instance = module.PluginManager("inproc://defaults")
    assert instance.client.kwargs["pub_endpoint"] is None
    assert instance.client.kwargs["ctrl_endpoint"] is None
    assert instance.client.kwargs["log_handler"] is None
    assert instance._loader._plugin_dirs == []
    instance.stop()


def test_register_shutdown_handlers_win32_simple_path(base_env, monkeypatch):
    registered = []
    monkeypatch.setattr(module.signal, "signal",
                        lambda signum, handler: registered.append((signum, handler)))
    exits = []
    monkeypatch.setattr(module.atexit, "register",
                        lambda callback: exits.append(callback))
    monkeypatch.setattr(module, "threading", SimpleNamespace(
        RLock=threading.RLock, Lock=threading.Lock,
        Thread=lambda **kwargs: pytest.fail("win32 must not start watchdog"),
    ))
    instance = module.PluginManager.__new__(module.PluginManager)
    instance._graceful_shutdown = lambda: registered.append("shutdown")

    SHUTDOWN_REGISTRATION(instance)

    assert [signum for signum, _ in registered[:2]] == [
        module.signal.SIGTERM, module.signal.SIGINT]
    assert len(exits) == 1 and exits[0] == instance._graceful_shutdown
    handler = registered[0][1]
    handler(int(module.signal.SIGTERM), None)
    assert registered[2] == "shutdown"


def test_register_shutdown_handlers_non_win32_watchdog(base_env, monkeypatch):
    monkeypatch.setattr(module.sys, "platform", "linux")
    handlers = []
    monkeypatch.setattr(module.signal, "signal",
                        lambda signum, handler: handlers.append((signum, handler)))
    monkeypatch.setattr(module.atexit, "register", lambda callback: None)
    piped = []
    monkeypatch.setattr(module.os, "pipe", lambda: (11, 12))
    monkeypatch.setattr(module.os, "set_blocking",
                        lambda fd, blocking: piped.append(("blocking", fd, blocking)))
    monkeypatch.setattr(module.signal, "set_wakeup_fd",
                        lambda fd: piped.append(("wakeup", fd)))
    exits = []
    monkeypatch.setattr(module.os, "_exit", lambda code: exits.append(code))
    reads = []
    targets = []

    class FakeThread:
        def __init__(self, target, name, daemon):
            assert name == "SignalWatchdog" and daemon is True
            targets.append(target)

        def start(self):
            pass

    monkeypatch.setattr(module, "threading", SimpleNamespace(
        RLock=threading.RLock, Lock=threading.Lock, Thread=FakeThread,
    ))
    monkeypatch.setattr(module.os, "read",
                        lambda fd, count: reads.append((fd, count)) or b"\x00")
    instance = module.PluginManager.__new__(module.PluginManager)
    shutdowns = []
    instance._graceful_shutdown = lambda: shutdowns.append(True)

    SHUTDOWN_REGISTRATION(instance)

    assert piped == [("blocking", 12, False), ("wakeup", 12)]
    assert len(handlers) == 2
    handle_signal = handlers[0][1]
    handle_signal(int(module.signal.SIGINT), None)
    assert shutdowns == [True]
    assert exits == [0]
    watchdog = targets[0]
    watchdog()
    assert reads == [(11, 1)]
    assert shutdowns == [True, True]
    assert exits == [0, 0]

    monkeypatch.setattr(module.os, "read",
                        lambda fd, count: (_ for _ in ()).throw(OSError("closed")))
    exits.clear()
    shutdowns.clear()
    watchdog()
    assert shutdowns == [] and exits == []


def test_graceful_shutdown_clears_events_and_handles_failures(manager):
    plugin = FakePlugin(raise_on_shutdown=True)
    manager._plugins["probe"] = plugin
    manager.client.fail_disconnect = True
    event = GameFinishedEvent()
    manager._queue_zmq_event("game_finished", event)
    manager._started = True

    manager.stop()

    assert manager._shutdown_requested
    assert manager._events_ready is False
    assert not manager._pending_events
    assert manager._started is False
    assert plugin.shutdown_calls == 1
    assert manager.client.disconnects == 1
    manager.stop()
    assert plugin.shutdown_calls == 1
    assert manager.client.disconnects == 1
    with pytest.raises(RuntimeError, match="Cannot restart"):
        manager.start()


def test_start_normal_and_already_started(manager):
    manager.start()
    assert manager._started is True
    assert manager._starting is False
    assert manager._events_ready is True
    assert manager.client.connected is True
    assert len(manager.client.subscriptions) == len(module.EVENT_TYPES)
    assert manager.client.handlers[GameFinishedEvent]
    manager.start()
    assert manager.client.disconnects == 0


def test_start_when_shutdown_requested_during_each_stage(manager, monkeypatch):
    for stage in ("_load_plugins", "connect", "_initialize_plugins"):
        instance = module.PluginManager("inproc://stage", plugin_dirs=[])
        instance._loader.load_all = lambda: []
        target = instance.client if stage == "connect" else instance
        monkeypatch.setattr(target, stage, instance.stop)
        instance.start()
        assert not instance._started
        assert not instance._starting
        assert instance._shutdown_requested
        instance._events_lock = threading.Lock()


def test_start_returns_when_shutdown_requested_after_validation(manager, monkeypatch):
    monkeypatch.setattr(manager, "_validate_control_authorizations", manager.stop)
    manager.start()
    assert not instance_started(manager)
    assert manager._shutdown_requested


def instance_started(instance):
    return instance._started


def test_start_after_release_startup_events_shutdown(manager, monkeypatch):
    def release():
        manager._shutdown_requested = True
        original_release()

    original_release = manager._release_startup_events
    monkeypatch.setattr(manager, "_release_startup_events", release)
    manager.start()
    assert not manager._started


def test_start_failure_closes_and_reraises(manager, monkeypatch):
    def fail():
        raise RuntimeError("boom")

    monkeypatch.setattr(manager._loader, "load_all", fail)
    with pytest.raises(RuntimeError, match="boom"):
        manager.start()
    assert manager._shutdown_requested
    assert not manager._starting
    assert manager.client.disconnects == 1


def test_validate_control_authorizations(manager, monkeypatch, tmp_path):
    fake = FakeAuthManager(removed=[("control.tag", "old-plugin")])
    monkeypatch.setattr("plugin_sdk.control_auth.ControlAuthorizationManager",
                        SimpleNamespace(instance=lambda: fake))
    manager._plugins["probe"] = FakePlugin()
    VALIDATE_AUTHORIZATIONS(manager)
    assert fake.loaded == {"probe"}
    assert fake.saves == 1

    fake.removed = []
    VALIDATE_AUTHORIZATIONS(manager)
    assert fake.saves == 2


def test_stop_is_graceful_shutdown(manager):
    manager.stop()
    assert manager._shutdown_requested


def test_start_with_gui_uses_existing_app_and_falls_back_to_action_icon(
        manager, monkeypatch, qapp):
    from PySide6.QtGui import QIcon

    class NullIcon:
        def isNull(self):
            return True

    monkeypatch.setattr("PySide6.QtGui.QIcon", lambda path: NullIcon())
    icons = []
    monkeypatch.setattr("plugin_manager.icons.action_icon",
                        lambda name: icons.append(name) or QIcon())
    windows = []
    monkeypatch.setattr("plugin_manager.main_window.PluginManagerWindow",
                        lambda pm: windows.append(FakeWindow(pm)) or windows[-1])
    monkeypatch.setattr(manager, "start", lambda: None)
    old_icon = qapp.windowIcon()
    manager.start_with_gui(qapp, show_main_window=True)
    assert manager._app is qapp
    assert icons == ["app"]
    assert manager.main_window.title == "插件管理器 - inproc://coverage"
    assert manager.main_window.shown == 1
    qapp.setWindowIcon(old_icon)


def test_start_with_gui_creates_app_and_hides_window(manager, monkeypatch, qapp):
    windows = []
    monkeypatch.setattr("plugin_manager.main_window.PluginManagerWindow",
                        lambda pm: windows.append(FakeWindow(pm)) or windows[-1])
    monkeypatch.setattr(manager, "start", lambda: None)
    manager.start_with_gui(show_main_window=False)
    assert manager._app is qapp
    assert manager.main_window.shown == 0
    assert not qapp.windowIcon().isNull()
    qapp.setWindowIcon(qapp.windowIcon().__class__())


def test_start_with_gui_creates_qapp_when_none(manager, monkeypatch, qapp):
    created = []

    class FakeQApplication:
        @staticmethod
        def instance():
            return None

        def __init__(self, args):
            created.append(args)
            self.args = args

        def setWindowIcon(self, icon):
            pass

    monkeypatch.setattr("PySide6.QtWidgets.QApplication", FakeQApplication)
    monkeypatch.setattr("plugin_manager.main_window.PluginManagerWindow",
                        lambda pm: FakeWindow(pm))
    monkeypatch.setattr(manager, "start", lambda: None)
    manager.start_with_gui(show_main_window=False)
    assert created == [[]]


def test_exec_gui_starts_when_needed_and_returns_result(manager, monkeypatch, qapp):
    calls = []
    monkeypatch.setattr(manager, "start_with_gui",
                        lambda *, show_main_window: (
                            calls.append(show_main_window),
                            setattr(manager, "_app", qapp),
                        ))
    monkeypatch.setattr(qapp, "exec", lambda: 42)
    monkeypatch.setattr(manager, "stop", lambda: calls.append("stop"))
    manager._app = None
    assert manager.exec_gui(show_main_window=False) == 42
    assert calls == [False, "stop"]


def test_exec_gui_uses_existing_app(manager, monkeypatch, qapp):
    manager._app = qapp
    monkeypatch.setattr(qapp, "exec", lambda: 0)
    stops = []
    monkeypatch.setattr(manager, "stop", lambda: stops.append(True))
    monkeypatch.setattr(manager, "start_with_gui",
                        lambda **kwargs: pytest.fail("must not start twice"))
    assert manager.exec_gui(show_main_window=True) == 0
    assert stops == [True]


def test_install_translator_creates_installer_when_needed(manager, monkeypatch):
    calls = []
    monkeypatch.setattr(module, "_TranslatorInstaller", lambda: SimpleNamespace(
        install=lambda language: calls.append(language),
    ))
    manager._translator_installer = None
    manager._install_translator("de_DE")
    assert calls == ["de_DE"]
    manager._install_translator("zh_CN")
    assert calls == ["de_DE", "zh_CN"]


def test_translator_installer_install_and_idle(qapp, qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QTranslator

    monkeypatch.setattr(module, "get_bundle_dir", lambda: tmp_path)
    (tmp_path / "de_DE.qm").write_bytes(b"fake-translation")
    (tmp_path / "ja_JP.qm").write_bytes(b"fake-translation")
    installer = module._TranslatorInstaller()
    loaded = []
    installed = []
    monkeypatch.setattr(QTranslator, "load",
                        lambda self, path: loaded.append(path) or True)
    monkeypatch.setattr(QCoreApplication, "installTranslator",
                        lambda self, translator: installed.append(translator) or True)
    monkeypatch.setattr(QCoreApplication, "removeTranslator",
                        lambda self, translator: installed.append("removed") or True)

    installer.install("zh_CN")
    qtbot.waitUntil(lambda: installer._translator is None, timeout=500)
    installer.install("de_DE")
    qtbot.waitUntil(lambda: len(installed) == 1, timeout=500)
    assert loaded == [str(tmp_path / "de_DE.qm")]
    installer.install("ja_JP")
    qtbot.waitUntil(lambda: len(installed) == 3, timeout=500)
    assert installed[1] == "removed"
    installer.install("missing_language")
    qtbot.waitUntil(lambda: installer._translator is None, timeout=500)
    installer.deleteLater()


def test_translator_installer_without_app(monkeypatch, qapp):
    installer = module._TranslatorInstaller()
    monkeypatch.setattr("PySide6.QtCore.QCoreApplication.instance", lambda: None)
    assert installer._install("de_DE") is None
    installer.deleteLater()


def test_log_handler_forwards_all_levels(monkeypatch):
    calls = []
    handler = module._LogHandler()
    for name in ("debug", "info", "warning", "error", "critical"):
        monkeypatch.setattr(module.logger, name,
                            lambda msg, *a, **k: calls.append((msg, a, k)))
        getattr(handler, name)("message", 1, extra="value")
    assert calls == [("message", (1,), {"extra": "value"})] * 5


def test_log_handler_supports_positional_only_messages(monkeypatch):
    calls = []
    handler = module._LogHandler()
    for name in ("debug", "info", "warning", "error", "critical"):
        monkeypatch.setattr(module.logger, name,
                            lambda *args, **kwargs: calls.append((args, kwargs)))
        getattr(handler, name)("direct")
    assert calls == [(("direct",), {})] * 5


def test_setup_zmq_subscriptions_queues_all_event_types(manager):
    from lib_zmq_plugins.shared.base import get_event_tag

    manager._setup_zmq_subscriptions()
    assert len(manager.client.subscriptions) == len(module.EVENT_TYPES)
    event = GameFinishedEvent()
    manager.client.emit(event)
    assert list(manager._pending_events) == [(get_event_tag(GameFinishedEvent), event)]
    assert not manager._events_draining


def test_queue_release_and_drain_dispatcher(manager, monkeypatch):
    from lib_zmq_plugins.shared.base import get_event_tag

    received = []
    monkeypatch.setattr(manager.dispatcher, "dispatch",
                        lambda tag, event: received.append((tag, event)))
    first, second = GameFinishedEvent(), GameFinishedEvent()
    queue_event(manager, first)
    manager._release_startup_events()
    assert received == [(get_event_tag(GameFinishedEvent), first)]
    queue_event(manager, second)
    assert received[-1] == (get_event_tag(GameFinishedEvent), second)
    assert not manager._events_draining


def test_queue_when_draining_and_shutdown_are_noops(manager):
    manager._events_draining = True
    queue_event(manager, GameFinishedEvent())
    assert len(manager._pending_events) == 1
    manager._events_draining = False
    manager._release_startup_events()
    manager.stop()
    queue_event(manager, GameFinishedEvent())
    assert not manager._pending_events
    manager._release_startup_events()
    assert not manager._started


def test_release_when_already_draining(manager):
    manager._events_draining = True
    manager._release_startup_events()
    assert manager._events_ready is True


def test_drain_language_show_and_dispatch_error(manager, monkeypatch, qapp):
    from lib_zmq_plugins.shared.base import get_event_tag

    received = []
    monkeypatch.setattr(manager, "_install_translator",
                        lambda language: received.append(("lang", language)))
    window = FakeWindow(manager)
    manager._main_window = window
    monkeypatch.setattr(manager.dispatcher, "dispatch",
                        lambda tag, event: received.append((tag, event)))
    manager._events_ready = True
    manager._events_draining = True
    manager._queue_zmq_event("language_change", LanguageChangeEvent(language="de_DE"))
    manager._queue_zmq_event("show_pm", ShowPluginManagerEvent())
    manager._queue_zmq_event("broken", object())

    def dispatch(tag, event):
        received.append((tag, event))
        if tag == "broken":
            raise RuntimeError("dispatch failure")

    monkeypatch.setattr(manager.dispatcher, "dispatch", dispatch)
    manager._drain_zmq_events()

    assert received[0] == ("lang", "de_DE")
    assert received[1][0] == get_event_tag(LanguageChangeEvent)
    assert received[2][0] == "broken"
    assert window.show_requests == 1
    assert not manager._events_draining


def test_drain_show_event_without_window(manager):
    manager._events_ready = True
    manager._events_draining = True
    queue_event(manager, ShowPluginManagerEvent())
    manager._drain_zmq_events()
    assert not manager._events_draining


def test_drain_reentrancy_and_shutdown_during_drain(manager, monkeypatch):
    first, second = GameFinishedEvent(), GameFinishedEvent()
    seen = []

    def dispatch(tag, event):
        seen.append(event)
        if event is first:
            queue_event(manager, second)
            manager.stop()

    monkeypatch.setattr(manager.dispatcher, "dispatch", dispatch)
    manager._events_ready = True
    manager._events_draining = True
    queue_event(manager, first)
    manager._drain_zmq_events()
    assert seen == [first]
    assert not manager._pending_events
    assert not manager._events_draining


def test_add_plugin_dir_delegates_to_loader(manager, tmp_path):
    root = tmp_path / "plugins"
    root.mkdir()
    manager.add_plugin_dir(root)
    assert manager._loader._plugin_dirs == [root]


def test_load_plugins_registers_dependencies(manager):
    plugin = FakePlugin("a")
    other = FakePlugin("b")
    manager._loader.load_all = lambda: [plugin, other]
    manager._load_plugins()
    assert manager.plugins == {"a": plugin, "b": other}
    assert manager.plugins is not manager._plugins
    assert plugin.client is manager.client
    assert plugin.dispatcher is manager.dispatcher
    assert other.client is manager.client


def test_apply_saved_plugin_states_default_and_invalid_log_level(
        manager, monkeypatch, tmp_path):
    plugin = FakePlugin("saved")
    manager._plugins = {"saved": plugin}
    manager.state_manager = PluginStateManager(tmp_path / "states.json")
    manager.state_manager.set("saved", PluginState(enabled=False, log_level="DEBUG"))
    APPLY_SAVED_STATES(manager)
    assert plugin.info.enabled is False
    assert plugin.set_log_level_calls == ["DEBUG"]

    plugin.set_log_level_calls = []

    def fail_once(level):
        plugin.set_log_level_calls.append(level)
        if len(plugin.set_log_level_calls) == 1:
            raise ValueError("bad level")

    monkeypatch.setattr(plugin, "set_log_level", fail_once)
    APPLY_SAVED_STATES(manager)
    assert plugin.set_log_level_calls == ["DEBUG", plugin.info.log_level]


def test_initialize_plugins_success_failure_disabled_and_shutdown(manager):
    good = FakePlugin("good")
    bad = FakePlugin("bad", raise_on_initialize=True)
    disabled = FakePlugin("disabled", enabled=False)
    manager._plugins = {"good": good, "bad": bad, "disabled": disabled}
    INITIALIZE_PLUGINS(manager)
    assert good.initialize_calls == 1
    assert bad.initialize_calls == 1
    assert disabled.initialize_calls == 0

    manager._shutdown_requested = True
    INITIALIZE_PLUGINS(manager)
    assert good.initialize_calls == 1


def test_shutdown_plugins_success_and_failure(manager):
    good = FakePlugin("good")
    bad = FakePlugin("bad", raise_on_shutdown=True)
    manager._plugins = {"good": good, "bad": bad}
    SHUTDOWN_PLUGINS(manager)
    assert good.shutdown_calls == 1
    assert bad.shutdown_calls == 1


def test_plugin_lookup_enable_disable_and_widgets(manager, qapp):
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    plugin = FakePlugin("visible", widget=widget)
    manager._plugins = {"visible": plugin}
    assert manager.get_plugin("visible") is plugin
    assert manager.get_plugin("missing") is None
    assert manager.enable_plugin("visible") is True
    assert manager.enable_plugin("missing") is False
    assert manager.disable_plugin("visible") is True
    assert manager.disable_plugin("missing") is False
    assert plugin.enable_calls == 1 and plugin.disable_calls == 1
    assert manager.get_plugin_widgets() == {"visible": widget}
    manager._plugins["hidden"] = FakePlugin("hidden", widget=None)
    assert manager.get_plugin_widgets() == {"visible": widget}
    widget.deleteLater()


def test_on_language_change_installs_and_dispatches(manager, monkeypatch):
    from lib_zmq_plugins.shared.base import get_event_tag

    languages, dispatched = [], []
    monkeypatch.setattr(manager, "_install_translator", languages.append)
    monkeypatch.setattr(manager.dispatcher, "dispatch",
                        lambda tag, event: dispatched.append((tag, event)))
    event = LanguageChangeEvent(language="ja_JP")
    manager._on_language_change(event)
    assert languages == ["ja_JP"]
    assert dispatched == [(get_event_tag(LanguageChangeEvent), event)]


def test_connected_callbacks_with_and_without_window(manager):
    manager._on_connected()
    manager._on_disconnected()
    window = FakeWindow(manager)
    manager._main_window = window
    manager._on_connected()
    manager._on_disconnected()
    assert window.connection_states == [True, False]


def test_repr_reflects_plugins_and_started(manager):
    manager._plugins["a"] = FakePlugin("a")
    manager._started = True
    assert repr(manager) == "<PluginManager: 1 plugins, started=True>"
