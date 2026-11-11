"""插件管理器操作图标；插件自身的身份图标仍由 BasePlugin 提供。

只依赖编译进 actions_rc 的资源，不依赖工作目录或外部 SVG 文件。
与 QWidget 一样，在 GUI 线程中调用；图标按当前应用调色板和 DPI 绘制。
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QFile, QIODevice, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QAction, QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialogButtonBox

from . import actions_rc

assert actions_rc is not None  # importing registers the embedded Qt resources


ACTION_ICON_NAMES = frozenset({
    "authorize", "cancel", "clear", "close", "confirm", "debug", "disable",
    "download", "enable", "guide", "info", "log", "quit", "refresh",
    "settings", "tag", "window", "window-close",
})
ICON_NAMES = ACTION_ICON_NAMES | {"app"}
_RESOURCE_PREFIX = ":/plugin_manager/actions/"
_SVG_COLOR = b"#526b86"


@lru_cache(maxsize=len(ICON_NAMES))
def _svg_data(name: str) -> bytes:
    if name not in ICON_NAMES:
        raise ValueError(f"Unknown plugin manager action icon: {name}")
    source = QFile(f"{_RESOURCE_PREFIX}{name}.svg")
    if not source.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError(f"Missing plugin manager action resource: {name}")
    try:
        return bytes(source.readAll().data())
    finally:
        source.close()


class _ActionIconEngine(QIconEngine):
    """保留矢量绘制，避免固定尺寸位图在高 DPI 下模糊。

    绘制时读取调色板，已有图标也能跟随浅色/深色主题切换。
    显式绘制禁用/选中颜色，不依赖平台对 SVG 的灰化策略。
    """

    def __init__(self, data: bytes, recolour: bool = True) -> None:
        super().__init__()
        self._data = data
        self._recolour = recolour

    def clone(self) -> QIconEngine:
        return _ActionIconEngine(self._data, self._recolour)

    def _pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        del state  # icon state is On/Off; this set has no state-specific variants
        palette = QApplication.palette()
        group = (QPalette.ColorGroup.Disabled if mode == QIcon.Mode.Disabled
                 else QPalette.ColorGroup.Active)
        role = (QPalette.ColorRole.HighlightedText if mode == QIcon.Mode.Selected
                else QPalette.ColorRole.ButtonText)
        color = palette.color(group, role)
        data = (self._data.replace(_SVG_COLOR, color.name().encode("ascii"))
                if self._recolour else self._data)
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(data))
        # 居中等比绘制，非正方形调用也不拉伸线条。
        side = min(size.width(), size.height())
        target = QRectF((size.width() - side) / 2, (size.height() - side) / 2,
                        side, side)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(color.alphaF())
        renderer.render(painter, target)
        painter.end()
        return pixmap

    def paint(
        self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State,
    ) -> None:
        device = painter.device()
        scale = device.devicePixelRatioF() if device is not None else 1.0
        painter.drawPixmap(rect, self.scaledPixmap(rect.size(), mode, state, scale))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self._pixmap(size, mode, state)

    def scaledPixmap(
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float,
    ) -> QPixmap:
        pixmap = self._pixmap(size * scale, mode, state)
        pixmap.setDevicePixelRatio(scale)
        return pixmap


def action_icon(name: str) -> QIcon:
    """返回操作图标或应用身份图标；不返回插件自己的身份图标。"""
    return QIcon(_ActionIconEngine(_svg_data(name), name in ACTION_ICON_NAMES))


def set_action_icon(target: QAction | QAbstractButton, name: str) -> None:
    """给操作入口加图标，保留原文字、快捷键、信号和启用条件。"""
    target.setIcon(action_icon(name))
    if isinstance(target, QAction):
        target.setIconVisibleInMenu(True)
    else:
        target.setIconSize(QSize(16, 16))  # logical pixels; Qt applies the screen DPR


def set_button_box_icons(box: QDialogButtonBox) -> None:
    """仅为管理器自己的标准按钮设置同套图标，不修改共享控件。"""
    for standard, name in (
        (QDialogButtonBox.StandardButton.Ok, "confirm"),
        (QDialogButtonBox.StandardButton.Cancel, "cancel"),
        (QDialogButtonBox.StandardButton.Close, "close"),
    ):
        button = box.button(standard)
        if button is not None:
            set_action_icon(button, name)
