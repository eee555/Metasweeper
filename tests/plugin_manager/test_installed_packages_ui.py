from concurrent.futures import Future
from threading import Event, Thread
from xml.etree import ElementTree

from PySide6.QtCore import QCoreApplication, QEvent, QThread, Qt

import plugin_manager.main_window as mw


def test_update_results_arrive_on_gui_thread_and_refresh_retries(qtbot, monkeypatch, tmp_path):
    futures = []
    calls = []
    result_threads = []
    original_check_result = mw._InstalledPackagesDialog._check_result

    def record_check_result(dialog):
        if dialog._future is not None and dialog._future.done():
            result_threads.append(QThread.currentThread() == dialog.thread())
        original_check_result(dialog)

    monkeypatch.setattr(mw._InstalledPackagesDialog, "_check_result", record_check_result)
    monkeypatch.setattr(mw, "list_installed_packages", lambda directory: [
        ("Example_Package", "1.0"), ("other", "3")])

    def check(directory, indexes):
        calls.append((directory, indexes.copy()))
        future = Future()
        futures.append(future)
        return future

    monkeypatch.setattr(mw, "check_package_updates_async", check)
    dialog = mw._InstalledPackagesDialog(tmp_path, ["https://example.org/simple"])
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog._refresh_button.isEnabled()
    assert dialog._table.item(0, 2).text() == "—"
    thread = Thread(target=lambda: futures[0].set_result({"example-package": "2.0"}))
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: dialog._future is None)
    assert QThread.currentThread() == dialog.thread()
    assert dialog._table.item(0, 2).text() == "2.0"
    assert dialog._table.item(1, 2).text() == "—"
    dialog._refresh_button.click()
    futures[1].set_exception(RuntimeError("index unavailable"))
    qtbot.waitUntil(lambda: dialog._future is None)
    assert "index unavailable" in dialog._status.text()
    assert dialog._refresh_button.isEnabled()
    dialog._table.setFocus()
    qtbot.keyClick(dialog._table, Qt.Key.Key_Down)
    assert dialog._table.currentRow() >= 0
    assert dialog._upgrade_button.isEnabled()
    dialog._refresh_button.click()
    futures[2].set_result({})
    qtbot.waitUntil(lambda: dialog._future is None)
    assert dialog._table.item(0, 2).text() == "—"
    assert calls == [(tmp_path, ["https://example.org/simple"])] * 3
    assert result_threads == [True, True, True]


def test_close_during_update_check_does_not_touch_destroyed_dialog(qtbot, monkeypatch, tmp_path):
    future = Future()
    assert future.set_running_or_notify_cancel()
    monkeypatch.setattr(mw, "list_installed_packages", lambda _: [("demo", "1")])
    monkeypatch.setattr(mw, "check_package_updates_async", lambda *_: future)
    dialog = mw._InstalledPackagesDialog(tmp_path, [])
    dialog.show()
    dialog.close()
    assert not dialog._timer.isActive()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    thread = Thread(target=lambda: future.set_result({"demo": "2"}))
    thread.start()
    thread.join()
    qtbot.wait(150)
    assert future.result() == {"demo": "2"}


def test_upgrade_progress_failure_retry_and_success(qtbot, monkeypatch, tmp_path):
    futures = []
    calls = []
    started, release = Event(), Event()
    monkeypatch.setattr(mw, "list_installed_packages", lambda _: [("Example_Package", "1.0")])

    def check(*_):
        future = Future()
        futures.append(future)
        future.set_result({"example-package": "2.0"})
        return future

    def upgrade(directory, indexes, name, *, output_callback):
        calls.append((directory, indexes, name, QThread.currentThread() == dialog.thread()))
        output_callback("pip output\n")
        started.set()
        if not release.wait(5):
            return "timed out"
        return "pip failed" if len(calls) == 1 else None

    monkeypatch.setattr(mw, "check_package_updates_async", check)
    monkeypatch.setattr(mw, "upgrade_installed_package", upgrade)
    dialog = mw._InstalledPackagesDialog(tmp_path, ["https://index/simple"])
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog._future is None)
    dialog._table.selectRow(0)
    dialog._upgrade_button.click()
    progress = dialog._progress
    try:
        qtbot.waitUntil(started.is_set)
        qtbot.waitUntil(lambda: "pip output" in progress._output.toPlainText())
        assert not dialog._upgrade_button.isEnabled()
        dialog.reject()
        assert dialog.isVisible()
        release.set()
        qtbot.waitUntil(lambda: not progress._active)
        assert "pip failed" in progress._status.text()
        progress.close()
        assert dialog._upgrade_button.isEnabled()
        dialog._upgrade_button.click()
        progress = dialog._progress
        qtbot.waitUntil(lambda: not progress._active)
        assert "重启插件管理器" in progress._status.text()
        assert "重启插件管理器" in dialog._restart_hint.text()
        qtbot.waitUntil(lambda: dialog._future is None)
        assert len(futures) == 2
        assert calls == [(tmp_path, ["https://index/simple"], "Example_Package", False)] * 2
        progress.close()
    finally:
        release.set()
        if progress._active:
            qtbot.waitUntil(lambda: not progress._active)


def test_environment_passes_current_indexes(qtbot, monkeypatch, tmp_path):
    class Settings:
        plugin_pip_indexes = ["https://old/simple"]
        plugin_lib_dir = str(tmp_path)

    captured = []
    monkeypatch.setattr(mw, "list_installed_packages", lambda _: [])
    monkeypatch.setattr(mw._InstalledPackagesDialog, "exec", lambda dialog: captured.append(dialog))
    dialog = mw.PluginEnvironmentDialog(Settings())
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog._worker is None)
    dialog._pip_indexes_edit.setPlainText("https://first/simple/\nhttps://second/simple")
    dialog._show_installed_packages()
    assert captured[0]._indexes == ["https://first/simple", "https://second/simple"]
    assert captured[0]._directory == tmp_path


def test_package_dialog_translations_are_complete():
    from pathlib import Path

    root = Path(mw.__file__).resolve().parents[1] / "ui"
    for language in ("en_US", "de_DE", "ja_JP", "pl_PL"):
        tree = ElementTree.parse(root / f"{language}.ts")
        for context_name in ("_InstalledPackagesDialog", "_InstallProgressDialog"):
            context = next(item for item in tree.findall("context")
                           if item.findtext("name") == context_name)
            for message in context.findall("message"):
                translation = message.find("translation")
                assert translation is not None
                assert translation.text and translation.get("type") != "unfinished"
                for placeholder in ("{count}", "{error}"):
                    if placeholder in message.findtext("source", ""):
                        assert placeholder in translation.text
