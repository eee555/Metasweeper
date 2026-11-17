"""插件标签右键菜单及视图生命周期回归测试。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QTimer, QTranslator, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from plugin_manager.main_window import DetachableTabWidget, PluginManagerWindow
from plugin_manager.plugin_state import PluginState, PluginStateManager
from plugin_sdk.plugin_base import PluginLifecycle, WindowMode


def compile_catalog(ts: Path, qm: Path) -> Path:
    """用 pyside6-lrelease 把 .ts 编译成 .qm（.qm 是构建产物，不入库）。"""
    name = "pyside6-lrelease.exe" if sys.platform == "win32" else "pyside6-lrelease"
    python_dir = Path(sys.executable).parent
    compiler = next(path for path in (python_dir / name, python_dir / "Scripts" / name)
                    if path.is_file())
    subprocess.run([str(compiler), str(ts), "-qm", str(qm)], check=True,
                   capture_output=True)
    return qm


@pytest.fixture
def window(qtbot):
    manager = PluginManagerWindow.__new__(PluginManagerWindow)
    manager._tab_widget = DetachableTabWidget()
    qtbot.addWidget(manager._tab_widget)
    manager._tab_widget.resize(800, 300)
    manager._tab_widget.show()
    manager._tab_widget.tab_close_requested.connect(manager._on_tab_closed)
    manager._closed_plugins = set()
    manager._manager = SimpleNamespace(plugins={})
    manager._state_mgr = PluginStateManager(":memory:")
    manager._get_plugin_default_state = lambda name: None
    manager._effective_state = lambda name: manager._state_mgr.get_effective(name, None)
    return manager


def add_plugin(window, name):
    widget = QWidget()
    state = PluginState(show_window=True, window_mode=WindowMode.TAB)
    plugin = SimpleNamespace(name=name, lifecycle=PluginLifecycle.READY,
                             is_enabled=True, widget=widget, plugin_icon=None,
                             close_calls=0)

    def close_widget():
        plugin.close_calls += 1
        old = plugin.widget
        plugin.widget = None
        old.deleteLater()

    def ensure_widget():
        if plugin.widget is None:
            plugin.widget = QWidget()
        return plugin.widget

    plugin.close_widget = close_widget
    plugin.ensure_widget = ensure_widget
    window._manager.plugins[name] = plugin
    window._state_mgr.set(name, state)
    window._tab_widget.add_detachable_tab(widget, name)
    return plugin, widget, state


def open_menu(monkeypatch, tabs, index, operation=None, before_trigger=None):
    captured = {}

    def execute(_pos):
        captured.update({key: action.isEnabled()
                         for key, action in tabs._tab_menu_actions.items()})
        if before_trigger:
            before_trigger()
        if operation:
            tabs._tab_menu_actions[operation].trigger()
        return None

    monkeypatch.setattr(tabs._tab_menu, "exec", execute)
    pos = tabs.tabBar().tabRect(index).center() if index >= 0 else QPoint(799, 10)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos,
                              tabs.tabBar().mapToGlobal(pos))
    QApplication.sendEvent(tabs.tabBar(), event)
    return captured


@pytest.mark.parametrize(("operation", "closed", "remaining"), [
    ("current", ["B"], ["A", "C", "D"]),
    ("left", ["A"], ["B", "C", "D"]),
    ("right", ["C", "D"], ["A", "B"]),
    ("others", ["A", "C", "D"], ["B"]),
    ("all", ["A", "B", "C", "D"], []),
])
def test_menu_closes_actual_views_and_preserves_plugin_state(
    window, monkeypatch, operation, closed, remaining,
):
    plugins = {name: add_plugin(window, name) for name in "ABCD"}
    tabs = window._tab_widget
    tabs.setCurrentIndex(3)  # 右键 B，而非当前选中的 D
    enabled = open_menu(monkeypatch, tabs, 1, operation)
    assert all(enabled.values())
    assert [tabs.tabText(i) for i in range(tabs.count())] == remaining
    assert window._closed_plugins == set(closed)
    for name, (plugin, widget, state) in plugins.items():
        assert plugin.close_calls == int(name in closed)
        assert plugin.is_enabled
        assert window._state_mgr.get(name) == state
        assert (plugin.widget is None) == (name in closed)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    for name, (_, widget, _) in plugins.items():
        assert shiboken6.isValid(widget) == (name not in closed)
    if closed:
        name = closed[0]
        window._open_plugin_window(name)
        assert plugins[name][0].widget is not None
        assert tabs.indexOf(plugins[name][0].widget) >= 0
        assert name not in window._closed_plugins


def test_menu_boundaries_empty_space_and_icons(window, monkeypatch):
    tabs = window._tab_widget
    assert open_menu(monkeypatch, tabs, -1) == {}
    for name in "ABC":
        add_plugin(window, name)
    assert open_menu(monkeypatch, tabs, 0) == {
        "current": True, "left": False, "right": True, "others": True, "all": True}
    assert open_menu(monkeypatch, tabs, 2) == {
        "current": True, "left": True, "right": False, "others": True, "all": True}
    assert all(not action.icon().isNull() and action.isIconVisibleInMenu()
               for action in tabs._tab_menu_actions.values())
    open_menu(monkeypatch, tabs, 1, "others")
    assert open_menu(monkeypatch, tabs, 0) == {
        "current": True, "left": False, "right": False, "others": False, "all": True}
    assert open_menu(monkeypatch, tabs, -1) == {}


def test_menu_survives_target_moving_or_disappearing(window, monkeypatch):
    for name in "ABC":
        add_plugin(window, name)
    tabs = window._tab_widget
    open_menu(monkeypatch, tabs, 1, "current",
              lambda: tabs.tabBar().moveTab(1, 0))
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["A", "C"]
    assert window._closed_plugins == {"B"}
    open_menu(monkeypatch, tabs, 0, "all",
              lambda: tabs._on_tab_close_requested(0))
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["C"]


def test_batch_snapshot_handles_reordering_and_removed_views(window, monkeypatch):
    for name in "ABCD":
        add_plugin(window, name)
    tabs = window._tab_widget

    def on_close(name):
        if name == "A":
            tabs.tabBar().moveTab(0, tabs.count() - 1)
            tabs._on_tab_close_requested(tabs.indexOf(window._manager.plugins["C"].widget))
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    tabs.tab_close_requested.connect(on_close)
    open_menu(monkeypatch, tabs, 1, "all")
    assert tabs.count() == 0
    assert window._closed_plugins == set("ABCD")
    assert all(plugin.close_calls == 1 for plugin in window._manager.plugins.values())


def test_detached_windows_are_not_closed(window, monkeypatch):
    add_plugin(window, "A")
    detached, widget, state = add_plugin(window, "B")
    tabs = window._tab_widget
    tabs._detach_tab(1, "B")
    detached_window = tabs._detached_windows["B"]
    open_menu(monkeypatch, tabs, 0, "all")
    assert tabs.count() == 0
    assert tabs._detached_windows["B"] is detached_window
    assert detached.widget is widget and detached.close_calls == 0
    assert window._state_mgr.get("B") == state
    tabs._attach_tab("B")
    assert tabs.widget(0) is widget


def test_actual_popup_supports_keyboard(window):
    add_plugin(window, "A")
    add_plugin(window, "B")
    tabs = window._tab_widget

    def use_keyboard():
        QTest.keyClick(tabs._tab_menu, Qt.Key.Key_Down)
        QTest.keyClick(tabs._tab_menu, Qt.Key.Key_Return)

    QTimer.singleShot(0, use_keyboard)
    QTimer.singleShot(1000, tabs._tab_menu.close)
    tabs._show_tab_context_menu(tabs.tabBar().tabRect(1).center())
    assert window._closed_plugins == {"B"}
    assert tabs.count() == 1 and tabs.tabText(0) == "A"


@pytest.mark.parametrize(("locale", "expected"), [
    ("en_US", ["Close Tab", "Close Tabs to the Left", "Close Tabs to the Right", "Close Other Tabs", "Close All Tabs"]),
    ("de_DE", ["Aktuellen Tab schließen", "Tabs links schließen", "Tabs rechts schließen", "Übrige Registerkarten schließen", "Sämtliche Registerkarten schließen"]),
    ("ja_JP", ["このタブを閉じる", "左側のタブを閉じる", "右側のタブを閉じる", "他のタブを閉じる", "すべてのタブを閉じる"]),
    ("pl_PL", ["Zamknij bieżącą kartę", "Zamknij karty po lewej", "Zamknij karty po prawej", "Zamknij pozostałe karty", "Zamknij wszystkie karty"]),
])
def test_compiled_translation_updates_existing_menu(window, qapp, tmp_path, locale, expected):
    tabs = window._tab_widget
    translator = QTranslator()
    ts = Path(__file__).resolve().parents[2] / "src" / "ui" / f"{locale}.ts"
    qm = compile_catalog(ts, tmp_path / f"{locale}.qm")
    assert translator.load(str(qm))
    qapp.installTranslator(translator)
    try:
        qapp.processEvents()
        assert [action.text() for action in tabs._tab_menu.actions()] == expected
    finally:
        qapp.removeTranslator(translator)
        qapp.processEvents()
    assert tabs._tab_menu_actions["current"].text() == "关闭当前标签页"
