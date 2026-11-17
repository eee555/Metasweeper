"""依赖安装和升级共用的进度窗口。"""
from threading import Event

from PySide6.QtWidgets import QPlainTextEdit

from plugin_manager.main_window import _InstallProgressDialog


def test_progress_wraps_and_follows_streamed_output(qtbot):
    send_next = Event()
    stop = Event()
    long_line = "long-dependency-name-" * 80

    def installer(*, output_callback):
        try:
            for batch in range(3):
                output_callback(f"batch {batch}: {long_line}\n")
                if batch < 2:
                    while not stop.is_set():
                        if send_next.wait(0.05):
                            send_next.clear()
                            break
        finally:
            stop.set()
        return None

    dialog = _InstallProgressDialog("progress", installer, ())
    qtbot.addWidget(dialog)
    dialog.resize(400, 250)
    dialog.start()
    try:
        output = dialog._output
        scroll_bar = output.verticalScrollBar()
        assert output.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
        for batch in range(3):
            qtbot.waitUntil(lambda: f"batch {batch}:" in output.toPlainText())
            qtbot.waitUntil(lambda: scroll_bar.maximum() > 0 and
                            scroll_bar.value() == scroll_bar.maximum())
            if batch < 2:
                # 模拟用户向上滚动：下次输出仍须跟随到最新位置。
                scroll_bar.setValue(0)
                send_next.set()
        qtbot.waitUntil(lambda: not dialog._active)
        # 等待后续布局事件，确保最终位置不会被延迟的范围更新改变。
        qtbot.wait(50)
        assert scroll_bar.value() == scroll_bar.maximum()
        assert output.document().firstBlock().layout().lineCount() > 1
        assert output.horizontalScrollBar().maximum() == 0
        assert output.toPlainText() == "".join(
            f"batch {batch}: {long_line}\n" for batch in range(3))
    finally:
        stop.set()
        send_next.set()
        if dialog._active:
            dialog._worker.wait(5000)
