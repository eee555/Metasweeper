"""
llm_minesweeper_controller - UI 组件
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QHBoxLayout,
    QSpinBox,
    QSizePolicy,
    QStyle,
    QToolButton,
)
from PySide6.QtCore import Signal, Slot, Qt, QCoreApplication, QEvent, QRect
from PySide6.QtGui import QIcon, QPainter, QPixmap
from utils.plugin_i18n import PluginTranslate, translated

_translate = PluginTranslate("MinesweeperMcp")


class McpControlWidget(QWidget):
    """Display service snapshots and emit requests without starting a service."""

    start_requested = Signal(int)
    stop_requested = Signal()
    _service_state_received = Signal(object)
    _port_received = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "stopped"
        self._endpoint = ""
        self._error_text = ""
        self._prompt_text = ""

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.action_button = QPushButton(self)
        self.action_button.setObjectName("action_button")
        controls.addWidget(self.action_button)
        controls.addStretch()
        self._port_label = QLabel(self)
        controls.addWidget(self._port_label)
        self.port_spin = QSpinBox(self)
        self.port_spin.setObjectName("port_spin")
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(8765)
        self._port_label.setBuddy(self.port_spin)
        controls.addWidget(self.port_spin)
        layout.addLayout(controls)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("status_label")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.status_label)

        prompt_header = QHBoxLayout()
        self._prompt_label = QLabel(self)
        prompt_header.addWidget(self._prompt_label)
        prompt_header.addStretch()
        self.copy_button = QToolButton(self)
        self.copy_button.setObjectName("copy_button")
        icon_size = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        pixel_ratio = self.devicePixelRatioF()
        copy_pixmap = QPixmap(
            round(icon_size * pixel_ratio), round(icon_size * pixel_ratio)
        )
        copy_pixmap.setDevicePixelRatio(pixel_ratio)
        copy_pixmap.fill(Qt.GlobalColor.transparent)
        document_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        offset = max(1, icon_size // 4)
        painter = QPainter(copy_pixmap)
        document_icon.paint(
            painter, QRect(offset, 0, icon_size - offset, icon_size - offset)
        )
        document_icon.paint(
            painter, QRect(0, offset, icon_size - offset, icon_size - offset)
        )
        painter.end()
        self.copy_button.setIcon(QIcon.fromTheme(
            "edit-copy", QIcon(copy_pixmap)))
        self.copy_button.setEnabled(False)
        prompt_header.addWidget(self.copy_button)
        layout.addLayout(prompt_header)

        self.prompt_edit = QPlainTextEdit(self)
        self.prompt_edit.setObjectName("prompt_edit")
        self.prompt_edit.setReadOnly(True)
        self.prompt_edit.setUndoRedoEnabled(False)
        self.prompt_edit.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.prompt_edit.setMinimumSize(0, 0)
        self._prompt_label.setBuddy(self.prompt_edit)
        layout.addWidget(self.prompt_edit, 1)

        self.action_button.clicked.connect(self._request_action)
        self.copy_button.clicked.connect(self._copy_prompt)
        self._service_state_received.connect(self._apply_service_state)
        self._port_received.connect(self._apply_port)
        self.retranslateUi()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()

    def retranslateUi(self) -> None:
        self._port_label.setText(_translate("MinesweeperMcp", "监听端口"))
        self.port_spin.setAccessibleName(_translate("MinesweeperMcp", "监听端口"))
        self._prompt_label.setText(_translate("MinesweeperMcp", "配置提示词"))
        self.prompt_edit.setAccessibleName(_translate("MinesweeperMcp", "配置提示词"))
        copy_text = _translate("MinesweeperMcp", "复制配置提示词")
        self.copy_button.setToolTip(copy_text)
        self.copy_button.setAccessibleName(copy_text)
        self.prompt_edit.setPlainText(translated(self._prompt_text))
        self._render_state()

    @Slot(int)
    def set_port(self, port: int) -> None:
        self._port_received.emit(port)

    @Slot(int)
    def _apply_port(self, port: int) -> None:
        if self._state in ("stopped", "error"):
            self.port_spin.setValue(port)

    @Slot(object)
    def set_service_state(self, payload: object) -> None:
        if isinstance(payload, dict):
            self._service_state_received.emit(dict(payload))

    @Slot(object)
    def _apply_service_state(self, payload: dict) -> None:
        state = payload.get("state")
        if state not in ("stopped", "starting", "running", "stopping", "error"):
            return
        self._state = state
        port = payload.get("port")
        if isinstance(port, int):
            self.port_spin.setValue(port)
        endpoint = payload.get("endpoint")
        self._endpoint = endpoint.strip() if isinstance(endpoint, str) else ""
        error = payload.get("error")
        self._error_text = error if isinstance(error, str) else ""
        prompt = payload.get("prompt")
        self._prompt_text = prompt if isinstance(prompt, str) else ""
        self.prompt_edit.setPlainText(translated(self._prompt_text))
        self.copy_button.setEnabled(bool(self.prompt_edit.toPlainText()))
        self._render_state()

    def _render_state(self) -> None:
        running = self._state == "running"
        transitioning = self._state in ("starting", "stopping")
        self.action_button.setText(
            _translate("MinesweeperMcp", "停止MCP") if running or self._state == "stopping"
            else _translate("MinesweeperMcp", "启动MCP")
        )
        self.action_button.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaStop if running or self._state == "stopping"
            else QStyle.StandardPixmap.SP_MediaPlay
        ))
        self.action_button.setEnabled(not transitioning)
        self.port_spin.setEnabled(self._state in ("stopped", "error"))
        status_text = {
            "stopped": _translate("MinesweeperMcp", "已停止"),
            "starting": _translate("MinesweeperMcp", "正在启动"),
            "running": _translate("MinesweeperMcp", "运行中"),
            "stopping": _translate("MinesweeperMcp", "正在停止"),
            "error": _translate("MinesweeperMcp", "启动失败"),
        }[self._state]
        if running and self._endpoint:
            status_text = _translate("MinesweeperMcp", "运行中：{endpoint}").format(
                endpoint=self._endpoint
            )
        if self._state == "error" and self._error_text:
            status_text = _translate("MinesweeperMcp", "错误：{reason}").format(
                reason=self._error_text
            )
        self.status_label.setText(status_text)

    @Slot()
    def _request_action(self) -> None:
        if self._state == "running":
            self.stop_requested.emit()
        elif self._state in ("stopped", "error"):
            self.start_requested.emit(self.port_spin.value())

    @Slot()
    def _copy_prompt(self) -> None:
        prompt = self.prompt_edit.toPlainText()
        if prompt:
            QApplication.clipboard().setText(prompt)
