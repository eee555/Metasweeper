from __future__ import annotations

import requests
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QProgressBar, QPushButton, QStyle, QVBoxLayout,
)

from .app_paths import get_all_plugin_dirs, get_executable_dir
from .plugin_download import DownloadCancelled, PluginDownloader
from .plugin_repositories import PluginRepository, RepositoryTag


class _DownloadTask(QThread):
    progress = pyqtSignal(int, int)

    def __init__(self, repository: PluginRepository, tag: RepositoryTag | None, parent):
        super().__init__(parent)
        self.repository = repository
        self.tag = tag
        self.result = None
        self.error = ""
        self.cancelled = False

    def run(self) -> None:
        try:
            with requests.Session() as session:
                downloader = PluginDownloader(session, self.isInterruptionRequested, self.progress.emit)
                if self.tag is None:
                    self.result = downloader.list_tags(self.repository)
                else:
                    self.result = downloader.install(
                        self.repository, self.tag,
                        get_executable_dir() / "user_plugins", get_all_plugin_dirs(),
                    )
        except DownloadCancelled:
            self.cancelled = True
        except Exception as exc:
            self.error = str(exc)


class PluginDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("下载插件"))
        self.setMinimumWidth(520)
        self._task = None
        self._repository = None
        self._closing = False
        self._installed = False

        self.platform = QComboBox()
        self.platform.addItem(self.tr("自动识别"), "auto")
        for label, platform in (("GitHub", "github"), ("GitLab", "gitlab"),
                                ("Gitee", "gitee"), ("Gitea / Forgejo (Codeberg)", "gitea")):
            self.platform.addItem(label, platform)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://github.com/owner/repository")
        self.fetch = QPushButton(self.tr("获取标签"))
        self.fetch.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.fetch.setEnabled(False)
        self.fetch.setAutoDefault(False)
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.url)
        url_layout.addWidget(self.fetch)

        self.tags = QComboBox()
        self.tags.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.tags.setMinimumContentsLength(20)
        self.tags.setEnabled(False)
        form = QFormLayout()
        form.addRow(self.tr("托管平台"), self.platform)
        form.addRow(self.tr("仓库链接"), url_layout)
        form.addRow("Tag", self.tags)

        self.progress = QProgressBar()
        self.progress.hide()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.install = self.buttons.addButton(self.tr("下载插件"), QDialogButtonBox.ActionRole)
        self.install.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        self.install.setEnabled(False)
        self.install.setAutoDefault(False)
        self.close_button = self.buttons.button(QDialogButtonBox.Close)
        self.close_button.setText(self.tr("关闭"))

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.buttons)
        self.url.textChanged.connect(self._url_changed)
        self.platform.currentIndexChanged.connect(self._url_changed)
        self.url.returnPressed.connect(self._fetch_tags)
        self.fetch.clicked.connect(self._fetch_tags)
        self.install.clicked.connect(self._install)
        self.buttons.rejected.connect(self.reject)
        QApplication.instance().aboutToQuit.connect(self._stop_task)

    def _url_changed(self) -> None:
        self._repository = None
        self._installed = False
        self.tags.clear()
        self.tags.setEnabled(False)
        self.install.setEnabled(False)
        self.fetch.setEnabled(bool(self.url.text().strip()))
        self.status.clear()

    def _fetch_tags(self) -> None:
        if self._task is not None:
            return
        self._url_changed()
        try:
            self._repository = PluginRepository.from_url(self.url.text(), self.platform.currentData())
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self.status.setText(self.tr("正在获取标签..."))
        self._start_task(None)

    def _install(self) -> None:
        if self._task is not None or self.tags.currentIndex() < 0:
            return
        self.status.setText(self.tr("正在下载并安装..."))
        self._start_task(self.tags.currentData())

    def _start_task(self, tag: RepositoryTag | None) -> None:
        self.platform.setEnabled(False)
        self.url.setEnabled(False)
        self.fetch.setEnabled(False)
        self.tags.setEnabled(False)
        self.install.setEnabled(False)
        self.close_button.setText(self.tr("取消"))
        self.progress.setRange(0, 0)
        self.progress.show()
        self._task = _DownloadTask(self._repository, tag, self)
        self._task.progress.connect(self._show_progress)
        self._task.finished.connect(self._task_finished)
        self._task.start()

    def _show_progress(self, received: int, total: int) -> None:
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(received)

    def _task_finished(self) -> None:
        task = self._task
        self._task = None
        self.progress.hide()
        self.platform.setEnabled(True)
        self.url.setEnabled(True)
        self.fetch.setEnabled(True)
        self.close_button.setEnabled(True)
        self.close_button.setText(self.tr("关闭"))
        if task.error:
            self.status.setText(self.tr("操作失败：{error}").format(error=task.error))
        elif task.cancelled:
            self.status.setText(self.tr("已取消。"))
        elif task.tag is None:
            for tag in task.result:
                self.tags.addItem(tag.name, tag)
            self.status.setText("" if task.result else self.tr("此仓库没有可用的标签。"))
        else:
            self._installed = True
            self.status.setText(self.tr("已安装到 {path}。重启插件管理器后生效。").format(path=task.result))
        self.tags.setEnabled(bool(self.tags.count()) and not self._installed)
        self.install.setEnabled(bool(self.tags.count()) and not self._installed)
        task.deleteLater()
        if self._closing:
            super().reject()

    def reject(self) -> None:
        if self._task is not None:
            self._closing = True
            self._task.requestInterruption()
            self.close_button.setEnabled(False)
            self.status.setText(self.tr("正在取消..."))
        else:
            super().reject()

    def closeEvent(self, event) -> None:
        if self._task is not None:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)

    def _stop_task(self) -> None:
        if self._task is not None:
            self._task.requestInterruption()
            self._task.wait()
