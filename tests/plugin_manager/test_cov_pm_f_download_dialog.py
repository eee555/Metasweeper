from __future__ import annotations

import pytest
from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent

from plugin_manager.plugin_download_dialog import _DownloadTask, PluginDownloadDialog
from plugin_manager.plugin_repositories import PluginRepository, RepositoryTag


REPOSITORY = PluginRepository.from_url("https://github.com/example/plugin")
TAG = RepositoryTag("v1", "a" * 40)


@pytest.fixture(autouse=True)
def offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class FakeDownloader:
    def __init__(self, _session, interrupted, progress):
        self.interrupted = interrupted
        self.progress = progress

    def list_tags(self, repository):
        assert repository == REPOSITORY
        self.progress(4, 9)
        return [TAG]

    def install(self, repository, tag, root, plugin_dirs):
        assert (repository, tag, plugin_dirs) == (REPOSITORY, TAG, [])
        self.progress(9, 9)
        return root / "installed"


class FakeTask:
    def __init__(self, repository=None, tag=None, parent=None, *, result=None,
                 error="", cancelled=False):
        self.repository = repository
        self.tag = tag
        self.result = result
        self.error = error
        self.cancelled = cancelled
        self.progress = SignalProxy()
        self.finished = SignalProxy()
        self.started = False
        self.interrupted = False
        self.waited = False
        self.deleted = False

    def start(self):
        self.started = True

    def requestInterruption(self):
        self.interrupted = True

    def wait(self):
        self.waited = True

    def isRunning(self):
        return True

    def terminate(self):
        self.terminated = True

    def deleteLater(self):
        self.deleted = True


class SignalProxy:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


def test_download_task_fetch_install_cancel_and_errors(qapp, monkeypatch, tmp_path):
    from plugin_manager import plugin_download_dialog as module

    monkeypatch.setattr(module.requests, "Session", FakeSession)
    monkeypatch.setattr(module, "PluginDownloader", FakeDownloader)
    monkeypatch.setattr(module, "get_executable_dir", lambda: tmp_path)
    monkeypatch.setattr(module, "get_all_plugin_dirs", lambda: [])
    fetch = _DownloadTask(REPOSITORY, None, None)
    progress = []
    fetch.progress.connect(lambda *values: progress.append(values))
    fetch.run()
    assert fetch.result == [TAG]
    assert fetch.error == ""
    assert not fetch.cancelled
    assert progress == [(4, 9)]

    install = _DownloadTask(REPOSITORY, TAG, None)
    install.run()
    assert install.result == tmp_path / "user_plugins" / "installed"

    class CancellingDownloader(FakeDownloader):
        def list_tags(self, _repository):
            raise module.DownloadCancelled()

    monkeypatch.setattr(module, "PluginDownloader", CancellingDownloader)
    cancelled = _DownloadTask(REPOSITORY, None, None)
    cancelled.run()
    assert cancelled.cancelled

    class FailingDownloader(FakeDownloader):
        def list_tags(self, _repository):
            raise RuntimeError("offline")

    monkeypatch.setattr(module, "PluginDownloader", FailingDownloader)
    failed = _DownloadTask(REPOSITORY, None, None)
    failed.run()
    assert failed.error == "offline"


def test_dialog_url_fetch_validation_and_empty_tags(qapp, qtbot, monkeypatch):
    from plugin_manager import plugin_download_dialog as module

    dialog = PluginDownloadDialog()
    qtbot.addWidget(dialog)
    assert not dialog.fetch.isEnabled()
    dialog.url.setText("  ")
    assert not dialog.fetch.isEnabled()
    dialog.url.setText("https://invalid.example/nope")
    assert dialog.fetch.isEnabled()
    dialog.fetch.click()
    assert "无效" in dialog.status.text() or dialog.status.text()
    assert dialog._task is None
    dialog._install()
    active = FakeTask(REPOSITORY)
    dialog._task = active
    dialog._fetch_tags()
    assert dialog._task is active
    dialog._task = None

    created = []

    def task_factory(repository, tag, parent):
        task = FakeTask(repository, tag, parent)
        created.append(task)
        return task

    monkeypatch.setattr(module, "_DownloadTask", task_factory)
    dialog.url.setText("https://github.com/example/plugin")
    dialog.fetch.click()
    assert created[-1].started
    assert not dialog.platform.isEnabled()
    assert not dialog.url.isEnabled()
    assert not dialog.fetch.isEnabled()
    assert created[-1].finished.callbacks
    created[-1].result = []
    created[-1].finished.emit()
    assert dialog._task is None
    assert "没有可用的标签" in dialog.status.text()
    assert dialog.platform.isEnabled()
    assert dialog.fetch.isEnabled()
    assert not dialog.install.isEnabled()


def test_dialog_tag_selection_progress_install_and_failures(qapp, qtbot, monkeypatch):
    from plugin_manager import plugin_download_dialog as module

    dialog = PluginDownloadDialog()
    qtbot.addWidget(dialog)
    dialog.url.setText("https://github.com/example/plugin")
    monkeypatch.setattr(module, "_DownloadTask", FakeTask)
    dialog._fetch_tags()
    task = dialog._task
    task.result = [TAG]
    task.finished.emit()
    assert dialog.tags.isEnabled()
    assert dialog.install.isEnabled()
    dialog.tags.setCurrentIndex(0)
    dialog._install()
    installing = dialog._task
    assert installing.tag == TAG
    assert not dialog.install.isEnabled()
    dialog._show_progress(3, 8)
    assert (dialog.progress.minimum(), dialog.progress.maximum(),
            dialog.progress.value()) == (0, 8, 3)
    dialog._show_progress(6, 0)
    assert dialog.progress.value() == 3
    installing.result = "plugin path"
    installing.finished.emit()
    assert dialog._installed
    assert "plugin path" in dialog.status.text()
    assert not dialog.install.isEnabled()

    for text, cancelled in (("failed", False), ("", True)):
        dialog._installed = False
        failed = FakeTask(REPOSITORY, None, dialog, error=text,
                          cancelled=cancelled)
        dialog._task = failed
        dialog._task_finished()
        assert failed.deleted
        assert ("操作失败" in dialog.status.text()) if text else ("已取消" in dialog.status.text())


def test_dialog_cancel_close_and_stop_task_paths(qapp, qtbot, monkeypatch):
    dialog = PluginDownloadDialog()
    qtbot.addWidget(dialog)
    task = FakeTask(REPOSITORY)
    dialog._task = task
    dialog.reject()
    assert dialog._closing and task.interrupted
    assert not dialog.close_button.isEnabled()
    assert "正在取消" in dialog.status.text()
    event = QCloseEvent()
    dialog.closeEvent(event)
    assert not event.isAccepted()
    dialog._stop_task()
    assert task.waited

    finished = FakeTask(REPOSITORY, None, dialog, result=[])
    dialog._task = finished
    dialog._closing = True
    dialog._task_finished()
    assert dialog._task is None
    assert not dialog.isVisible()

    idle = PluginDownloadDialog()
    qtbot.addWidget(idle)
    event = QCloseEvent()
    idle.closeEvent(event)
    assert event.isAccepted()
    idle._stop_task()
    idle.reject()
    assert not idle.isVisible()
