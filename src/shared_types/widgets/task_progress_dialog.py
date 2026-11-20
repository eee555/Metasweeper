"""通用后台任务对话框：统一展示进度和流式输出。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class TaskProgressDialog(QDialog):
    """在工作线程执行长任务时显示进度条和滚动跟随的输出区。

    工作线程只能通过 Qt 信号调用 ``set_status``、``append_output`` 和
    ``set_progress``，这些调用会在对话框所属线程执行。支持取消的任务会等待
    工作线程退出后再关闭窗口。
    """

    task_output = Signal(str)
    task_progress = Signal(int, int)
    task_finished = Signal(object)

    def __init__(
        self,
        title: str,
        initial_status: str,
        parent=None,
        *,
        on_cancel: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal if parent is not None
                               else Qt.WindowModality.ApplicationModal)
        self.resize(540, 320)
        self.setMinimumSize(400, 250)
        self._active = False
        self._on_cancel = on_cancel

        layout = QVBoxLayout(self)
        self._status = QLabel(initial_status)
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._status)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)
        self.task_output.connect(self.append_output, Qt.ConnectionType.QueuedConnection)
        self.task_progress.connect(self.set_progress, Qt.ConnectionType.QueuedConnection)

        self._output = QPlainTextEdit(self)
        self._output.setReadOnly(True)
        self._output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        scroll_bar = self._output.verticalScrollBar()
        scroll_bar.rangeChanged.connect(
            lambda minimum, maximum: scroll_bar.setValue(maximum))
        layout.addWidget(self._output, 1)

        self._close_button = QPushButton(self.tr("关闭"))
        self._close_button.clicked.connect(self.reject)
        layout.addWidget(self._close_button, alignment=Qt.AlignmentFlag.AlignRight)

    @property
    def progress(self) -> QProgressBar:
        """兼容旧调用点读取进度条自身的范围与值。"""
        return self._progress

    @Slot(str)
    def set_status(self, text: str) -> None:
        self._status.setText(text)

    @Slot(str)
    def append_output(self, text: str) -> None:
        cursor = self._output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    @Slot(int, int)
    def set_progress(self, value: int, maximum: int) -> None:
        if maximum > 0:
            self._progress.setRange(0, maximum)
            self._progress.setValue(max(0, min(value, maximum)))

    def set_indeterminate(self) -> None:
        self._progress.setRange(0, 0)

    def set_completed(self, text: str, *, success: bool = True) -> None:
        """任务结束后解除关闭保护，并记录最终状态。"""
        self.set_task_running(False)
        if success:
            self.set_progress(1, 1)
        else:
            self._progress.hide()
        self.set_status(text)

    def set_task_running(self, running: bool) -> None:
        self._active = running
        can_cancel = running and self._on_cancel is not None
        self._close_button.setText(self.tr("取消") if can_cancel else self.tr("关闭"))
        self._close_button.setEnabled(not running or can_cancel)

    def set_result(self, text: str) -> None:
        self.set_status(text)

    def reject(self) -> None:
        if not self._active:
            super().reject()
        elif self._on_cancel is not None and self._close_button.isEnabled():
            self._close_button.setEnabled(False)
            self.set_status(self.tr("正在取消…"))
            self._on_cancel()

    def closeEvent(self, event) -> None:
        if self._active:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
