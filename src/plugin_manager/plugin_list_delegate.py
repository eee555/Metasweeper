"""Two-line rendering for the plugin sidebar."""
from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPalette, QPen
from PySide6.QtWidgets import QListWidget, QStyle, QStyledItemDelegate


_TITLE = Qt.ItemDataRole.UserRole + 2
_STATUS = Qt.ItemDataRole.UserRole + 3
_TONE = Qt.ItemDataRole.UserRole + 4
_VERSION = Qt.ItemDataRole.UserRole + 5

_DOT_COLORS = {
    "ready": ("#24794c", "#6fcb99"),
    "warning": ("#a65d18", "#f1b778"),
    "error": ("#bd3838", "#ff9594"),
}


def set_plugin_row(item, title: str, status: str, tone: str, version: str = "") -> None:
    item.setData(_TITLE, title)
    item.setData(_STATUS, status)
    item.setData(_TONE, tone)
    item.setData(_VERSION, version)
    item.setData(Qt.ItemDataRole.AccessibleTextRole,
                 " · ".join(part for part in (title, status, version) if part))


def _fonts(font):
    title = QFont(font)
    title.setWeight(QFont.Weight.DemiBold)
    detail = QFont(font)
    if detail.pointSizeF() > 0:
        detail.setPointSizeF(max(1.0, detail.pointSizeF() - 1))
    elif detail.pixelSize() > 0:
        detail.setPixelSize(max(1, detail.pixelSize() - 2))
    return title, detail


class PluginListDelegate(QStyledItemDelegate):
    active_plugin_key: str | None = None

    @staticmethod
    def menu_rect(rect: QRect) -> QRect:
        return QRect(rect.right() - 35, rect.top() + 4, 28, 23)

    def sizeHint(self, option, index):
        title, detail = _fonts(option.font)
        text_height = QFontMetrics(title).height() + QFontMetrics(detail).height() + 2
        return QSize(0, max(54, text_height + 16))

    def paint(self, painter, option, index):
        title_text = index.data(_TITLE)
        if title_text is None:
            super().paint(painter, option, index)
            return

        palette = option.palette
        row = option.rect.adjusted(4, 2, -4, -2)
        if row.width() < 1 or row.height() < 1:
            return
        active = (self.active_plugin_key is not None
                  and index.data(Qt.ItemDataRole.UserRole) == self.active_plugin_key)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        focused = bool(option.state & QStyle.StateFlag.State_HasFocus)
        dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
        accent = QColor("#76a6ff" if dark else "#4275c1")
        primary = palette.color(QPalette.ColorRole.WindowText)
        secondary = QColor(primary)
        secondary.setAlphaF(0.73 if dark else 0.76)

        title, detail = _fonts(option.font)
        title_metrics = QFontMetrics(title)
        detail_metrics = QFontMetrics(detail)
        top = row.y() + (row.height() - title_metrics.height() - detail_metrics.height() - 2) // 2

        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        if active or hovered:
            fill = QColor(accent)
            fill.setAlphaF(0.20 if active else 0.07)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(QRectF(row), 8, 8)
        if focused:
            outline = QColor(accent)
            outline.setAlphaF(0.85)
            painter.setPen(QPen(outline, 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(row.adjusted(1, 1, -1, -1)), 7, 7)

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon is not None:
            icon.paint(painter, QRect(row.x() + 10, row.y() + (row.height() - 28) // 2, 28, 28))

        text_x = row.x() + 48
        menu_rect = self.menu_rect(option.rect)
        text_width = max(0, menu_rect.left() - text_x - 5)
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.setFont(title)
        painter.setPen(primary)
        painter.drawText(QRect(text_x, top, text_width, title_metrics.height()), align,
                         title_metrics.elidedText(title_text, Qt.TextElideMode.ElideRight, text_width))

        status_y = top + title_metrics.height() + 2
        tone = index.data(_TONE)
        colors = _DOT_COLORS.get(tone)
        dot = QColor(colors[dark]) if colors else secondary
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot)
        painter.drawEllipse(QRectF(text_x, status_y + (detail_metrics.height() - 6) / 2, 6, 6))

        painter.setFont(detail)
        status = index.data(_STATUS) or ""
        version = index.data(_VERSION) or ""
        status_x = text_x + 12
        detail_right = menu_rect.right() - 6
        detail_width = max(0, detail_right - status_x)
        version_text = detail_metrics.elidedText(version, Qt.TextElideMode.ElideRight,
                                                detail_width)
        version_width = detail_metrics.horizontalAdvance(version_text)
        status_width = max(0, detail_width - (version_width + 8 if version_width else 0))
        painter.setPen(secondary)
        painter.drawText(
            QRect(status_x, status_y, status_width, detail_metrics.height()), align,
            detail_metrics.elidedText(status, Qt.TextElideMode.ElideRight, status_width))
        if version_width:
            muted = QColor(primary)
            muted.setAlphaF(0.58 if dark else 0.64)
            painter.setPen(muted)
            painter.drawText(
                QPoint(detail_right - version_width, status_y + detail_metrics.ascent()),
                version_text)

        painter.setPen(Qt.PenStyle.NoPen)
        if hovered:
            button_fill = QColor(primary)
            button_fill.setAlphaF(0.09)
            painter.setBrush(button_fill)
            painter.drawRoundedRect(QRectF(menu_rect), 5, 5)
        painter.setBrush(primary)
        center = menu_rect.center()
        for offset in (-5, 0, 5):
            painter.drawEllipse(QRectF(center.x() + offset - 1.5, center.y() - 1.5, 3, 3))
        painter.restore()


class PluginListWidget(QListWidget):
    menu_requested = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed_menu: QPersistentModelIndex | None = None
        self.setItemDelegate(PluginListDelegate(self))

    def _menu_index_at(self, pos: QPoint) -> QModelIndex:
        index = self.indexAt(pos)
        if index.isValid() and index.data(_TITLE) is not None:
            if PluginListDelegate.menu_rect(self.visualRect(index)).contains(pos):
                return index
        return QModelIndex()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_menu = None
            index = self._menu_index_at(event.position().toPoint())
            if index.isValid():
                self._pressed_menu = QPersistentModelIndex(index)
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pressed_menu is not None:
            pressed = self._pressed_menu
            self._pressed_menu = None
            index = self._menu_index_at(event.position().toPoint())
            if index.isValid() and pressed == index:
                rect = PluginListDelegate.menu_rect(self.visualRect(index))
                self.menu_requested.emit(rect.intersected(self.viewport().rect()).bottomLeft())
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and self._menu_index_at(event.position().toPoint()).isValid()):
            self.mousePressEvent(event)
            return
        super().mouseDoubleClickEvent(event)
