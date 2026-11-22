"""_refresh_plugin_list, context menu and authorization actions."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon

import plugin_manager.main_window as mw
from plugin_manager.plugin_state import PluginState
from plugin_sdk.plugin_base import PluginLifecycle, WindowMode
from tests.plugin_manager.test_cov_pm_e_helpers import (  # noqa: F401
    _offscreen, attach_list_state, make_plugin, real_window, shell,
)


def _install(w, qtbot, plugins):
    manager, state = attach_list_state(w, qtbot, plugins)
    w._get_plugin_default_state = lambda name: None
    w._effective_state = lambda name: state.get_effective(
        name, w._get_plugin_default_state(name))
    return manager, state


def _capture_menu(monkeypatch):
    menus = []

    class Menu:
        def __init__(self, parent):
            self.parent = parent
            self.items = []
            self.executed = None
            self._keepalive = []
            menus.append(self)

        def addAction(self, text):
            from PySide6.QtGui import QAction
            act = QAction(text, self.parent)
            act.setEnabled(True)
            self._keepalive.append(act)
            self.items.append(act)
            return act

        def addSeparator(self):
            self.items.append("sep")
            return "sep"

        def exec(self, pos):
            self.executed = pos

    monkeypatch.setattr(mw, "QMenu", Menu)
    return menus


def _actions(menu):
    return [item for item in menu.items if item != "sep"]


def test_refresh_plugin_list_empty(qtbot):
    w = shell(qtbot)
    _install(w, qtbot, {})
    w._refresh_plugin_list()
    assert w._list.count() == 0 and w._tab_widget.count() == 0
    assert w._operation_notice.isHidden()


def test_workspace_tracks_open_tabs_and_keyboard_activation(qtbot, monkeypatch, tmp_path):
    plugins = {name: make_plugin(qtbot, name) for name in ("first", "second")}
    window = real_window(qtbot, monkeypatch, tmp_path, plugins, tray=False)
    window._auto_update_timer.stop()
    window.show()
    window.activateWindow()
    plugin_list = window._list
    tabs = window._tab_widget

    qtbot.mouseClick(plugin_list.viewport(), Qt.MouseButton.LeftButton,
                    pos=plugin_list.visualItemRect(plugin_list.item(1)).center())
    assert tabs.tab_key(tabs.currentIndex()) == "second"
    window._on_tab_closed("first")
    window._on_tab_closed("second")
    assert window._workspace.currentWidget() == window._empty_workspace
    assert window._empty_title.text() == "未打开插件窗口"
    assert window._empty_market_btn.isHidden()

    plugin_list.setFocus()
    plugin_list.setCurrentRow(0)
    qtbot.waitUntil(plugin_list.hasFocus)
    qtbot.keyClick(plugin_list, Qt.Key.Key_Return)
    assert tabs.tab_key(tabs.currentIndex()) == "first"
    assert window._workspace.currentWidget() == tabs


def test_selected_failed_plugin_exposes_diagnostics(qtbot, monkeypatch, tmp_path):
    failed = make_plugin(qtbot, "failed", PluginLifecycle.STOPPED)
    failed.initialization_error = "initialization error"
    failed.info.version = "1.2.0-preview.20261120"
    window = real_window(qtbot, monkeypatch, tmp_path, {"failed": failed}, tray=False)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *args: errors.append(args[-1]))
    assert window._plugin_details_btn.isHidden()
    window._list.setCurrentRow(0)
    assert not window._plugin_details_btn.isHidden()
    assert window._list.currentItem().toolTip() == "查看详情"
    window._plugin_details_btn.click()
    assert errors == ["initialization error"]


def test_refresh_plugin_list_all_lifecycle_variants(qtbot):
    w = shell(qtbot)
    plugins = {
        "zeta": make_plugin(qtbot, "zeta", PluginLifecycle.INITIALIZING,
                            widget=None),
        "beta": make_plugin(qtbot, "beta", enabled=False, widget=None),
        "alpha": make_plugin(qtbot, "alpha", PluginLifecycle.SHUTTING_DOWN,
                             widget=None),
        "ready": make_plugin(qtbot, "ready"),
        "stopped": make_plugin(qtbot, "stopped", PluginLifecycle.STOPPED,
                               widget=None),
        "noview": make_plugin(qtbot, "noview", widget=None),

    }
    for name, plugin in plugins.items():
        if name != "ready":
            plugin.widget = None
    manager, state = _install(w, qtbot, plugins)
    w._refresh_plugin_list()

    assert [w._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(w._list.count())] == [
                "zeta", "beta", "alpha", "ready", "stopped", "noview"]
    by_name = {w._list.item(i).data(Qt.ItemDataRole.UserRole): w._list.item(i)
               for i in range(w._list.count())}
    assert by_name["zeta"].text() == w.tr("{name}（初始化中...）").format(name="zeta")
    assert by_name["alpha"].text() == w.tr("{name}（关闭中...）").format(name="alpha")
    assert by_name["beta"].foreground().color() == Qt.GlobalColor.gray
    assert w._tab_widget.count() == 1
    assert w._tab_widget.tabText(0) == "ready"
    assert w._tab_widget.tabIcon(0).cacheKey() == plugins["ready"].plugin_icon.cacheKey()
    assert w._operation_notice.isHidden()

    w._list.setCurrentRow(2)
    w._refresh_plugin_list()
    assert w._list.currentRow() == 2


def test_refresh_plugin_list_detached_mode(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "detached")
    manager, state = _install(w, qtbot, {"detached": p})
    state.set("detached", PluginState(window_mode=WindowMode.DETACHED))
    seen = []
    monkeypatch.setattr(w._tab_widget, "_detach_tab",
                        lambda index, name: seen.append((index, name)))
    w._refresh_plugin_list()
    assert seen == [(0, "detached")]


def test_refresh_plugin_list_skips_closed_and_detached(qtbot):
    w = shell(qtbot)
    p = make_plugin(qtbot, "closed")
    _install(w, qtbot, {"closed": p})
    w._closed_plugins.add("closed")
    w._refresh_plugin_list()
    assert w._tab_widget.count() == 0
    w._closed_plugins.clear()
    w._tab_widget._detached_windows["closed"] = SimpleNamespace()
    w._refresh_plugin_list()
    assert w._tab_widget.count() == 0
    del w._tab_widget._detached_windows["closed"]


def test_context_menu_no_item_or_unknown_plugin(qtbot, monkeypatch):
    w = shell(qtbot)
    _install(w, qtbot, {})
    menus = _capture_menu(monkeypatch)
    w._on_list_context_menu(QPoint(9999, 9999))
    assert menus == []

    from PySide6.QtWidgets import QListWidgetItem
    item = QListWidgetItem("ghost")
    item.setData(Qt.ItemDataRole.UserRole, "ghost")
    w._list.addItem(item)
    w._list.setCurrentRow(0)
    pos = QPoint(1, 1)
    monkeypatch.setattr(w._list, "itemAt", lambda p: item)
    w._on_list_context_menu(pos)
    assert menus == []


def test_row_more_button_opens_existing_plugin_menu(qtbot, monkeypatch, tmp_path):
    plugin = make_plugin(qtbot, "demo")
    window = real_window(qtbot, monkeypatch, tmp_path, {"demo": plugin})
    menus = _capture_menu(monkeypatch)
    window.show()
    listing = window._list
    row = listing.visualItemRect(listing.item(0))
    button = listing.itemDelegate().menu_rect(row)
    assert button.bottom() <= row.center().y()
    clicked = []
    listing.itemClicked.connect(clicked.append)

    qtbot.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=button.center())
    assert len(menus) == 1
    assert menus[0].executed == listing.viewport().mapToGlobal(button.bottomLeft())
    assert menus[0].items[0].text() == window.tr("打开窗口")
    assert clicked == []

    qtbot.mousePress(listing.viewport(), Qt.MouseButton.LeftButton, pos=button.center())
    qtbot.mouseRelease(listing.viewport(), Qt.MouseButton.LeftButton, pos=row.center())
    assert len(menus) == 1
    assert clicked == []

    version_area = QPoint(button.center().x(), row.bottom() - 10)
    qtbot.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=version_area)
    assert len(menus) == 1
    assert clicked == [listing.item(0)]


def test_context_menu_all_actions_enabled_plugin(qtbot, monkeypatch):
    w = shell(qtbot)
    required = [object]
    p = make_plugin(qtbot, "demo", info=SimpleNamespace(
        required_controls=required))
    _install(w, qtbot, {"demo": p})
    menus = _capture_menu(monkeypatch)

    from PySide6.QtWidgets import QListWidgetItem
    item = QListWidgetItem("demo")
    item.setData(Qt.ItemDataRole.UserRole, "demo")
    w._list.addItem(item)
    monkeypatch.setattr(w._list, "itemAt", lambda p: item)
    w._on_list_context_menu(QPoint(2, 3))
    menu = menus[0]
    assert menu.executed == w._list.viewport().mapToGlobal(QPoint(2, 3))
    assert [entry if entry == "sep" else entry.text() for entry in menu.items] == [
        "打开窗口", "关闭窗口", "设置...", "sep",
        "启用", "禁用", "sep",
        "插件详情", "查看 README", "打开日志", "sep", "一键授权控制权限",
        "sep", "导出插件数据…", "导入插件数据…",
    ]
    acts = _actions(menu)
    assert acts[0].isEnabled() is True and acts[1].isEnabled() is False
    assert acts[3].isEnabled() is False and acts[4].isEnabled() is True

    calls = []
    handlers = [
        ("open", "demo"), ("close", "demo"), ("settings", "demo"),
        ("toggle", "demo", True), ("toggle", "demo", False),
        ("info", "demo"), ("readme", "demo"), ("log", "demo"), ("auth", "demo"),
        ("export", "demo"), ("import", "demo"),
    ]
    monkeypatch.setattr(w, "_toggle_plugin",
                        lambda name, enabled: calls.append(("toggle", name, enabled)))
    monkeypatch.setattr(w, "_open_plugin_info",
                        lambda name: calls.append(("info", name)))
    labels = {
        "_open_plugin_window": "open", "_close_plugin_window": "close",
        "_open_plugin_log": "log", "_open_plugin_readme": "readme",
        "_authorize_plugin_controls": "auth",
        "_open_plugin_settings": "settings",
        "_export_single_plugin_data": "export",
        "_import_single_plugin_data": "import",
    }
    for name, label in labels.items():
        monkeypatch.setattr(w, name, lambda n, label=label: calls.append((label, n)))

    for index, act in enumerate(acts):
        act.setEnabled(True)
        act.triggered.emit()
        assert calls[-1] == handlers[index]
    assert len(calls) == len(acts)
    assert ("toggle", "demo", True) in calls
    assert ("toggle", "demo", False) in calls
    assert calls[-1] == ("import", "demo")


def test_context_menu_disabled_and_closed_and_ready_tab(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "demo", enabled=False,
                    lifecycle=PluginLifecycle.STOPPED)
    _install(w, qtbot, {"demo": p})
    menus = _capture_menu(monkeypatch)
    from PySide6.QtWidgets import QListWidgetItem
    item = QListWidgetItem("demo")
    item.setData(Qt.ItemDataRole.UserRole, "demo")
    w._list.addItem(item)
    monkeypatch.setattr(w._list, "itemAt", lambda p: item)
    w._on_list_context_menu(QPoint(0, 0))
    acts = _actions(menus[0])
    assert len(acts) == 10
    assert acts[0].isEnabled() is False and acts[1].isEnabled() is False
    assert acts[3].isEnabled() is True and acts[4].isEnabled() is False

    p.lifecycle = PluginLifecycle.READY
    p.is_enabled = True
    p.widget = None
    w._closed_plugins.add("demo")
    menus.clear()
    w._on_list_context_menu(QPoint(0, 0))
    acts = _actions(menus[0])
    assert acts[0].isEnabled() is True
    assert acts[1].isEnabled() is False

    w._closed_plugins.clear()
    w._tab_widget.add_detachable_tab(p.ensure_widget(), "demo")
    menus.clear()
    w._on_list_context_menu(QPoint(0, 0))
    acts = _actions(menus[0])
    assert acts[0].isEnabled() is False
    assert acts[1].isEnabled() is True

    w._tab_widget.removeTab(0)
    w._tab_widget._detached_windows["demo"] = SimpleNamespace()
    menus.clear()
    w._on_list_context_menu(QPoint(0, 0))
    assert _actions(menus[0])[1].isEnabled() is True
    del w._tab_widget._detached_windows["demo"]


def test_authorize_plugin_controls_branches(qtbot, monkeypatch):
    w = shell(qtbot)
    p = make_plugin(qtbot, "demo")
    _install(w, qtbot, {"demo": p})
    calls = []
    auth = SimpleNamespace(
        authorize=lambda cmd, name: calls.append((cmd, name)),
        save=lambda: calls.append("save"))
    monkeypatch.setattr(mw.ControlAuthorizationManager, "instance",
                        staticmethod(lambda: auth))

    w._authorize_plugin_controls("missing")
    p.lifecycle = PluginLifecycle.NEW
    w._authorize_plugin_controls("demo")
    assert calls == []

    p.lifecycle = PluginLifecycle.READY
    w._authorize_plugin_controls("demo")
    assert calls == []

    required = [object, dict]
    p.info.required_controls = required
    w._authorize_plugin_controls("demo")
    assert calls == [(object, "demo"), (dict, "demo"), "save"]
    assert w.tr("已授权 {n} 个控制命令给插件 {name}").format(
        n=2, name="demo") in w._operation_notice.text()


def test_toggle_plugin_enable_and_disable(qtbot, monkeypatch, tmp_path):
    from plugin_manager.plugin_state import PluginState, PluginStateManager

    w = shell(qtbot)
    p = make_plugin(qtbot, "demo")
    state_file = tmp_path / "states.json"
    state = PluginStateManager(state_file)
    state.set("demo", PluginState(enabled=False, show_window=False))
    state.save()
    manager, _ = attach_list_state(w, qtbot, {"demo": p}, state)
    calls = []
    manager.enable_plugin = lambda name: calls.append(("enable", name))
    manager.disable_plugin = lambda name: calls.append(("disable", name))
    monkeypatch.setattr(w, "_remove_plugin_window",
                        lambda name: calls.append(("remove", name)))
    monkeypatch.setattr(w, "_refresh_plugin_list", lambda: calls.append("refresh"))
    reloaded = PluginStateManager(state_file)
    w._toggle_plugin("demo", True)
    reloaded.load()
    assert reloaded.get("demo").enabled is True

    w._toggle_plugin("demo", False)
    reloaded.load()
    assert reloaded.get("demo").enabled is False
    assert reloaded.get("demo").show_window is False
    assert calls == [
        ("enable", "demo"), "refresh",
        ("remove", "demo"), ("disable", "demo"), "refresh",
    ]
