"""Coverage for config-path helper, detached plugin window and status widget."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from plugin_manager.main_window import (
    ConnectionStatusWidget,
    DetachedPluginWindow,
    _resolve_plugin_config_path,
)
import plugin_manager.app_paths as app_paths
import plugin_manager.main_window as mw


@pytest.fixture(autouse=True)
def offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mw, "action_icon",
                        lambda _name: QIcon(QPixmap(16, 16)))


def _mouse(kind, local, global_pos, buttons, button=Qt.MouseButton.NoButton):
    return QMouseEvent(
        kind, QPointF(local), QPointF(global_pos), button, buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def test_resolve_config_path_none_and_missing_other_info():
    assert _resolve_plugin_config_path(None) is None
    assert _resolve_plugin_config_path(
        SimpleNamespace(other_info=None)) is None


def test_resolve_config_path_uses_explicit_attribute():
    expected = Path("explicit/config.json")
    plugin = SimpleNamespace(other_info=object(), config_file_path=expected)
    assert _resolve_plugin_config_path(plugin) is expected


def test_resolve_config_path_falls_back_to_plugin_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: tmp_path)
    plugin = SimpleNamespace(other_info=object(),
                             info=SimpleNamespace(name="demo"))
    assert _resolve_plugin_config_path(plugin) == (
        tmp_path / "plugin_data" / "SimpleNamespace" / "demo" / "config.json"
    )


def test_resolve_config_path_swallows_errors(monkeypatch):
    import plugin_manager.app_paths as app_paths

    def boom(_plugin_cls):
        raise RuntimeError("no data dir")

    monkeypatch.setattr(app_paths, "get_plugin_data_dir", boom)
    plugin = SimpleNamespace(other_info=object(), info=SimpleNamespace(name="demo"))
    assert _resolve_plugin_config_path(plugin) is None


def test_detached_window_init_parents_widget_and_sets_title(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    dialog = DetachedPluginWindow("Alpha", widget)
    qtbot.addWidget(dialog)

    assert "Alpha" in dialog.windowTitle()
    assert dialog._plugin_name == "Alpha"
    assert dialog._widget is widget
    assert widget.parent() is dialog
    assert dialog.layout().count() == 2
    assert dialog.layout().itemAt(1).widget() is widget
    assert widget.isVisible() or not widget.isHidden()
    dialog.show()
    assert widget.isVisible()


def test_detached_window_start_drag_tracks_offset(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    dialog = DetachedPluginWindow("Alpha", widget)
    qtbot.addWidget(dialog)
    dialog.show()
    pos = QPoint(dialog.x() + 12, dialog.y() + 9)

    dialog.start_drag(pos)

    assert dialog._dragging is True
    assert dialog._drag_offset == QPoint(12, 9)
    dialog.releaseMouse()


def test_detached_window_mouse_press_move_release(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    dialog = DetachedPluginWindow("Alpha", widget)
    qtbot.addWidget(dialog)
    dialog.show()
    before = dialog.pos()

    press = _mouse(QEvent.Type.MouseButtonPress, QPoint(5, 5),
                   before + QPoint(10, 10), Qt.MouseButton.LeftButton,
                   Qt.MouseButton.LeftButton)
    dialog.mousePressEvent(press)
    assert dialog._dragging is True
    assert dialog._drag_offset == QPoint(10, 10)

    target = before + QPoint(70, 55)
    move = _mouse(QEvent.Type.MouseMove, QPoint(5, 5), target,
                  Qt.MouseButton.LeftButton)
    dialog.mouseMoveEvent(move)
    assert dialog.pos() == target - QPoint(10, 10)

    release = _mouse(QEvent.Type.MouseButtonRelease, QPoint(5, 5), target,
                     Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
    dialog.mouseReleaseEvent(release)
    assert dialog._dragging is False


def test_detached_window_ignores_non_left_or_inactive_drag(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    dialog = DetachedPluginWindow("Alpha", widget)
    qtbot.addWidget(dialog)
    dialog.show()
    before = dialog.pos()

    right_press = _mouse(QEvent.Type.MouseButtonPress, QPoint(5, 5), before,
                         Qt.MouseButton.RightButton, Qt.MouseButton.RightButton)
    dialog.mousePressEvent(right_press)
    assert dialog._dragging is False

    move = _mouse(QEvent.Type.MouseMove, QPoint(5, 5), before + QPoint(40, 40),
                  Qt.MouseButton.NoButton)
    dialog.mouseMoveEvent(move)
    assert dialog.pos() == before

    right_release = _mouse(QEvent.Type.MouseButtonRelease, QPoint(5, 5), before,
                           Qt.MouseButton.NoButton, Qt.MouseButton.RightButton)
    dialog._dragging = True
    dialog.mouseReleaseEvent(right_release)
    assert dialog._dragging is True


def test_detached_window_close_emits_and_blocked_close_does_not(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    dialog = DetachedPluginWindow("Alpha", widget)
    qtbot.addWidget(dialog)
    seen = []
    dialog.close_requested.connect(seen.append)
    dialog.show()
    dialog.close()
    assert seen == ["Alpha"]

    blocked = DetachedPluginWindow("Beta", QWidget())
    qtbot.addWidget(blocked)
    blocked_seen = []
    blocked.blockSignals(True)
    blocked.close_requested.connect(blocked_seen.append)
    blocked.show()
    blocked.close()
    assert blocked_seen == []


def test_connection_status_widget_all_combinations(qtbot):
    widget = ConnectionStatusWidget("tcp://127.0.0.1:5555")
    qtbot.addWidget(widget)
    assert widget._endpoint == "tcp://127.0.0.1:5555"
    assert "未连接" in widget._status_label.text()
    assert widget._reconnect_label.text() == ""

    widget.set_status(True, 0)
    assert "已连接" in widget._status_label.text()
    assert "green" in widget._status_label.styleSheet()
    assert widget._reconnect_label.isHidden()

    widget.set_status(True, 3)
    assert "3" in widget._reconnect_label.text()
    assert not widget._reconnect_label.isHidden()

    widget.set_status(False, 2)
    assert "未连接" in widget._status_label.text()
    assert "red" in widget._status_label.styleSheet()
    assert "2" in widget._reconnect_label.text()
    assert not widget._reconnect_label.isHidden()

    widget.set_status(False, 0)
    assert widget._reconnect_label.isHidden()


def test_connection_status_widget_with_parent(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    widget = ConnectionStatusWidget("inproc://x", parent)
    qtbot.addWidget(widget)
    assert widget.parent() is parent
    assert any(isinstance(widget.layout().itemAt(i).widget(), QLabel)
               for i in range(widget.layout().count()))
