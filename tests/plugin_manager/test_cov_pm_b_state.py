"""Coverage tests for plugin_manager.plugin_state."""
from __future__ import annotations

import json
from pathlib import Path

from plugin_manager.plugin_state import PluginState, PluginStateManager, _DEFAULT
from plugin_sdk.plugin_base import LogLevel, WindowMode


def _manager(path: Path) -> PluginStateManager:
    return PluginStateManager(path)


def test_plugin_state_defaults_and_equality():
    a = PluginState()
    b = PluginState()
    assert a == b
    assert a == _DEFAULT
    assert a.enabled is True
    assert a.show_window is True
    assert a.window_mode == WindowMode.TAB
    assert a.log_level == LogLevel.DEBUG
    assert PluginState(enabled=False, show_window=False,
                       window_mode=WindowMode.DETACHED,
                       log_level=LogLevel.ERROR) != a


def test_load_missing_file_keeps_empty_states(tmp_path):
    manager = _manager(tmp_path / "missing" / "state.json")
    manager.load()
    assert manager.all_states == {}
    assert manager.get("alpha") is _DEFAULT


def test_load_valid_json_and_round_trip_save(tmp_path):
    path = tmp_path / "states.json"
    path.write_text(json.dumps({
        "alpha": {
            "enabled": False,
            "show_window": False,
            "window_mode": "detached",
            "log_level": "ERROR",
            "unknown_field": "ignored",
        },
        "beta": {"enabled": True, "junk": 17},
    }), encoding="utf-8")
    manager = _manager(path)
    manager.load()

    alpha = manager.get("alpha")
    assert alpha == PluginState(False, False, WindowMode.DETACHED, LogLevel.ERROR)
    assert manager.get("beta") == PluginState()

    custom = PluginState(enabled=False, show_window=False,
                         window_mode=WindowMode.CLOSED, log_level=LogLevel.WARNING)
    manager.set("gamma", custom)
    assert manager._dirty is True
    manager.save()
    assert manager._dirty is False
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["gamma"] == {
        "enabled": False,
        "show_window": False,
        "window_mode": "closed",
        "log_level": "WARNING",
    }

    reload_manager = _manager(path)
    reload_manager.load()
    assert reload_manager.get("gamma") == custom


def test_load_unknown_fields_filtered_into_defaults(tmp_path):
    path = tmp_path / "states.json"
    path.write_text(json.dumps({"alpha": {"mystery": 1, "log_level": "INFO"}}),
                    encoding="utf-8")
    manager = _manager(path)
    manager.load()
    assert manager.get("alpha") == PluginState(log_level=LogLevel.INFO)


def test_load_corrupt_json_is_ignored(tmp_path):
    path = tmp_path / "states.json"
    path.write_text("{broken", encoding="utf-8")
    manager = _manager(path)
    manager.load()
    assert manager.all_states == {}
    manager.set("alpha", PluginState(enabled=False))
    manager.save()
    assert json.loads(path.read_text(encoding="utf-8"))["alpha"]["enabled"] is False


def test_save_without_changes_does_not_create_file(tmp_path):
    path = tmp_path / "deep" / "states.json"
    manager = _manager(path)
    manager.load()
    manager.save()
    assert path.exists() is False


def test_save_failure_logs_and_keeps_dirty(tmp_path, monkeypatch):
    manager = _manager(tmp_path / "states.json")
    manager.set("alpha", PluginState(enabled=False))
    seen = []
    monkeypatch.setattr("plugin_manager.plugin_state.logger.error",
                        lambda message: seen.append(message))

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)
    manager.save()
    assert manager._dirty is True
    assert seen and "disk full" in seen[0]


def test_get_effective_precedence_chain(tmp_path):
    manager = _manager(tmp_path / "states.json")
    declared = PluginState(enabled=False, show_window=False,
                           window_mode=WindowMode.CLOSED, log_level=LogLevel.ERROR)

    assert manager.get_effective("alpha") == _DEFAULT
    assert manager.get_effective("alpha", None) == _DEFAULT
    assert manager.get_effective("alpha", declared) is declared

    saved = PluginState(enabled=True, show_window=True,
                        window_mode=WindowMode.DETACHED, log_level=LogLevel.INFO)
    manager.set("alpha", saved)
    effective = manager.get_effective("alpha", declared)
    assert effective == saved
    assert effective is not saved
    assert effective is not declared


def test_remove_and_all_states_are_isolated_snapshots(tmp_path):
    manager = _manager(tmp_path / "states.json")
    manager.set("alpha", PluginState(enabled=False))
    manager.set("beta", PluginState(enabled=False))
    manager.remove("missing")
    assert manager._dirty is True

    snapshot = manager.all_states
    snapshot.clear()
    assert set(manager.all_states) == {"alpha", "beta"}
    manager.remove("alpha")
    assert set(manager.all_states) == {"beta"}
    assert manager.get("alpha") is _DEFAULT
