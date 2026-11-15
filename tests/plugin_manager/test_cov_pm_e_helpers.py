"""PluginManagerWindow coverage helpers: never construct the real app."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QSystemTrayIcon, QWidget

import plugin_manager.main_window as mw
from plugin_manager.main_window import DetachableTabWidget, PluginManagerWindow
from plugin_manager.plugin_state import PluginStateManager
from plugin_sdk.plugin_base import PluginLifecycle


@pytest.fixture(autouse=True)
def _offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


class _Signals(QObject):
    ready = Signal(object)
    stopped = Signal(object)


def shell(qtbot) -> PluginManagerWindow:
    """A QMainWindow-initialized shell with only light-weight state attached."""
    w = PluginManagerWindow.__new__(PluginManagerWindow)
    QMainWindow.__init__(w)
    # qtbot closes registered widgets at teardown; avoid a real confirmation
    # dialog from closeEvent (which would block forever offscreen).
    w.closeEvent = lambda event: event.accept()
    qtbot.addWidget(w)
    return w


def make_plugin(qtbot, name="plug", lifecycle=PluginLifecycle.READY,
                enabled=True, widget=None, info=None, other_info=None,
                plugin_dir=None):
    if widget is None:
        widget = QWidget()
    qtbot.addWidget(widget)
    p = SimpleNamespace(
        name=name,
        info=info or SimpleNamespace(
            name=name, enabled=enabled, show_window=True,
            window_mode="tab", log_level="DEBUG", required_controls=[],
        ),
        is_enabled=enabled,
        lifecycle=lifecycle,
        widget=widget,
        plugin_icon=QIcon(),
        other_info=other_info,
        plugin_dir=plugin_dir,
        set_log_level=lambda level: None,
        get_readme_text=lambda: "# readme",
        save_config=lambda: None,
        signals=_Signals(),
        close_calls=0,
        log_levels=[],
    )
    p.ready = p.signals.ready
    p.stopped = p.signals.stopped
    p.set_log_level = lambda level: p.log_levels.append(level)

    def _ensure_widget():
        if p.widget is None:
            p.widget = QWidget()
            qtbot.addWidget(p.widget)
        return p.widget

    def _close_widget():
        p.close_calls += 1
        old = p.widget
        p.widget = None
        if old is not None:
            old.hide()
            old.setParent(None)
            old.deleteLater()

    p.ensure_widget = _ensure_widget
    p.close_widget = _close_widget
    return p


def attach_list_state(w, qtbot, plugins=None, state_mgr=None):
    """Install real QListWidget + tab widget; return (manager, state manager)."""
    from PySide6.QtWidgets import QListWidget

    w._list = QListWidget()
    qtbot.addWidget(w._list)
    w._tab_widget = DetachableTabWidget()
    qtbot.addWidget(w._tab_widget)
    w._closed_plugins = set()
    w._state_mgr = state_mgr or PluginStateManager(":memory:")
    w._manager = SimpleNamespace(plugins=dict(plugins or {}),
                                 enable_plugin=lambda name: None,
                                 disable_plugin=lambda name: None)
    return w._manager, w._state_mgr


def make_manager(tmp_path, plugins=None, **overrides):
    sm = PluginStateManager(tmp_path / "states.json")
    sm.load()
    mgr = SimpleNamespace(
        state_manager=sm,
        plugins=dict(plugins or {}),
        connection_endpoint="tcp://127.0.0.1:5555",
        is_connected=True,
        reconnect_count=0,
        stop=lambda: None,
        client=None,
        main_window=None,
    )
    for key, value in overrides.items():
        setattr(mgr, key, value)
    return mgr


def real_window(qtbot, monkeypatch, tmp_path, plugins=None, tray=True):
    """Full real PluginManagerWindow.__init__, with all I/O sandboxed."""
    monkeypatch.setattr(mw, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(mw, "SettingsManager", lambda data_dir: SimpleNamespace(
        file_log_level="DEBUG", viewer_log_level="INFO",
        viewer_auto_scroll=True, viewer_show_source=False,
    ))
    if tray:
        monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable",
                            staticmethod(lambda: True))
    w = PluginManagerWindow(make_manager(tmp_path, plugins))
    qtbot.addWidget(w, before_close_func=lambda widget: (
        widget._timer.stop(),
        widget._tray_icon.hide() if widget._tray_icon is not None else None,
        setattr(widget, "closeEvent", lambda event: event.accept()),
    ))
    return w
