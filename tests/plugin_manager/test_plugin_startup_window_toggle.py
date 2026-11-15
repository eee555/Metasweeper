"""插件「启动时显示窗口」开关与窗口实例生命周期回归测试。

按「触发源」区分（配置与窗口生命周期双向解耦，但窗口自身关闭仍析构实例）：
- 程序化回填开关状态不触发 toggled 信号回环
- 手动打开窗口不回写 show_window / window_mode 启动配置
- 设置页把开关从开改关并保存：已有窗口与 widget 仍存在（配置不驱动窗口）
- 关闭 Tab / 关闭独立窗口：析构 widget 实例，但不回写配置
- 启动 show_window=False：释放已创建的实例（只读配置，不回写）
- 反复关闭后再打开：每轮都创建全新 widget 实例，不复用已 deleteLater 的对象
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget

from plugin_manager.main_window import (
    DetachableTabWidget,
    PluginManagerWindow,
    PluginSettingsDialog,
)
from plugin_manager.plugin_state import PluginState, PluginStateManager
from plugin_sdk.plugin_base import PluginLifecycle, WindowMode


@pytest.fixture
def app(qtbot, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return qtbot


@pytest.fixture
def manager_window(app):
    """构造仅包含窗口管理所需最小状态的主窗口壳。"""
    window = PluginManagerWindow.__new__(PluginManagerWindow)
    window._tab_widget = DetachableTabWidget()
    window._closed_plugins = set()
    state_mgr = PluginStateManager(":memory:")
    window._state_mgr = state_mgr
    window._manager = SimpleNamespace(plugins={})

    # __new__ 构造的壳未走 __init__，显式复刻独立窗口关闭的连线。
    window._tab_widget.window_close_requested.connect(
        window._on_detached_window_closed)

    # _apply_saved_states / _effective_state 的最小依赖
    window._get_plugin_default_state = lambda name: None  # type: ignore[method-assign]
    window._effective_state = lambda name: window._state_mgr.get_effective(  # type: ignore[method-assign]
        name, window._get_plugin_default_state(name))
    return window


def _install_plugin(manager_window, name: str, state: PluginState, widget: QWidget):
    """安装一个模拟 BasePlugin 窗口生命周期的桩。

    与 ``plugin_base.close_widget()`` / ``ensure_widget()`` 保持一致：
    close 后置空实例缓存并 deleteLater；再次 ensure 时重新创建新 QWidget，
    绝不复用已析构的 C++ 对象。
    """
    manager_window._state_mgr.set(name, state)
    created_widgets = [widget]
    plugin = SimpleNamespace(
        name=name,
        lifecycle=PluginLifecycle.READY,
        is_enabled=True,
        widget=widget,
        plugin_icon=None,
        close_calls=0,
        created_widgets=created_widgets,
        set_log_level=lambda level: None,
    )

    def _ensure_widget():
        if plugin.widget is None:
            new_widget = QWidget()
            created_widgets.append(new_widget)
            plugin.widget = new_widget
        return plugin.widget

    def _close_widget():
        plugin.close_calls += 1
        old = plugin.widget
        plugin.widget = None
        if old is not None:
            old.deleteLater()

    plugin.ensure_widget = _ensure_widget
    plugin.close_widget = _close_widget
    manager_window._manager.plugins[name] = plugin
    return plugin


def _drain_deletes():
    """派发 DeferredDelete，使 deleteLater 真正析构 C++ 对象。"""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_programmatic_set_checked_does_not_emit_signals(app):
    """对话框初始化时 setChecked 不应触发 toggled。"""
    state = PluginState(show_window=False)
    dialog = PluginSettingsDialog("test", state)
    toggled = []
    dialog._chk_show.toggled.connect(toggled.append)
    assert dialog._chk_show.isChecked() is False
    assert toggled == []

    # 真实用户交互仍然必须发出信号。
    dialog._chk_show.toggle()
    assert toggled == [True]


def test_plugin_settings_uses_plugin_icon_and_falls_back_to_parent(app):
    parent = QWidget()
    parent_icon = QIcon(QPixmap(16, 16))
    parent.setWindowIcon(parent_icon)
    plugin_icon = QIcon(QPixmap(32, 32))
    dialog = PluginSettingsDialog("test", PluginState(), parent=parent,
                                  plugin=SimpleNamespace(plugin_icon=plugin_icon))
    assert dialog.windowIcon().cacheKey() == plugin_icon.cacheKey()

    fallback = PluginSettingsDialog("test", PluginState(), parent=parent)
    assert fallback.windowIcon().cacheKey() == parent_icon.cacheKey()


def test_open_window_does_not_change_startup_toggle(manager_window):
    """手动打开窗口不得写回 show_window / window_mode。"""
    name = "startup-off"
    widget = QWidget()
    state = PluginState(show_window=False, window_mode=WindowMode.TAB)
    _install_plugin(manager_window, name, state, widget)

    manager_window._open_plugin_window(name)

    assert manager_window._state_mgr.get(name) == state
    assert manager_window._state_mgr.get(name).show_window is False
    assert manager_window._tab_widget.count() == 1
    assert name not in manager_window._closed_plugins
    widget.deleteLater()


def test_closing_startup_toggle_never_kills_existing_window(manager_window):
    """模拟设置页把开关从开改为关并保存：已有窗口仍存在、widget 未销毁。"""
    name = "keep-window"
    widget = QWidget()
    state = PluginState(show_window=True, window_mode=WindowMode.TAB)
    plugin = _install_plugin(manager_window, name, state, widget)
    manager_window._open_plugin_window(name)

    new_state = PluginState(show_window=False, window_mode=WindowMode.TAB)
    manager_window._state_mgr.set(name, new_state)
    manager_window._state_mgr.save = lambda: None  # 隔离文件写入

    assert manager_window._tab_widget.count() == 1
    assert manager_window._tab_widget.widget(0) is widget
    assert plugin.widget is widget
    assert plugin.close_calls == 0
    assert manager_window._state_mgr.get(name).show_window is False
    manager_window._tab_widget.removeTab(0)
    widget.deleteLater()


def test_repeated_open_close_destroys_and_recreates_widget(manager_window):
    """C/E 行：重复打开/关闭 3 轮安全；每次关闭析构，每次重新打开创建新实例。"""
    name = "recreate"
    widget = QWidget()
    state = PluginState(show_window=False, window_mode=WindowMode.TAB)
    plugin = _install_plugin(manager_window, name, state, widget)

    seen_ids: set[int] = set()
    for round_no in range(3):
        manager_window._open_plugin_window(name)
        assert manager_window._tab_widget.count() == 1
        current = manager_window._tab_widget.widget(0)
        assert current is plugin.widget
        if round_no > 0:
            # 上一轮已析构，重建必然是全新实例，绝不复用已 deleteLater 的对象。
            assert id(current) not in seen_ids
        seen_ids.add(id(current))

        manager_window._close_plugin_window(name)
        assert manager_window._tab_widget.count() == 0
        assert plugin.widget is None         # 实例缓存已置空
        assert plugin.close_calls == round_no + 1
        _drain_deletes()
        assert not shiboken6.isValid(current)  # 本轮实例已真正释放

    # 全程绝不回写启动偏好。
    assert manager_window._state_mgr.get(name) == state
    assert manager_window._state_mgr.get(name).show_window is False
    assert name in manager_window._closed_plugins
    assert plugin.close_calls == 3


def test_tab_closed_destroys_widget_without_changing_config(manager_window):
    """D 行：用户点标签页 X → 析构实例，但不回写配置。"""
    name = "tab-close"
    widget = QWidget()
    state = PluginState(show_window=True, window_mode=WindowMode.TAB)
    plugin = _install_plugin(manager_window, name, state, widget)
    manager_window._open_plugin_window(name)

    # 模拟 DetachableTabWidget._on_tab_close_requested：先移除标签，再投递信号。
    manager_window._tab_widget.removeTab(0)
    manager_window._on_tab_closed(name)
    _drain_deletes()

    assert manager_window._tab_widget.count() == 0
    assert plugin.widget is None
    assert plugin.close_calls == 1
    assert name in manager_window._closed_plugins
    assert manager_window._state_mgr.get(name) == state
    assert manager_window._state_mgr.get(name).show_window is True
    assert manager_window._state_mgr.get(name).window_mode == WindowMode.TAB
    assert not shiboken6.isValid(widget)


def test_detached_window_close_destroys_widget_without_changing_config(manager_window):
    """E 行：用户直接关闭独立窗口 → 析构实例，但不回写配置。"""
    name = "detached-close"
    widget = QWidget()
    state = PluginState(show_window=True, window_mode=WindowMode.DETACHED)
    plugin = _install_plugin(manager_window, name, state, widget)
    manager_window._open_plugin_window(name)

    assert name in manager_window._tab_widget._detached_windows
    manager_window._close_plugin_window(name)
    _drain_deletes()

    assert manager_window._tab_widget.count() == 0
    assert name not in manager_window._tab_widget._detached_windows
    assert plugin.widget is None
    assert plugin.close_calls == 1
    assert name in manager_window._closed_plugins
    assert manager_window._state_mgr.get(name) == state
    assert manager_window._state_mgr.get(name).show_window is True
    assert manager_window._state_mgr.get(name).window_mode == WindowMode.DETACHED
    assert not shiboken6.isValid(widget)


def test_startup_hidden_state_releases_widget(manager_window):
    """B 行：启动 show_window=False → 释放已创建的实例，只读配置不回写。"""
    name = "hidden-at-start"
    widget = QWidget()
    state = PluginState(show_window=False)
    plugin = _install_plugin(manager_window, name, state, widget)
    # 真实启动时序：initialize() 已同步创建 widget，但此时尚未挂入任何 Tab；
    # _apply_saved_states() 在 _refresh_plugin_list() 之前运行。
    manager_window._apply_saved_states()
    _drain_deletes()

    assert manager_window._tab_widget.count() == 0
    assert name in manager_window._closed_plugins
    assert plugin.widget is None
    assert plugin.close_calls == 1
    assert not shiboken6.isValid(widget)
    assert manager_window._state_mgr.get(name) == state


def test_startup_visible_state_keeps_and_shows_widget(manager_window):
    """B 行：启动 show_window=True → 正常显示已创建的实例，且不回写配置。"""
    name = "visible-at-start"
    widget = QWidget()
    state = PluginState(show_window=True, window_mode=WindowMode.TAB)
    plugin = _install_plugin(manager_window, name, state, widget)
    manager_window._open_plugin_window(name)

    manager_window._apply_saved_states()

    assert manager_window._tab_widget.count() == 1
    assert manager_window._tab_widget.widget(0) is widget
    assert plugin.widget is widget
    assert plugin.close_calls == 0
    assert name not in manager_window._closed_plugins
    assert manager_window._state_mgr.get(name) == state
    manager_window._tab_widget.removeTab(0)
    widget.deleteLater()


def test_detached_window_x_button_destroys_widget(manager_window):
    """用户点独立窗口自身 X：析构实例、清理引用、不嵌回、不回写配置。"""
    name = "window-x"
    widget = QWidget()
    state = PluginState(show_window=True, window_mode=WindowMode.DETACHED)
    plugin = _install_plugin(manager_window, name, state, widget)
    manager_window._open_plugin_window(name)

    t = manager_window._tab_widget
    assert name in t._detached_windows
    detached = t._detached_windows[name]
    # 真实用户关闭：未经 blockSignals，closeEvent 应 emit close_requested。
    detached.close()
    _drain_deletes()

    assert name not in t._detached_windows          # 引用已清理
    assert t.count() == 0                          # 没有嵌回标签页继续持有
    assert plugin.widget is None
    assert plugin.close_calls == 1                 # 真正析构
    assert not shiboken6.isValid(widget)
    assert name in manager_window._closed_plugins
    assert manager_window._state_mgr.get(name) == state
    assert manager_window._state_mgr.get(name).show_window is True
    assert manager_window._state_mgr.get(name).window_mode == WindowMode.DETACHED


def test_programmatic_attach_and_cleanup_do_not_destroy_widget(manager_window):
    """程序化 _attach_tab / _cleanup_detached：不误析构、不误发 close_requested。"""
    name = "programmatic"
    widget = QWidget()
    state = PluginState(show_window=True, window_mode=WindowMode.DETACHED)
    plugin = _install_plugin(manager_window, name, state, widget)
    manager_window._open_plugin_window(name)

    t = manager_window._tab_widget
    spy = []
    t.window_close_requested.connect(spy.append)

    # 约束 2：_open_tab_window 程序化嵌回（_attach_tab）仍可用，
    # widget 保留在 Tab 上、不析构、不误发关闭请求、不回写配置。
    manager_window._open_tab_window(name)

    assert name not in t._detached_windows
    assert t.count() == 1
    assert t.widget(0) is widget
    assert plugin.widget is widget
    assert plugin.close_calls == 0
    assert shiboken6.isValid(widget)
    assert spy == []
    assert manager_window._state_mgr.get(name) == state

    # 约束 3：_cleanup_detached 兜底场景（layout 里的 widget 已先被取走）。
    # blockSignals(True) 让 closeEvent 走默认关闭、不 emit close_requested，
    # 因此不会重入 _remove_plugin_window 造成二次析构或异常。
    t._detach_tab(0, name)
    detached = t._detached_windows[name]
    lay = detached.layout()
    lay.removeWidget(widget)
    widget.setParent(None)          # 摘出子控件，隔离 Qt 父窗口连带销毁语义
    t._cleanup_detached(name)
    _drain_deletes()

    assert name not in t._detached_windows
    assert spy == []                # 程序化 close() 未误发关闭/析构请求
    assert plugin.widget is widget  # 插件仍持有，未被二次析构
    assert plugin.close_calls == 0
    assert shiboken6.isValid(widget)
    assert manager_window._state_mgr.get(name) == state
    widget.deleteLater()
