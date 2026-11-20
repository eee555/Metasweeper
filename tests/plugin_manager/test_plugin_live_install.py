"""Runtime activation of a newly installed market package."""
from __future__ import annotations

import json
import sys
from threading import RLock

import pytest
from loguru import logger

from plugin_manager import app_paths, logging_setup, plugin_lib_env, plugin_manager, plugin_uninstall
from plugin_manager.event_dispatcher import EventDispatcher
from plugin_manager.plugin_loader import PluginLoader
from plugin_manager.plugin_state import PluginState, PluginStateManager


SOURCE = """
from plugin_sdk import BasePlugin, PluginInfo

class Demo(BasePlugin):
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="live-demo")

    def _setup_subscriptions(self):
        pass
"""


@pytest.fixture
def runtime(tmp_path, monkeypatch, qtbot):
    root = tmp_path / "user_plugins"
    package = root / "metasweeper_live_demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(SOURCE, encoding="utf-8")
    (package / plugin_uninstall.META_FILENAME).write_text(json.dumps({
        "repository": "https://github.com/example/live-demo",
    }), encoding="utf-8")
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(app_paths, "get_plugin_data_dir", lambda _: tmp_path / "plugin_data")
    monkeypatch.setattr(logging_setup, "get_plugin_logger", lambda *a, **kw: (logger, 0))
    monkeypatch.setattr(logging_setup, "set_plugin_log_level", lambda *a, **kw: None)
    monkeypatch.setattr(plugin_manager, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(plugin_uninstall, "get_executable_dir", lambda: tmp_path)
    monkeypatch.setattr(plugin_manager, "dependency_environment_requires_restart", lambda: False)
    manager = plugin_manager.PluginManager.__new__(plugin_manager.PluginManager)
    manager._started = True
    manager._shutdown_requested = False
    manager._settings = plugin_manager.SettingsManager(tmp_path)
    manager._plugins = {}
    manager._plugins_lock = RLock()
    manager._loader = PluginLoader()
    manager._client = object()
    manager._dispatcher = EventDispatcher()
    manager._translator_installer = None
    manager.state_manager = PluginStateManager(tmp_path / "plugin_states.json")
    try:
        yield manager, package
    finally:
        for instance in manager.plugins.values():
            if hasattr(instance, "shutdown"):
                instance.shutdown()
        sys.modules.pop(package.name, None)


@pytest.mark.parametrize("enabled", [True, False])
def test_loads_only_new_package_and_respects_saved_state(runtime, qtbot, enabled):
    manager, package = runtime
    manager.state_manager.set("live-demo", PluginState(enabled=enabled))
    existing = object()
    manager._plugins["existing"] = existing
    prepared = []

    assert manager.load_installed_package(package, prepared.append) == "loaded"

    instance = manager.get_plugin("live-demo")
    assert instance is not None and prepared == [instance]
    assert manager.plugins["existing"] is existing
    assert instance.is_enabled == enabled
    if enabled:
        qtbot.waitUntil(lambda: instance.is_ready)
    assert manager.load_installed_package(package, prepared.append) == "restart"
    assert manager.get_plugin("live-demo") is instance


@pytest.mark.parametrize("source", ["raise ImportError('missing dependency')", SOURCE])
def test_import_failure_or_duplicate_name_preserves_existing_plugin(runtime, source):
    manager, package = runtime
    (package / "__init__.py").write_text(source, encoding="utf-8")
    existing = object()
    manager._plugins["live-demo"] = existing
    assert manager.load_installed_package(package, lambda _: pytest.fail("unexpected registration")) == "failed"
    assert manager.get_plugin("live-demo") is existing
    status = manager.get_module_dependency_status(package.name)
    assert status.import_status == "failed"
    assert status.import_error


def test_environment_replacement_defers_import(runtime, monkeypatch, tmp_path):
    manager, package = runtime
    monkeypatch.setattr(plugin_lib_env, "_LIVE_ENV_CHANGED", plugin_lib_env.threading.Event())
    monkeypatch.setattr(plugin_uninstall, "installed_fingerprints",
                        lambda _: {"shared": "new-version"})
    plugin_lib_env._check_live_dependency_changes(tmp_path, {"shared": "old-version"})
    assert plugin_lib_env.dependency_environment_requires_restart()
    monkeypatch.setattr(plugin_manager, "dependency_environment_requires_restart",
                        plugin_lib_env.dependency_environment_requires_restart)
    assert manager.load_installed_package(package, lambda _: pytest.fail("unexpected load")) == "restart"
    assert package.name not in sys.modules


def test_async_initialization_failure_is_available_for_the_plugin_list(runtime, qtbot):
    manager, package = runtime
    (package / "__init__.py").write_text(
        SOURCE + "\n    def on_initialized(self):\n        raise RuntimeError('startup failed')\n",
        encoding="utf-8")
    assert manager.load_installed_package(package, lambda _: None) == "loaded"
    instance = manager.get_plugin("live-demo")
    qtbot.waitUntil(lambda: instance.initialization_error is not None)
    assert instance.initialization_error == "RuntimeError: startup failed"
