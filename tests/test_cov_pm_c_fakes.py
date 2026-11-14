"""Shared fakes for plugin_manager coverage tests (no real ZMQ/network/app)."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from plugin_manager import plugin_manager as module
from shared_types.events import GameFinishedEvent


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.handlers = {}
        self.connected = False
        self.disconnects = 0
        self.is_connected = True
        self.reconnect_count = 7
        self.on_connect = lambda: None
        self.on_disconnect = lambda: None
        self.subscriptions = []
        self.registrations = []
        self.fail_disconnect = False

    def register_event_types(self, *args):
        self.registrations.append(("events", args))

    def register_command_types(self, *args):
        self.registrations.append(("commands", args))

    def register_query_types(self, *args, **kwargs):
        self.registrations.append(("queries", args, kwargs))

    def subscribe(self, event_type, callback):
        self.handlers[event_type] = callback
        self.subscriptions.append(event_type)

    def connect(self):
        self.connected = True
        self.is_connected = True
        self.on_connect()

    def disconnect(self):
        self.disconnects += 1
        self.connected = False
        self.is_connected = False
        if self.fail_disconnect:
            raise RuntimeError("disconnect failed")
        self.on_disconnect()

    def emit(self, event):
        callback = self.handlers.get(type(event))
        if callback is not None:
            callback(event)


class FakePlugin:
    def __init__(self, name: str = "probe", enabled: bool = True, widget=None,
                 raise_on_shutdown: bool = False,
                 raise_on_initialize: bool = False,
                 raise_on_log_level: bool = False):
        self.name = name
        self.info = SimpleNamespace(
            enabled=enabled, show_window=True, window_mode="tab", log_level="INFO",
        )
        self.is_enabled = enabled
        self.widget = widget
        self.client = None
        self.dispatcher = None
        self.set_log_level_calls = []
        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.enable_calls = 0
        self.disable_calls = 0
        self.raise_on_initialize = raise_on_initialize
        self.raise_on_shutdown = raise_on_shutdown
        self.raise_on_log_level = raise_on_log_level

    def set_client(self, client):
        self.client = client

    def set_event_dispatcher(self, dispatcher):
        self.dispatcher = dispatcher

    def set_log_level(self, level):
        self.set_log_level_calls.append(level)
        if self.raise_on_log_level:
            raise ValueError("bad level")

    def initialize(self):
        self.initialize_calls += 1
        if self.raise_on_initialize:
            raise RuntimeError("initialize failed")

    def shutdown(self):
        self.shutdown_calls += 1
        if self.raise_on_shutdown:
            raise RuntimeError("shutdown failed")

    def enable(self):
        self.enable_calls += 1
        self.is_enabled = True

    def disable(self):
        self.disable_calls += 1
        self.is_enabled = False


class FakeWindow:
    def __init__(self, manager=None):
        self.manager = manager
        self.title = None
        self.shown = 0
        self.connection_states = []
        self.show_requests = 0

        class _Signal:
            def __init__(self, owner):
                self.owner = owner

            def emit(self, *args):
                self.owner.show_requests += 1

        self._show_requested = _Signal(self)

    def setWindowTitle(self, title):
        self.title = title

    def show(self):
        self.shown += 1

    def set_connected(self, ok):
        self.connection_states.append(ok)


class FakeAuthManager:
    def __init__(self, removed=()):
        self.instance = self
        self.loaded = None
        self.removed = list(removed)
        self.saves = 0

    def validate_authorizations(self, loaded_plugins):
        self.loaded = loaded_plugins
        return self.removed

    def save(self):
        self.saves += 1


SHUTDOWN_REGISTRATION = module.PluginManager.__dict__["_register_shutdown_handlers"]
VALIDATE_AUTHORIZATIONS = module.PluginManager.__dict__["_validate_control_authorizations"]
APPLY_SAVED_STATES = module.PluginManager.__dict__["_apply_saved_plugin_states"]
INITIALIZE_PLUGINS = module.PluginManager.__dict__["_initialize_plugins"]
SHUTDOWN_PLUGINS = module.PluginManager.__dict__["_shutdown_plugins"]


@pytest.fixture
def base_env(monkeypatch, tmp_path):
    """Isolate PluginManager.__init__ from signals, atexit, data dir and ZMQ."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(module, "ZMQClient", FakeClient)
    monkeypatch.setattr(module, "patch_sys_path_for_frozen", lambda: None)
    monkeypatch.setattr(module, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(module, "get_all_plugin_dirs", lambda: [tmp_path / "plugins"])
    monkeypatch.setattr(module.signal, "signal", lambda *args: None)
    monkeypatch.setattr(module.atexit, "register", lambda *args: None)
    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(module, "_TranslatorInstaller", lambda: SimpleNamespace(
        install=lambda language: None,
    ))
    monkeypatch.setattr(module.PluginManager, "_register_shutdown_handlers",
                        lambda self: None)
    monkeypatch.setattr(module.PluginManager, "_validate_control_authorizations",
                        lambda self: None)
    monkeypatch.setattr(module.PluginManager, "_apply_saved_plugin_states",
                        lambda self: None)
    previous = module.PluginManager._instance
    yield
    module.PluginManager._instance = previous


@pytest.fixture
def manager(base_env, tmp_path):
    instance = module.PluginManager(
        "inproc://coverage", plugin_dirs=[], log_handler=object(),
        pub_endpoint="tcp://pub", ctrl_endpoint="tcp://ctrl",
    )
    instance._loader.load_all = lambda: []
    yield instance
    if not instance._shutdown_requested:
        instance.stop()


def make_started_manager(base_env):
    """Create a manager whose startup steps are stubbed to the minimum."""
    return module.PluginManager("inproc://coverage", plugin_dirs=[])


def queue_event(instance, event):
    from lib_zmq_plugins.shared.base import get_event_tag
    instance._queue_zmq_event(get_event_tag(type(event)), event)
