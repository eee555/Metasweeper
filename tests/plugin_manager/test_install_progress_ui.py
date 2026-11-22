"""依赖安装和升级共用的进度窗口。"""

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QPlainTextEdit

from shared_types.widgets import TaskProgressDialog


def test_progress_wraps_and_follows_streamed_output(qtbot):
    long_line = "long-dependency-name-" * 80

    dialog = TaskProgressDialog("progress", "running")
    qtbot.addWidget(dialog)
    dialog.resize(400, 250)
    dialog.set_task_running(True)
    dialog.show()
    try:
        output = dialog._output
        scroll_bar = output.verticalScrollBar()
        assert output.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
        for batch in range(3):
            dialog.append_output(f"batch {batch}: {long_line}\n")
            qtbot.waitUntil(lambda: f"batch {batch}:" in output.toPlainText())
            qtbot.waitUntil(lambda: scroll_bar.maximum() > 0 and
                            scroll_bar.value() == scroll_bar.maximum())
            if batch < 2:
                # 模拟用户向上滚动：下次输出仍须跟随到最新位置。
                scroll_bar.setValue(0)
        dialog.set_completed("done")
        qtbot.waitUntil(lambda: not dialog._active)
        # 等待后续布局事件，确保最终位置不会被延迟的范围更新改变。
        qtbot.wait(250)
        assert scroll_bar.value() == scroll_bar.maximum()
        assert output.horizontalScrollBar().maximum() == 0
        assert output.toPlainText() == "".join(
            f"batch {batch}: {long_line}\n" for batch in range(3))
    finally:
        dialog.close()


def test_progress_ranges_and_blocks_close_while_running(qtbot):
    dialog = TaskProgressDialog("progress", "running")
    qtbot.addWidget(dialog)
    dialog.set_task_running(True)
    dialog.set_progress(3, 8)
    assert (dialog.progress.minimum(), dialog.progress.maximum(),
            dialog.progress.value()) == (0, 8, 3)

    event = QCloseEvent()
    dialog.closeEvent(event)
    assert not event.isAccepted()

    dialog.set_progress(6, 0)
    assert dialog.progress.value() == 3
    dialog.set_completed("done")
    event = QCloseEvent()
    dialog.closeEvent(event)
    assert event.isAccepted()
