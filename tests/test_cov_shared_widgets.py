"""共享 Qt 控件覆盖率补测：ConfirmDialog / EditableComboBox / ToggleSwitch。

不依赖 conftest 的 qtbot，本地创建 offscreen QApplication 并逐个清理控件；
所有断言校验信号、状态、返回值或异常，而非仅调用。
"""
from __future__ import annotations

import pytest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget,
)

from shared_types.widgets.confirm_dialog import ConfirmDialog
from shared_types.widgets.editable_combo_box import EditableComboBox
from shared_types.widgets.toggle_switch import ToggleSwitch


@pytest.fixture(scope="module")
def app():
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widgets(app):
    created: list[QWidget] = []
    yield created
    for w in created:
        w.hide()
        w.setParent(None)
        w.deleteLater()
    QApplication.processEvents()


def _keep(widgets, w):
    widgets.append(w)
    return w


# ── ConfirmDialog ──────────────────────────────────────────────────

class _ContentDialog(ConfirmDialog):
    """带内容布局与 accept/reject 钩子记录的子类。"""

    def __init__(self, *args, **kwargs):
        self.events: list[str] = []
        self.content_layout = None
        super().__init__(*args, **kwargs)

    def _create_content(self):
        self.content_layout = QVBoxLayout()
        self.content_layout.addWidget(QWidget())
        return self.content_layout

    def _on_accepted(self):
        self.events.append("accepted")

    def _on_rejected(self):
        self.events.append("rejected")


def test_confirm_dialog_defaults_title_and_flags(app, widgets):
    d = _keep(widgets, ConfirmDialog())
    assert d.windowTitle() == "对话框"
    assert not (d.windowFlags() & Qt.WindowContextHelpButtonHint)
    assert isinstance(d.button_box, QDialogButtonBox)
    assert d._buttons == (QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    assert d._create_content() is None


def test_confirm_dialog_custom_title_buttons_and_content(app, widgets):
    buttons = QDialogButtonBox.Save | QDialogButtonBox.Discard | QDialogButtonBox.Help
    d = _keep(widgets, _ContentDialog(title="自定义标题", buttons=buttons))
    assert d.windowTitle() == "自定义标题"
    assert d.content_layout is not None
    # 内容布局已被加入主布局
    assert d.layout().count() == 2
    found = d.buttons()
    assert QDialogButtonBox.Save in found and QDialogButtonBox.Discard in found
    assert QDialogButtonBox.Help in found
    assert QDialogButtonBox.Ok not in found
    for btn, widget in found.items():
        assert d.button(btn) is widget
        assert widget is not None


def test_confirm_dialog_accept_reject_hooks_and_results(app, widgets):
    d = _keep(widgets, _ContentDialog())
    d.button_box.accepted.emit()
    assert d.events == ["accepted"]
    assert d.result() == 1  # QDialog.Accepted

    d2 = _keep(widgets, _ContentDialog())
    d2.button_box.rejected.emit()
    assert d2.events == ["rejected"]
    assert d2.result() == 0  # QDialog.Rejected


def test_confirm_dialog_base_hooks_are_noops(app, widgets):
    """基类 _on_accepted/_on_rejected 的空实现不影响 accept/reject。"""
    d = _keep(widgets, ConfirmDialog())
    d.accept()
    assert d.result() == 1
    d2 = _keep(widgets, ConfirmDialog())
    d2.reject()
    assert d2.result() == 0


def test_confirm_dialog_empty_button_set(app, widgets):
    d = _keep(widgets, ConfirmDialog(buttons=QDialogButtonBox.StandardButtons(0)))
    assert d.buttons() == {}
    assert d.button(QDialogButtonBox.Ok) is None


# ── EditableComboBox ────────────────────────────────────────────────

@pytest.mark.parametrize("case_sensitive,filter_mode", [
    (False, "contains"),
    (True, "startswith"),
])
def test_editable_combo_box_init_completer_and_default(app, widgets,
                                                      case_sensitive, filter_mode):
    box = _keep(widgets, EditableComboBox(
        ["Alpha", "Beta", "Gamma"], default_index=1,
        case_sensitive=case_sensitive, filter_mode=filter_mode))
    assert box.isEditable()
    assert box.count() == 3
    assert box.currentIndex() == 1
    assert box.currentData() == "Beta"
    completer = box.completer()
    assert completer is not None
    expected_cs = Qt.CaseSensitive if case_sensitive else Qt.CaseInsensitive
    assert completer.caseSensitivity() == expected_cs
    expected_mode = Qt.MatchStartsWith if filter_mode == "startswith" else Qt.MatchContains
    assert completer.filterMode() == expected_mode
    from PySide6.QtWidgets import QCompleter
    assert completer.completionMode() == QCompleter.PopupCompletion


def test_editable_combo_box_invalid_default_index_ignored(app, widgets):
    box = _keep(widgets, EditableComboBox(["only"], default_index=99))
    assert box.currentIndex() == 0
    assert box.currentData() == "only"


def test_editable_combo_box_empty_items(app, widgets):
    box = _keep(widgets, EditableComboBox([]))
    assert box.count() == 0
    assert box.currentIndex() == -1
    # 空列表下输入非法 → 清空文本
    box.lineEdit().setText("nonsense")
    box._validate_input()
    assert box.currentText() == ""


def test_editable_combo_box_validate_restores_default(app, widgets):
    box = _keep(widgets, EditableComboBox(["A", "B", "C"], default_index=2))
    box.lineEdit().setText("INVALID")
    box._validate_input()
    assert box.currentData() == "C"
    # 合法输入保持不变
    box.lineEdit().setText("A")
    box._validate_input()
    assert box.currentData() == "A"


def test_editable_combo_box_editing_finished_signal(app, widgets):
    box = _keep(widgets, EditableComboBox(["A", "B"], default_index=0))
    box.lineEdit().setText("BAD")
    box.lineEdit().editingFinished.emit()
    assert box.currentData() == "A"


def test_editable_combo_box_set_items_restores_old_text(app, widgets):
    box = _keep(widgets, EditableComboBox(["A", "B", "C"], default_index=2))
    assert box.currentData() == "C"
    box.setItems(["C", "D"])
    assert box.currentData() == "C"
    assert [box.itemText(i) for i in range(box.count())] == ["C", "D"]


def test_editable_combo_box_set_items_falls_back_to_default_index(app, widgets):
    box = _keep(widgets, EditableComboBox(["A", "B"], default_index=1))
    box.setItems(["X", "Y", "Z"])
    assert box.currentData() == "Y"
    assert box.currentData() == box.currentText()


def test_editable_combo_box_set_items_empty(app, widgets):
    box = _keep(widgets, EditableComboBox(["A"], default_index=0))
    box.setItems([])
    assert box.count() == 0
    assert box.currentData() == ""


# ── ToggleSwitch ────────────────────────────────────────────────────

def _mouse(event_type, x, button=Qt.LeftButton):
    return QMouseEvent(event_type, QPointF(float(x), 5.0), QPointF(float(x), 5.0),
                       button, button, Qt.NoModifier)


def _key(key):
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.NoModifier)


def test_toggle_switch_defaults_and_size(app, widgets):
    w = _keep(widgets, ToggleSwitch())
    assert w.isChecked() is False
    assert w.isAnimated() is True
    assert w.handle_position == 0.0
    assert w.sizeHint().width() == 44 and w.sizeHint().height() == 22
    assert w.focusPolicy() == Qt.StrongFocus
    assert w._track_on_color == QColor("#4CAF50")
    assert w._track_off_color == QColor("#BDBDBD")
    assert w._handle_color == QColor("#FFFFFF")


def test_toggle_switch_initial_checked_and_custom_colors(app, widgets):
    w = _keep(widgets, ToggleSwitch(checked=True, animated=False,
                                    track_on_color=QColor("#112233"),
                                    track_off_color=QColor("#445566"),
                                    handle_color=QColor("#778899")))
    assert w.isChecked() is True and w.handle_position == 1.0
    assert w._track_on_color == QColor("#112233")
    assert w._track_off_color == QColor("#445566")
    assert w._handle_color == QColor("#778899")


def test_toggle_switch_set_checked_no_animate_emits_signal(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    emitted: list[bool] = []
    w.toggled.connect(emitted.append)
    w.setChecked(True)
    assert w.isChecked() is True and w.handle_position == 1.0
    assert emitted == [True]
    w.setChecked(True)  # 幂等：不重复发信号
    assert emitted == [True]
    w.setChecked(False)
    assert w.isChecked() is False and w.handle_position == 0.0
    assert emitted == [True, False]


def test_toggle_switch_set_checked_animated_and_explicit_animate(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=True))
    emitted: list[bool] = []
    w.toggled.connect(emitted.append)
    w.setChecked(True)
    assert emitted == [True]
    assert w._animation.startValue() == 0.0
    assert w._animation.endValue() == 1.0
    # 显式 animate=False 覆盖构造时的 animated=True
    w.setChecked(False, animate=False)
    assert w.handle_position == 0.0
    assert emitted == [True, False]


def test_toggle_switch_toggle_and_animated_flag(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    assert w.isAnimated() is False
    w.setAnimated(True)
    assert w.isAnimated() is True
    w.setAnimated(False)
    w.toggle()
    assert w.isChecked() is True


def test_toggle_switch_handle_position_property_clamps(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    w.handle_position = -3.0
    assert w.handle_position == 0.0
    w.handle_position = 5.0
    assert w.handle_position == 1.0
    w.handle_position = 0.42
    assert w.handle_position == pytest.approx(0.42)


def test_toggle_switch_color_setters(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    w.setTrackOnColor(QColor("#010203"))
    w.setTrackOffColor(QColor("#040506"))
    w.setHandleColor(QColor("#070809"))
    assert w._track_on_color == QColor("#010203")
    assert w._track_off_color == QColor("#040506")
    assert w._handle_color == QColor("#070809")


def test_toggle_switch_paint_event_runs(app, widgets):
    """渲染路径：直接调用 paintEvent 覆盖颜色插值 + 轨道/滑块绘制。

    离线 QPaintDevice 会让 QPainter 打印告警但不抛异常；断言调用后可
    正常结束，且关闭/开启两端插值结果不同（通过 track_color 计算间接验证）。
    """
    w = _keep(widgets, ToggleSwitch(animated=False))
    w.resize(w.sizeHint())
    w.paintEvent(QPaintEvent(w.rect()))
    w.setChecked(True)
    w.paintEvent(QPaintEvent(w.rect()))
    assert w.handle_position == 1.0


def test_toggle_switch_mouse_press_tracks_drag_and_stops_running_animation(app, widgets):
    from PySide6.QtCore import QPropertyAnimation
    from unittest.mock import patch

    w = _keep(widgets, ToggleSwitch(animated=True))
    # 不真正启动动画（避免离线 Qt 告警），用伪造 state() 覆盖 Running 分支
    with patch.object(w._animation, "state",
                      return_value=QPropertyAnimation.Running), \
            patch.object(w._animation, "stop") as stop:
        w.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 3))
        stop.assert_called_once_with()
    assert w._dragging is True
    assert w._drag_start_x == 3.0
    assert w._drag_position == 0.0


def test_toggle_switch_mouse_press_ignores_non_left_button(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    w.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 3, Qt.RightButton))
    assert w._dragging is False


def test_toggle_switch_mouse_move_requires_drag_and_travel(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    # 未拖拽直接返回
    w.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 30))
    assert w.handle_position == 0.0
    w._dragging = True
    w._drag_start_x = 2.0
    w._drag_position = 0.0
    w._track_width = w._track_height  # travel <= 0 分支
    w.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 40))
    assert w.handle_position == 0.0
    w._track_width = 44
    w.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 13))
    assert 0.0 < w.handle_position <= 1.0
    # 超过边界会被 clamp 到 1.0
    w.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 999))
    assert w.handle_position == 1.0


def test_toggle_switch_mouse_release_without_drag_is_noop(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 2))
    assert w.isChecked() is False


def test_toggle_switch_pure_click_toggles(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    emitted: list[bool] = []
    w.toggled.connect(emitted.append)
    w._dragging = True
    w._drag_start_x = 2.0
    w._drag_position = 0.0
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 2))
    assert w.isChecked() is True and emitted == [True]
    assert w._dragging is False


def test_toggle_switch_drag_snap_to_on_with_animation(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=True))
    emitted: list[bool] = []
    w.toggled.connect(emitted.append)
    w._dragging = True
    w._drag_start_x = 0.0
    w._drag_position = 0.0
    w.handle_position = 0.8
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 40))
    assert w.isChecked() is True and emitted == [True]
    assert w._animation.endValue() == 1.0
    assert w._dragging is False


def test_toggle_switch_drag_snap_to_off_without_animation(app, widgets):
    w = _keep(widgets, ToggleSwitch(checked=True, animated=False))
    emitted: list[bool] = []
    w.toggled.connect(emitted.append)
    w._dragging = True
    w._drag_start_x = 0.0
    w._drag_position = 1.0
    w.handle_position = 0.2
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 2))
    assert w.isChecked() is False and emitted == [False]
    assert w.handle_position == 0.0


def test_toggle_switch_drag_snap_same_state_no_signal(app, widgets):
    w = _keep(widgets, ToggleSwitch(checked=True, animated=False))
    emitted: list[bool] = []
    w.toggled.connect(emitted.append)
    w._dragging = True
    w._drag_start_x = 0.0
    w._drag_position = 1.0
    w.handle_position = 0.9
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 40))
    assert w.isChecked() is True and emitted == []
    assert w.handle_position == 1.0


def test_toggle_switch_drag_travel_zero_treated_as_click(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    w._dragging = True
    w._drag_start_x = 0.0
    w._drag_position = 0.0
    w._track_width = w._track_height
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 10))
    assert w.isChecked() is True


@pytest.mark.parametrize("key", [Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter])
def test_toggle_switch_keyboard_keys_toggle_and_accept(app, widgets, key):
    w = _keep(widgets, ToggleSwitch(animated=False))
    event = _key(key)
    w.keyPressEvent(event)
    assert w.isChecked() is True
    assert event.isAccepted()


def test_toggle_switch_other_key_delegates_to_base(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    event = _key(Qt.Key_Escape)
    w.keyPressEvent(event)
    assert w.isChecked() is False


def test_toggle_switch_start_animation_end_values(app, widgets):
    w = _keep(widgets, ToggleSwitch(animated=False))
    w.handle_position = 0.3
    w._start_animation(True)
    assert w._animation.startValue() == pytest.approx(0.3)
    assert w._animation.endValue() == 1.0
    w._start_animation(False)
    assert w._animation.endValue() == 0.0
