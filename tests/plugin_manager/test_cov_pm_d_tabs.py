"""Coverage for detachable tab bar / widget lifecycle."""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

import pytest

from plugin_manager.main_window import (
    DetachableTabWidget,
    _DetachableTabBar,
)
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


@pytest.fixture
def tabs(qtbot):
    widget = DetachableTabWidget()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_init_installs_custom_bar_and_connections(tabs, qtbot):
    assert isinstance(tabs.tabBar(), _DetachableTabBar)
    assert tabs._tab_bar is tabs.tabBar()
    assert tabs.isMovable()
    assert tabs.tabsClosable()
    assert tabs._detached_windows == {}
    seen = []
    tabs.tab_close_requested.connect(seen.append)
    tabs._on_tab_close_requested(0)
    assert seen == []


def test_add_detachable_tab_with_and_without_icon(tabs, qtbot):
    plain = QWidget()
    qtbot.addWidget(plain)
    icon = QIcon(QPixmap(16, 16))
    fancy = QWidget()
    qtbot.addWidget(fancy)

    assert tabs.add_detachable_tab(plain, "Plain") == 0
    assert tabs.add_detachable_tab(fancy, "Fancy", icon) == 1
    assert tabs.tabText(0) == "Plain"
    assert tabs.tabText(1) == "Fancy"
    assert not tabs.tabIcon(0).isNull() or tabs.tabIcon(0).isNull()
    assert tabs.tabIcon(1).cacheKey() == icon.cacheKey()


def test_bar_mouse_press_records_start_and_ignores_right_button(tabs):
    bar = tabs._tab_bar
    tabs.add_detachable_tab(QWidget(), "Alpha")
    center = bar.mapToGlobal(bar.tabRect(0).center())

    bar.mousePressEvent(_mouse(
        QEvent.Type.MouseButtonPress, QPoint(5, 5), center,
        Qt.MouseButton.RightButton, Qt.MouseButton.RightButton))
    assert bar._drag_start_pos is None

    bar.mousePressEvent(_mouse(
        QEvent.Type.MouseButtonPress, QPoint(5, 5), center,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    assert bar._drag_start_pos == center


def test_bar_drag_threshold_and_vertical_detach_signal(tabs):
    bar = tabs._tab_bar
    tabs.add_detachable_tab(QWidget(), "Alpha")
    center = bar.mapToGlobal(bar.tabRect(0).center())
    seen = []
    bar.drag_initiated.connect(lambda i, n, p: seen.append((i, n, p)))

    bar.mousePressEvent(_mouse(
        QEvent.Type.MouseButtonPress, QPoint(5, 5), center,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    # Right button does not keep left pressed: no signal.
    bar.mouseMoveEvent(_mouse(
        QEvent.Type.MouseMove, QPoint(5, 5), center + QPoint(0, 100),
        Qt.MouseButton.RightButton))
    assert seen == []

    # Small left-drag below threshold: no signal.
    bar.mouseMoveEvent(_mouse(
        QEvent.Type.MouseMove, QPoint(5, 5), center + QPoint(2, 2),
        Qt.MouseButton.LeftButton))
    assert seen == []

    # Large horizontal-only drag passes distance but fails vertical delta.
    bar.mouseMoveEvent(_mouse(
        QEvent.Type.MouseMove, QPoint(5, 5), center + QPoint(100, 0),
        Qt.MouseButton.LeftButton))
    assert seen == []

    target = center + QPoint(0, QApplication.startDragDistance() * 4)
    bar.mouseMoveEvent(_mouse(
        QEvent.Type.MouseMove, QPoint(5, 5), target,
        Qt.MouseButton.LeftButton))
    assert len(seen) == 1
    assert seen[0][0:2] == (0, "Alpha")
    assert seen[0][2] == target
    assert bar._drag_start_pos is None


def test_bar_drag_on_invalid_tab_and_no_start(tabs):
    bar = tabs._tab_bar
    seen = []
    bar.drag_initiated.connect(lambda *args: seen.append(args))

    # No press recorded.
    bar.mouseMoveEvent(_mouse(
        QEvent.Type.MouseMove, QPoint(5, 5), QPoint(5, 200),
        Qt.MouseButton.LeftButton))
    assert seen == []

    # Press far outside tab area, then drag down.
    outside = QPoint(5000, 5000)
    bar.mousePressEvent(_mouse(
        QEvent.Type.MouseButtonPress, QPoint(5, 5), outside,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    bar.mouseMoveEvent(_mouse(
        QEvent.Type.MouseMove, QPoint(5, 5), outside + QPoint(0, 100),
        Qt.MouseButton.LeftButton))
    assert seen == []


def test_bar_double_click_valid_invalid_and_right_button(tabs):
    bar = tabs._tab_bar
    tabs.add_detachable_tab(QWidget(), "Alpha")
    center_local = bar.tabRect(0).center()
    center_global = bar.mapToGlobal(center_local)
    seen = []
    bar.drag_initiated.connect(lambda i, n, p: seen.append((i, n, p)))

    bar.mouseDoubleClickEvent(_mouse(
        QEvent.Type.MouseButtonDblClick, center_local, center_global,
        Qt.MouseButton.RightButton, Qt.MouseButton.RightButton))
    assert seen == []

    bar.mouseDoubleClickEvent(_mouse(
        QEvent.Type.MouseButtonDblClick, QPoint(5000, 5000), center_global,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    assert seen == []

    bar.mouseDoubleClickEvent(_mouse(
        QEvent.Type.MouseButtonDblClick, center_local, center_global,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    assert len(seen) == 1
    assert seen[0][0:2] == (0, "Alpha")


def test_detach_attach_close_cycle_end_to_end(tabs, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    icon = QIcon(QPixmap(16, 16))
    tabs.add_detachable_tab(widget, "Alpha", icon)
    tabs.show()

    detached_seen, attach_seen, close_seen, window_close_seen = [], [], [], []
    tabs.tab_detached.connect(detached_seen.append)
    tabs.tab_attach_requested.connect(attach_seen.append)
    tabs.tab_close_requested.connect(close_seen.append)
    tabs.window_close_requested.connect(window_close_seen.append)

    tabs._on_drag_from_bar(0, "Alpha", QPoint(300, 250))
    assert tabs.count() == 0
    assert detached_seen == ["Alpha"]
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    assert window.isVisible()
    assert window._dragging is True
    assert window.windowIcon().cacheKey() == icon.cacheKey()
    assert window.layout().itemAt(1).widget() is widget
    window.releaseMouse()

    tabs._attach_tab("Alpha")
    assert tabs.count() == 1
    assert tabs.tabText(0) == "Alpha"
    assert tabs.widget(0) is widget
    assert attach_seen == ["Alpha"]
    assert tabs._detached_windows == {}

    tabs._on_tab_close_requested(0)
    assert tabs.count() == 0
    assert close_seen == ["Alpha"]


def test_detach_without_position_and_invalid_index(tabs, qtbot):
    tabs._detach_tab(-1, "Missing")
    assert tabs._detached_windows == {}

    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    assert window.isVisible()
    assert window._dragging is False
    assert tabs.count() == 0


def test_attach_missing_and_layout_failure_cleanup(tabs, qtbot):
    tabs._attach_tab("Missing")

    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    window.layout().takeAt(1)
    widget.setParent(tabs)
    window.setLayout(None)
    tabs._attach_tab("Alpha")
    assert "Alpha" not in tabs._detached_windows
    assert tabs.count() == 0
    widget.setParent(None)


def test_attach_cleans_up_when_layout_item_is_not_a_widget(tabs, qtbot):
    from PySide6.QtWidgets import QSpacerItem, QSizePolicy

    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    layout = window.layout()
    layout.takeAt(1)
    widget.setParent(None)
    spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    layout.insertItem(1, spacer)

    tabs._attach_tab("Alpha")
    assert "Alpha" not in tabs._detached_windows
    assert tabs.count() == 0


def test_attach_cleans_up_when_layout_has_no_second_item(tabs, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    layout = window.layout()
    layout.takeAt(1)
    widget.setParent(None)
    # Layout still has the hint label at index 0, but no second item.
    tabs._attach_tab("Alpha")
    assert "Alpha" not in tabs._detached_windows
    assert tabs.count() == 0


def test_attach_cleans_up_when_second_layout_item_is_none(tabs, qtbot, monkeypatch):
    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    fake_layout = SimpleNamespace(count=lambda: 2, itemAt=lambda _i: None)
    monkeypatch.setattr(window, "layout", lambda: fake_layout)

    tabs._attach_tab("Alpha")
    assert "Alpha" not in tabs._detached_windows
    assert tabs.count() == 0
    widget.setParent(None)


def test_attach_without_icon_skips_icon_restore(tabs, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    window._icon = None
    tabs._attach_tab("Alpha")
    assert tabs.count() == 1
    assert tabs.tabIcon(0).isNull()


def test_attach_inserts_before_existing_same_name_tab(tabs, qtbot):
    original = QWidget()
    qtbot.addWidget(original)
    tabs.add_detachable_tab(original, "Alpha")
    tabs._detach_tab(0, "Alpha")
    detached = tabs._detached_windows["Alpha"]
    qtbot.addWidget(detached)
    icon = QIcon(QPixmap(16, 16))
    detached._icon = icon

    replacement = QWidget()
    qtbot.addWidget(replacement)
    tabs.add_detachable_tab(replacement, "Alpha")
    seen = []
    tabs.tab_attach_requested.connect(seen.append)

    tabs._attach_tab("Alpha")

    assert tabs.count() == 2
    assert tabs.widget(0) is original
    assert tabs.widget(1) is replacement
    assert seen == []


def test_cleanup_detached_blocks_close_signal(tabs, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    seen = []
    tabs.window_close_requested.connect(seen.append)

    tabs._cleanup_detached("Alpha")
    assert "Alpha" not in tabs._detached_windows
    assert seen == []
    assert window.signalsBlocked() is True

    tabs._cleanup_detached("Alpha")


def test_detached_window_close_request_forwards_signal(tabs, qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    tabs.add_detachable_tab(widget, "Alpha")
    tabs._detach_tab(0, "Alpha")
    window = tabs._detached_windows["Alpha"]
    qtbot.addWidget(window)
    seen = []
    tabs.window_close_requested.connect(seen.append)

    window.close()

    assert seen == ["Alpha"]


def test_on_tab_close_requested_ignores_empty_index(tabs):
    seen = []
    tabs.tab_close_requested.connect(seen.append)
    tabs._on_tab_close_requested(0)
    assert seen == []
    assert tabs.count() == 0
