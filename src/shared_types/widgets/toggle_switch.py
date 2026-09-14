"""
开关控件

iOS/Android 风格的滑动开关，支持平滑动画和拖拽交互。
动画可通过 animated=False 关闭。
"""

from __future__ import annotations

from PyQt5.QtCore import (
    QPropertyAnimation,
    QEasingCurve,
    Qt,
    pyqtProperty,
    pyqtSignal,
    QSize,
)
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """
    滑动开关控件

    Features:
        - 平滑滑动动画（可关闭）
        - 点击切换 + 拖拽滑动
        - 自定义开/关颜色
        - 键盘 Space/Enter 切换
        - toggled 信号兼容 QCheckBox

    Usage:
        switch = ToggleSwitch()
        switch.toggled.connect(lambda checked: print(checked))
        switch.setChecked(True)
    """

    toggled = pyqtSignal(bool)

    def __init__(
        self,
        parent=None,
        checked: bool = False,
        animated: bool = True,
        track_on_color: QColor | None = None,
        track_off_color: QColor | None = None,
        handle_color: QColor | None = None,
    ):
        super().__init__(parent)
        self._checked = checked
        self._animated = animated
        self._handle_position = 1.0 if checked else 0.0

        # 尺寸参数
        self._track_height = 22
        self._track_width = 44
        self._handle_margin = 2
        self._handle_radius = (self._track_height - 2 *
                               self._handle_margin) / 2

        # 颜色
        self._track_on_color = track_on_color or QColor("#4CAF50")
        self._track_off_color = track_off_color or QColor("#BDBDBD")
        self._handle_color = handle_color or QColor("#FFFFFF")

        # 拖拽状态
        self._drag_start_x = 0.0
        self._drag_position = 0.0
        self._dragging = False

        # 动画
        self._animation = QPropertyAnimation(self, b"handle_position")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.OutQuad)

        self.setFixedSize(self.sizeHint())
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    # ── 属性动画 ──────────────────────────────────────────

    @pyqtProperty(float) # pyright: ignore[reportArgumentType]
    def handle_position(self) -> float: # pyright: ignore[reportRedeclaration]
        return self._handle_position

    @handle_position.setter # pyright: ignore[reportArgumentType]
    def handle_position(self, pos: float):
        self._handle_position = max(0.0, min(1.0, pos))
        self.update()

    # ── 公开接口 ──────────────────────────────────────────

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool | None = None):
        """设置开关状态。animate=None 时使用构造时的 animated 设置。"""
        if checked == self._checked:
            return
        self._checked = checked
        should_animate = self._animated if animate is None else animate
        if should_animate:
            self._start_animation(checked)
        else:
            self._handle_position = 1.0 if checked else 0.0
            self.update()
        self.toggled.emit(checked)

    def toggle(self):
        self.setChecked(not self._checked)

    def isAnimated(self) -> bool:
        return self._animated

    def setAnimated(self, animated: bool):
        self._animated = animated

    def setTrackOnColor(self, color: QColor):
        self._track_on_color = color
        self.update()

    def setTrackOffColor(self, color: QColor):
        self._track_off_color = color
        self.update()

    def setHandleColor(self, color: QColor):
        self._handle_color = color
        self.update()

    # ── 尺寸 ──────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        return QSize(self._track_width, self._track_height)

    # ── 绘制 ──────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 轨道颜色插值
        track_color = QColor(
            int(self._track_off_color.red()
                + (self._track_on_color.red() - self._track_off_color.red())
                * self._handle_position),
            int(self._track_off_color.green()
                + (self._track_on_color.green() - self._track_off_color.green())
                * self._handle_position),
            int(self._track_off_color.blue()
                + (self._track_on_color.blue() - self._track_off_color.blue())
                * self._handle_position),
        )

        # 绘制轨道
        track_rect = self.rect()
        track_radius = self._track_height / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(track_rect, track_radius, track_radius)

        # 绘制滑块
        handle_diameter = self._track_height - 2 * self._handle_margin
        handle_x = self._handle_margin + self._handle_position * (
            self._track_width - handle_diameter - 2 * self._handle_margin
        )
        handle_y = self._handle_margin

        # 滑块阴影
        shadow_color = QColor(0, 0, 0, 40)
        painter.setBrush(QBrush(shadow_color))
        painter.drawEllipse(
            int(handle_x) + 1, int(handle_y) + 1,
            int(handle_diameter), int(handle_diameter),
        )

        # 滑块本体
        painter.setBrush(QBrush(self._handle_color))
        painter.drawEllipse(
            int(handle_x), int(handle_y),
            int(handle_diameter), int(handle_diameter),
        )

        painter.end()

    # ── 交互 ──────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_x = event.x()
            self._drag_position = self._handle_position
            self._dragging = True
            if self._animation.state() == QPropertyAnimation.Running:
                self._animation.stop()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        delta = event.x() - self._drag_start_x
        travel = self._track_width - self._track_height
        if travel <= 0:
            return
        self._handle_position = max(0.0, min(1.0,
                                             self._drag_position + delta / travel))
        self.update()

    def mouseReleaseEvent(self, event):
        if not self._dragging:
            return
        self._dragging = False
        # 判断是否为纯点击（几乎没有移动）
        travel = self._track_width - self._track_height
        if travel <= 0 or abs(self._handle_position - self._drag_position) < 0.01:
            # 纯点击 → 切换
            self.toggle()
            return
        # 拖拽 → 吸附：超过 0.5 吸到开，否则吸到关
        new_checked = self._handle_position >= 0.5
        if new_checked != self._checked:
            self._checked = new_checked
            self.toggled.emit(new_checked)
        if self._animated:
            self._start_animation(new_checked)
        else:
            self._handle_position = 1.0 if new_checked else 0.0
            self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.toggle()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ── 动画 ──────────────────────────────────────────────

    def _start_animation(self, to_checked: bool):
        self._animation.stop()
        self._animation.setStartValue(self._handle_position)
        self._animation.setEndValue(1.0 if to_checked else 0.0)
        self._animation.start()
