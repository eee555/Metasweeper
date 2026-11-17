from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QTime, Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.plugin_i18n import PluginTranslate, translated

_translate = PluginTranslate("ClipboardReplay")


class ClipboardReplayWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)

        self._listening = False
        toolbar = QHBoxLayout()
        self._log_label = QLabel(_translate("ClipboardReplay", "运行日志"), self)
        toolbar.addWidget(self._log_label)
        self.status_label = QLabel(_translate("ClipboardReplay", "已暂停"), self)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        toolbar.addWidget(self.status_label)
        toolbar.addStretch()
        self._clear_button = QToolButton(self)
        self._clear_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        )
        self._clear_button.setToolTip(_translate("ClipboardReplay", "清空日志"))
        self._clear_button.setAccessibleName(_translate("ClipboardReplay", "清空日志"))
        self._clear_button.setEnabled(False)
        toolbar.addWidget(self._clear_button)
        self._layout.addLayout(toolbar)

        self.log_output = QPlainTextEdit(self)
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(1000)
        self.log_output.setPlaceholderText(_translate("ClipboardReplay", "暂无日志"))
        self.log_output.setAccessibleName(_translate("ClipboardReplay", "运行日志"))
        self._layout.addWidget(self.log_output, 1)
        self._clear_button.clicked.connect(self.log_output.clear)
        self.log_output.textChanged.connect(self._update_clear_button)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self._log_label.setText(_translate("ClipboardReplay", "运行日志"))
            self.status_label.setText(
                _translate("ClipboardReplay", "监听中") if self._listening
                else _translate("ClipboardReplay", "已暂停"))
            self._clear_button.setToolTip(_translate("ClipboardReplay", "清空日志"))
            self._clear_button.setAccessibleName(_translate("ClipboardReplay", "清空日志"))
            self.log_output.setPlaceholderText(_translate("ClipboardReplay", "暂无日志"))
            self.log_output.setAccessibleName(_translate("ClipboardReplay", "运行日志"))

    @Slot()
    def _update_clear_button(self) -> None:
        self._clear_button.setEnabled(not self.log_output.document().isEmpty())

    @Slot(object)
    def handle_output(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        source = payload.get("source")
        is_system = not isinstance(source, str) or not source or source == "系统"
        if payload.get("kind") == "state" and is_system:
            enabled = payload.get("enabled")
            if isinstance(enabled, bool):
                self._listening = enabled
                self.status_label.setText(
                    _translate("ClipboardReplay", "监听中") if enabled
                    else _translate("ClipboardReplay", "已暂停"))
        if is_system:
            source = _translate("ClipboardReplay", "系统")
        message = payload.get("message")
        if not isinstance(message, str) or not message:
            return
        timestamp = payload.get("time")
        if not isinstance(timestamp, str) or not timestamp:
            timestamp = QTime.currentTime().toString("HH:mm:ss")
        is_error = payload.get(
            "level") == "error" or payload.get("kind") == "error"
        level = (_translate("ClipboardReplay", "错误") if is_error
                 else _translate("ClipboardReplay", "信息"))
        scrollbar = self.log_output.verticalScrollBar()
        scroll_position = scrollbar.value()
        follow_tail = scroll_position >= scrollbar.maximum()
        self.log_output.appendPlainText(
            f"[{timestamp}] [{level}] [{translated(source)}] {translated(message)}")
        scrollbar.setValue(scrollbar.maximum()
                           if follow_tail else scroll_position)
