"""Plugin window and dialog methods of PluginManagerWindow."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidgetItem, QMessageBox, QWidget

import plugin_manager.main_window as mw
from plugin_manager.plugin_state import PluginState
from plugin_sdk.plugin_base import PluginLifecycle, WindowMode
from test_cov_pm_e_helpers import (  # noqa: F401
    _offscreen, attach_list_state, make_plugin, shell,
)


def _install(w, qtbot, plugins=None):
    manager, state = attach_list_state(w, qtbot, plugins)
    w._get_plugin_default_state = lambda name: None
    w._effective_state = lambda name: state.get_effective(
        name, w._get_plugin_default_state(name))
    w._refresh_plugin_list = lambda: None
    return manager, state


def test_open_plugin_window_guard_branches(qtbot):
    w = shell(qtbot)
    _install(w, qtbot, {})
    w._open_plugin_window("missing")
    assert w._tab_widget.count() == 0

    p = make_plugin(qtbot, "p", PluginLifecycle.INITIALIZING)
    w._manager.plugins["p"] = p
    w._open_plugin_window("p")
    assert w._tab_widget.count() == 0

    p.lifecycle = PluginLifecycle.READY
    p.ensure_widget = lambda: None
    w._open_plugin_window("p")
    assert w._tab_widget.count() == 0


def test_open_plugin_window_tab_detached_existing_and_reopen(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    manager, state = _install(w, qtbot, {"p": p})
    w._open_plugin_window("p")
    assert w._tab_widget.count() == 1 and w._tab_widget.tabText(0) == "p"
    assert "p" not in w._closed_plugins

    w._open_plugin_window("p")
    assert w._tab_widget.count() == 1 and w._tab_widget.currentIndex() == 0

    w._closed_plugins.add("p")
    state.set("p", PluginState(window_mode=WindowMode.DETACHED))
    opened = []
    w._tab_widget.removeTab(0)
    monkeypatch.setattr(w, "_open_detached_window",
                        lambda name: opened.append(name))
    w._open_plugin_window("p")
    assert opened == ["p"] and "p" not in w._closed_plugins

    shown = []
    detached = SimpleNamespace(show=lambda: shown.append("show"),
                               activateWindow=lambda: shown.append("activate"))
    w._tab_widget._detached_windows["p"] = detached
    w._open_plugin_window("p")
    assert shown == ["show", "activate"] and opened == ["p"]
    del w._tab_widget._detached_windows["p"]


def test_remove_plugin_window_detached_and_tab(qtbot):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    _install(w, qtbot, {"p": p})
    widget = p.widget
    w._tab_widget.add_detachable_tab(widget, "p")
    events = []
    window = SimpleNamespace(
        blockSignals=lambda flag: events.append(("block", flag)),
        close=lambda: events.append("close"),
        deleteLater=lambda: events.append("deleteLater"))
    w._tab_widget._detached_windows["p"] = window
    w._remove_plugin_window("p")
    assert events == [("block", True), "close", "deleteLater"]
    assert "p" not in w._tab_widget._detached_windows
    assert w._tab_widget.count() == 0
    assert p.widget is None and p.close_calls == 1
    assert "p" in w._closed_plugins


def test_remove_plugin_window_no_plugin_and_close_wrapper(qtbot):
    w = shell(qtbot)
    _install(w, qtbot, {})
    w._remove_plugin_window("ghost")
    assert "ghost" in w._closed_plugins

    p = make_plugin(qtbot, "p")
    p.widget = None
    w._manager.plugins["p"] = p
    w._remove_plugin_window("p")
    assert p.close_calls == 0

    w._close_plugin_window("p")
    assert "p" in w._closed_plugins


def test_open_plugin_log(qtbot, monkeypatch):
    w = shell(qtbot)
    calls = []
    monkeypatch.setattr(w, "_open_log_viewer",
                        lambda initial_log: calls.append(initial_log))
    w._open_plugin_log("alpha")
    assert calls == ["alpha"]


def test_open_plugin_readme_success_and_branches(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    _install(w, qtbot, {})
    made = []

    class Readme:
        def __init__(self, name, text, parent=None, base_dir=None):
            made.append((name, text, parent, base_dir))

        def exec(self):
            made.append("exec")

    monkeypatch.setattr(mw, "_PluginReadmeDialog", Readme)
    w._open_plugin_readme("missing")
    assert made == []

    p = make_plugin(qtbot, "p", plugin_dir=tmp_path)
    w._manager.plugins["p"] = p
    w._open_plugin_readme("p")
    assert made[0] == ("p", "# readme", w, tmp_path)
    assert "exec" in made

    warnings = []
    monkeypatch.setattr(mw.QMessageBox, "warning",
                        lambda *args: warnings.append(args))
    p.get_readme_text = lambda: (_ for _ in ()).throw(OSError("bad"))
    made.clear()
    w._open_plugin_readme("p")
    assert len(warnings) == 1 and "README" in warnings[0][1]
    assert "exec" not in made


def test_open_plugin_info(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    _install(w, qtbot, {"p": p})
    made = []

    class Info:
        def __init__(self, plugin, parent=None):
            made.append((plugin, parent))

        def exec(self):
            made.append("exec")

    monkeypatch.setattr(mw, "PluginInfoDialog", Info)
    w._open_plugin_info("missing")
    assert made == []
    w._open_plugin_info("p")
    assert made == [(p, w), "exec"]


def _settings_dialog(monkeypatch, result, new_state):
    made = []

    class Dialog:
        def __init__(self, name, current, other_info, parent=None, plugin=None):
            made.append((name, current, other_info, parent, plugin))
            self.result_state = new_state

        def exec(self):
            made.append("exec")
            return result

        def apply_config(self):
            made.append("apply_config")

    monkeypatch.setattr(mw, "PluginSettingsDialog", Dialog)
    return made


def test_open_plugin_settings_rejected(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    manager, state = _install(w, qtbot, {"p": p})
    made = _settings_dialog(monkeypatch, QDialog.DialogCode.Rejected,
                            PluginState())
    w._open_plugin_settings("p")
    assert made[0][0] == "p" and made[0][2] is None and made[0][4] is p
    assert state.get("p") == PluginState() or state.all_states == {}


def test_open_plugin_settings_accepted_all_changes(qtbot, monkeypatch):
    w = shell(qtbot)
    other = object()
    p = make_plugin(qtbot, "p", other_info=other)
    manager, state = _install(w, qtbot, {"p": p})
    calls = []
    manager.enable_plugin = lambda name: calls.append(("enable", name))
    manager.disable_plugin = lambda name: calls.append(("disable", name))
    state.set("p", PluginState(enabled=True, log_level="DEBUG"))
    new_state = PluginState(enabled=False, log_level="INFO")
    made = _settings_dialog(monkeypatch, QDialog.DialogCode.Accepted, new_state)
    p.save_config = lambda: calls.append("save_config")
    monkeypatch.setattr(w, "_remove_plugin_window",
                        lambda name: calls.append(("remove", name)))
    refreshes = []
    w._refresh_plugin_list = lambda: refreshes.append("refresh")
    w._open_plugin_settings("p")
    assert made[0][2] is other
    assert state.get("p") == new_state
    assert "apply_config" in made and "save_config" in calls
    assert ("remove", "p") in calls and ("disable", "p") in calls
    assert p.log_levels == ["INFO"]
    assert refreshes == ["refresh"]


def test_open_plugin_settings_enable_and_missing_plugin(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    manager, state = _install(w, qtbot, {"p": p})
    calls = []
    manager.enable_plugin = lambda name: calls.append(("enable", name))
    state.set("p", PluginState(enabled=False))
    made = _settings_dialog(monkeypatch, QDialog.DialogCode.Accepted,
                            PluginState(enabled=True))
    refreshes = []
    w._refresh_plugin_list = lambda: refreshes.append("refresh")
    w._open_plugin_settings("p")
    assert ("enable", "p") in calls and p.log_levels == []
    assert refreshes == ["refresh"]

    made.clear()
    w._open_plugin_settings("missing")
    assert made[0][0] == "missing" and made[0][2] is None
