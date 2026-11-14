"""State helpers, tab/detached windows, list click and closeEvent."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox, QWidget

import plugin_manager.main_window as mw
from plugin_manager.plugin_state import PluginState
from plugin_sdk.plugin_base import PluginLifecycle, WindowMode
from test_cov_pm_e_helpers import (  # noqa: F401
    _offscreen, attach_list_state, make_plugin, shell,
)


def _install(w, qtbot, plugins=None):
    manager, state = attach_list_state(w, qtbot, plugins)
    return manager, state


def test_get_plugin_default_state(qtbot):
    w = shell(qtbot)
    default = PluginState(enabled=False, show_window=False,
                          window_mode=WindowMode.DETACHED, log_level="ERROR")
    p = make_plugin(qtbot, "p", info=SimpleNamespace(
        enabled=False, show_window=False, window_mode=WindowMode.DETACHED,
        log_level="ERROR"))
    _install(w, qtbot, {"p": p})
    assert w._get_plugin_default_state("p") == default
    assert w._get_plugin_default_state("missing") is None
    assert w._effective_state("p") == default


def test_effective_state_prefers_saved(qtbot):
    w = shell(qtbot)
    manager, state = _install(w, qtbot, {})
    saved = PluginState(enabled=False, window_mode=WindowMode.CLOSED)
    state.set("p", saved)
    w._get_plugin_default_state = lambda name: PluginState(enabled=True)
    assert w._effective_state("p") == saved


def test_apply_saved_states_all_branches(qtbot, monkeypatch):
    w = shell(qtbot)
    calls = []
    disabled = make_plugin(qtbot, "disabled")
    hidden = make_plugin(qtbot, "hidden")
    closed = make_plugin(qtbot, "closed")
    failing = make_plugin(qtbot, "failing")
    failing.set_log_level = lambda level: (_ for _ in ()).throw(ValueError("bad"))
    manager, state = _install(w, qtbot, {
        "disabled": disabled, "hidden": hidden,
        "closed": closed, "failing": failing,
    })
    manager.disable_plugin = lambda name: calls.append(("disable", name))
    state.set("disabled", PluginState(enabled=False))
    state.set("hidden", PluginState(show_window=False))
    state.set("closed", PluginState(window_mode=WindowMode.CLOSED))
    state.set("failing", PluginState(enabled=True, log_level="INFO"))
    w._get_plugin_default_state = lambda name: None
    w._apply_saved_states()
    assert ("disable", "disabled") in calls
    assert {"hidden", "closed"} <= w._closed_plugins
    assert hidden.close_calls == 1 and closed.close_calls == 1
    assert disabled.log_levels == ["DEBUG"]
    assert hidden.log_levels == ["DEBUG"]
    assert failing.log_levels == []


def test_sync_state_no_changes_and_both_changes(qtbot):
    w = shell(qtbot)
    manager, state = _install(w, qtbot, {})
    w._get_plugin_default_state = lambda name: None
    w._sync_state("p")
    assert state.all_states == {}
    w._sync_state("p", enabled=False)
    assert state.get("p").enabled is False
    w._sync_state("p", enabled=True, window_mode=WindowMode.DETACHED)
    st = state.get("p")
    assert st.enabled is True and st.window_mode == WindowMode.DETACHED


def test_open_tab_window_branches(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    _install(w, qtbot, {"p": p})
    t = w._tab_widget
    w._open_tab_window("missing")
    assert t.count() == 0

    p.lifecycle = PluginLifecycle.NEW
    w._open_tab_window("p")
    assert t.count() == 0
    p.lifecycle = PluginLifecycle.READY
    p.ensure_widget = lambda: None
    w._open_tab_window("p")
    assert t.count() == 0
    other_plugin = make_plugin(qtbot, "other")
    p.widget = other_plugin.widget
    p.ensure_widget = lambda: p.widget

    t.add_detachable_tab(p.widget, "p")
    second_widget = QWidget()
    qtbot.addWidget(second_widget)
    t.add_detachable_tab(second_widget, "other")
    w._open_tab_window("p")
    assert t.currentIndex() == 0

    attached = []
    t._attach_tab = lambda name: attached.append(name)
    t._detached_windows["p"] = SimpleNamespace()
    w._open_tab_window("p")
    assert attached == ["p"]
    del t._detached_windows["p"]
    t.removeTab(1)
    t.removeTab(0)

    other = make_plugin(qtbot, "fresh")
    w._manager.plugins["fresh"] = other
    w._open_tab_window("fresh")
    assert t.count() == 1 and t.tabText(0) == "fresh"
    t.removeTab(0)
    for widget in (p.widget, second_widget, other.widget):
        if shiboken6.isValid(widget):
            widget.setParent(None)


def test_open_detached_window_branches(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    _install(w, qtbot, {"p": p})
    t = w._tab_widget
    w._open_detached_window("missing")
    assert t.count() == 0

    p.lifecycle = PluginLifecycle.NEW
    w._open_detached_window("p")
    assert t.count() == 0
    p.lifecycle = PluginLifecycle.READY
    p.ensure_widget = lambda: None
    w._open_detached_window("p")
    assert t.count() == 0
    tmp_plugin = make_plugin(qtbot, "tmp")
    p.widget = tmp_plugin.widget
    p.ensure_widget = lambda: p.widget

    shown = []
    t._detached_windows["p"] = SimpleNamespace(
        show=lambda: shown.append("show"))
    w._open_detached_window("p")
    assert shown == ["show"]
    del t._detached_windows["p"]

    detach_calls = []
    t._detach_tab = lambda index, name: detach_calls.append((index, name))
    t.add_detachable_tab(p.widget, "p")
    w._open_detached_window("p")
    assert detach_calls[-1] == (0, "p")
    t.removeTab(0)

    w._open_detached_window("p")
    assert detach_calls[-1] == (0, "p")
    t.removeTab(0)
    if shiboken6.isValid(p.widget):
        p.widget.setParent(None)


def test_on_list_double_clicked_and_tab_events(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "p")
    _install(w, qtbot, {"p": p})
    calls = []
    monkeypatch.setattr(w, "_open_plugin_window",
                        lambda name: calls.append(("open", name)))
    monkeypatch.setattr(w, "_remove_plugin_window",
                        lambda name: calls.append(("remove", name)))
    w._on_list_double_clicked(None)
    assert calls == []
    item = QListWidgetItem("p")
    item.setData(Qt.ItemDataRole.UserRole, "p")
    w._list.addItem(item)
    w._on_list_double_clicked(item)
    w._on_tab_detached("p")
    w._on_tab_attached("p")
    w._on_tab_closed("p")
    w._on_detached_window_closed("p")
    assert calls == [("open", "p"), ("remove", "p"), ("remove", "p")]


def test_close_event_without_tray_attribute(qtbot, monkeypatch):
    w = shell(qtbot)
    original = mw.PluginManagerWindow.closeEvent
    w.closeEvent = lambda event: original(w, event)
    try:
        manager, state = _install(w, qtbot, {})
        calls = []
        state.save = lambda: calls.append("save")
        manager.stop = lambda: calls.append("stop")
        monkeypatch.setattr(mw.QMessageBox, "question",
                            lambda *args: QMessageBox.StandardButton.Yes)
        from PySide6.QtGui import QCloseEvent
        accepted = QCloseEvent()
        w.closeEvent(accepted)
        assert accepted.isAccepted() and calls == ["save", "stop"]
    finally:
        w.closeEvent = lambda event: event.accept()
