"""插件市场：扫描索引、搜索、版本比较、安装与更新。

界面只在 GUI 线程创建和修改；索引扫描与下载在 ``_MarketTask`` 线程执行。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event

import requests
from loguru import logger
from packaging.version import Version
from PySide6.QtCore import (
    QCoreApplication, QObject, QRunnable, QThread, QThreadPool, QTimer, Qt, QUrl, Signal, Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .app_paths import get_all_plugin_dirs, get_executable_dir
from .icons import action_icon, set_action_icon, set_button_box_icons
from .plugin_catalog import (
    CatalogEntry, InstalledPlugin, PluginRelease, find_installed_for_repository,
    rank_versions, scan_installed,
)
from .plugin_download import DownloadCancelled, PluginDownloader
from .plugin_readme_dialog import _PluginReadmeDialog
from .plugin_repositories import PluginRepository, RepositoryTag
from .plugin_updates import prepare_plugin_dependencies
from .settings_manager import SettingsManager

STATE_NOT_INSTALLED = "未安装"
STATE_UPDATE = "可更新"
STATE_LATEST = "已是最新"
STATE_FAILED = "检查失败"
STATE_INSTALLED = "已安装"


def _tr(text: str) -> str:
    return QCoreApplication.translate("PluginMarketDialog", text)


@dataclass(slots=True)
class MarketRow:
    """市场列表中的一行。"""

    entry: CatalogEntry
    releases: PluginRelease | None = None
    installed: InstalledPlugin | None = None

    @property
    def latest_version(self) -> str:
        latest = self.releases.latest if self.releases else None
        return str(latest[0]) if latest else ""

    @property
    def installed_version(self) -> str:
        if self.installed and self.installed.version:
            return str(self.installed.version)
        return ""

    @property
    def state(self) -> str:
        if self.releases is not None and self.releases.error:
            return _tr(STATE_FAILED)
        if self.installed is None:
            return _tr(STATE_NOT_INSTALLED)
        if self.releases is not None and self.releases.latest_version is not None:
            if self.installed.version is None:
                return _tr(STATE_INSTALLED)
            if self.installed.update_available(self.releases):
                return _tr(STATE_UPDATE)
            return _tr(STATE_LATEST)
        return _tr(STATE_INSTALLED)

    @property
    def can_install(self) -> bool:
        return self.releases is not None and bool(self.releases.versions)


@dataclass(slots=True)
class MarketSnapshot:
    """一次扫描的完整结果。"""

    rows: list[MarketRow] = field(default_factory=list)
    error: str = ""


class _MarketTask(QThread):
    progress = Signal(int, int)
    snapshot = Signal(object)
    installed = Signal(str)
    message = Signal(str)

    def __init__(self, index_url: str, target: MarketRow | None,
                 version: Version | None, parent, source: str = "github"):
        super().__init__(parent)
        self.index_url = index_url
        self.target = target
        self.version = version
        self.source = source
        self.error = ""

    def run(self) -> None:
        try:
            with requests.Session() as session:
                downloader = PluginDownloader(
                    session, self.isInterruptionRequested, self.progress.emit)
                if self.target is None:
                    entries = downloader.discover_plugins(self.source)
                    self.snapshot.emit(self._scan(downloader, entries))
                else:
                    self.installed.emit(self._install(downloader, self.target))
        except DownloadCancelled:
            pass
        except Exception as exc:  # noqa: BLE001 - 反馈到界面
            self.error = str(exc)

    def _scan(self, _downloader: PluginDownloader,
              entries: list[CatalogEntry]) -> MarketSnapshot:
        installed = scan_installed(get_all_plugin_dirs())

        def fetch_tags(entry: CatalogEntry) -> tuple[list, Exception | None]:
            if self.isInterruptionRequested():
                raise DownloadCancelled()
            try:
                with requests.Session() as session:
                    downloader = PluginDownloader(
                        session, self.isInterruptionRequested, self.progress.emit)
                    return downloader.list_tags(entry.repository), None
            except DownloadCancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - 单仓库失败不影响其它插件
                return [], exc

        if entries:
            with ThreadPoolExecutor(max_workers=min(4, len(entries))) as workers:
                release_results = list(workers.map(fetch_tags, entries))
        else:
            release_results = []

        rows: list[MarketRow] = []
        for entry, (release_tags, error) in zip(entries, release_results):
            row = MarketRow(
                entry=entry,
                installed=find_installed_for_repository(entry.repository, installed),
            )
            if error is not None:
                row.releases = PluginRelease(entry=entry, error=str(error))
            else:
                tags = [(tag.name, tag.commit) for tag in release_tags]
                row.releases = PluginRelease(
                    entry=entry, versions=rank_versions(entry, tags))
            rows.append(row)
        return MarketSnapshot(rows=rows)

    def _install(self, downloader: PluginDownloader, row: MarketRow) -> str:
        releases = row.releases
        if releases is None:
            raise ValueError(_tr("没有可安装的版本。"))
        wanted = self.version if self.version is not None else releases.latest_version
        match = next((item for item in releases.versions if item[0] == wanted), None)
        if match is None:
            raise ValueError(_tr("该版本已不在仓库中。"))
        version, tag_name, commit = match

        def prepare_dependencies(package):
            module_name = (row.installed.directory.name if row.installed is not None
                           else row.entry.repository.module_name)
            prepare_plugin_dependencies(package, module_name, self.message.emit)

        if row.installed is not None:
            plugin_dir = get_executable_dir() / "user_plugins"
            if row.installed.directory.parent.resolve() != plugin_dir.resolve():
                raise ValueError(_tr("插件不在受管理的用户插件目录中，无法自动更新。"))
            return str(downloader.update(
                row.entry.repository, RepositoryTag(tag_name, commit), plugin_dir,
                plugin_version=str(version), tag_prefix=row.entry.tag_prefix,
                destination_name=row.installed.directory.name,
                before_publish=prepare_dependencies))
        return str(downloader.install(
            row.entry.repository, RepositoryTag(tag_name, commit),
            get_executable_dir() / "user_plugins", get_all_plugin_dirs(),
            plugin_version=str(version), tag_prefix=row.entry.tag_prefix,
            before_publish=prepare_dependencies,
        ))


class _ReadmeResult(QObject):
    finished = Signal(object, str)


class _ReadmeTask(QRunnable):
    def __init__(self, repository: PluginRepository, cancelled: Event) -> None:
        super().__init__()
        self.repository = repository
        self.cancelled = cancelled
        self.result = _ReadmeResult()

    def run(self) -> None:
        try:
            with requests.Session() as session:
                downloader = PluginDownloader(session, self.cancelled.is_set, lambda *_: None)
                readme = downloader.fetch_readme(self.repository)
        except DownloadCancelled:
            return
        except Exception as exc:
            if not self.cancelled.is_set():
                self.result.finished.emit(None, str(exc))
        else:
            if not self.cancelled.is_set():
                self.result.finished.emit(readme, "")


class _MarketDetailsDialog(_PluginReadmeDialog):
    def __init__(self, row: MarketRow, parent=None) -> None:
        self._entry = row.entry
        self._cancel_readme = Event()
        super().__init__(row.entry.name, "", parent,
                         title=_tr("{name} - 插件详情").format(name=row.entry.name),
                         repository_url=QUrl(row.entry.repository.url))
        self.resize(780, 620)
        self.button(QDialogButtonBox.StandardButton.Close).setText(_tr("关闭"))
        task = _ReadmeTask(row.entry.repository, self._cancel_readme)
        task.result.finished.connect(self._show_readme, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    def _create_content(self) -> QVBoxLayout:
        entry = self._entry
        details = QFormLayout()
        details.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        details.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for label, value in ((_tr("作者"), entry.author), (_tr("说明"), entry.description)):
            if value:
                field = QLabel()
                field.setTextFormat(Qt.TextFormat.PlainText)
                field.setText(value)
                field.setWordWrap(True)
                field.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                details.addRow(label, field)

        repository = QHBoxLayout()
        url = QLabel(entry.repository.url)
        url.setTextFormat(Qt.TextFormat.PlainText)
        url.setWordWrap(True)
        url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        repository.addWidget(url, 1)
        open_repository = QPushButton(_tr("打开仓库"))
        open_repository.setAutoDefault(False)
        open_repository.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(entry.repository.url)))
        repository.addWidget(open_repository)
        details.addRow(_tr("仓库"), repository)

        body = super()._create_content()
        assert self._browser is not None
        self._browser.hide()
        self._readme_status = QLabel(_tr("正在加载 README…"))
        self._readme_status.setTextFormat(Qt.TextFormat.PlainText)
        self._readme_status.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(details)
        layout.addWidget(self._readme_status)
        layout.addLayout(body, 1)
        return layout

    @Slot(object, str)
    def _show_readme(self, result: tuple[str, str] | None, error: str) -> None:
        if self._cancel_readme.is_set():
            return
        if error:
            self._readme_status.setText(_tr("README 加载失败：{error}").format(error=error))
        elif result is None or not result[0].strip():
            self._readme_status.setText(_tr("仓库中未找到 README。"))
        else:
            content, base_url = result
            self._repository_url = QUrl(base_url)
            self._set_markdown(content)
            self._readme_status.hide()
            if self._browser is not None:
                self._browser.show()

    def done(self, result: int) -> None:
        self._cancel_readme.set()
        super().done(result)


class PluginMarketDialog(QDialog):
    """插件市场：搜索、查看版本、安装与更新。"""

    restart_requested = Signal()

    def __init__(self, index_url: str, parent=None, *, settings: SettingsManager | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle(_tr("插件市场"))
        self.setWindowIcon(action_icon("app"))
        self.resize(940, 580)
        self._index_url = index_url
        self._task: _MarketTask | None = None
        self._rows: list[MarketRow] = []
        self._closing = False
        self._restart_scan_after_cancel = False
        self._queue: list[MarketRow] = []
        self._installed_paths: list[str] = []

        self.source = QComboBox()
        self.source.addItem("GitHub", "github")
        self.source.addItem("Gitee", "gitee")
        if settings is not None:
            self.source.setCurrentIndex(self.source.findData(settings.settings.plugin_market_source))
        self.source_label = QLabel()
        self._update_source_label()
        self.scan_button = QPushButton(_tr("刷新"))
        set_action_icon(self.scan_button, "refresh")
        index_layout = QHBoxLayout()
        index_layout.addWidget(QLabel(_tr("搜索源")))
        index_layout.addWidget(self.source)
        index_layout.addWidget(self.source_label)
        index_layout.addStretch(1)
        index_layout.addWidget(self.scan_button)

        self.search = QLineEdit()
        self.search.setPlaceholderText(_tr("搜索插件名称、说明或作者"))
        self.filter = QComboBox()
        self.filter.addItem(_tr("全部"), "all")
        self.filter.addItem(_tr("可更新"), "updatable")
        self.filter.addItem(_tr("未安装"), "not_installed")
        self.update_all = QPushButton(_tr("全部更新"))
        set_action_icon(self.update_all, "download")
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.search, 1)
        filter_layout.addWidget(self.filter)
        filter_layout.addWidget(self.update_all)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            _tr("插件"), _tr("最新版本"), _tr("已安装"), _tr("状态"), _tr("详情")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(self._open_details_at)

        self.version = QComboBox()
        self.version.setEnabled(False)
        self.action = QPushButton(_tr("安装"))
        set_action_icon(self.action, "download")
        self.action.setEnabled(False)
        action_layout = QHBoxLayout()
        action_layout.addWidget(QLabel(_tr("安装版本")))
        action_layout.addWidget(self.version, 1)
        action_layout.addWidget(self.action)

        self.progress = QProgressBar()
        self.progress.hide()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        set_button_box_icons(buttons)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(_tr("关闭"))

        layout = QVBoxLayout(self)
        layout.addLayout(index_layout)
        layout.addLayout(filter_layout)
        layout.addWidget(self.table, 1)
        layout.addLayout(action_layout)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(buttons)

        self.scan_button.clicked.connect(self.start_scan)
        self.source.currentIndexChanged.connect(self._source_changed)
        self.search.textChanged.connect(self._populate)
        self.filter.currentIndexChanged.connect(self._populate)
        self.action.clicked.connect(self._install_selected)
        self.update_all.clicked.connect(self._update_all)
        buttons.rejected.connect(self.reject)
        QTimer.singleShot(0, self.start_scan)

    def _update_source_label(self) -> None:
        if self.source.currentData() == "gitee":
            self.source_label.setText(_tr("Gitee 关键词：metasweeper"))
        else:
            self.source_label.setText(_tr("GitHub 主题：metasweeper-plugin"))

    def _source_changed(self) -> None:
        self._update_source_label()
        if self._settings is not None:
            source = "gitee" if self.source.currentData() == "gitee" else "github"
            try:
                self._settings.set_plugin_market_source(source)
            except OSError:
                logger.exception("Failed to save plugin market source")
        if self._task is not None and self._task.target is None:
            self._restart_scan_after_cancel = True
            self._task.requestInterruption()
            return
        self.start_scan()

    # ── 扫描 ──────────────────────────────────────────────────
    def start_scan(self) -> None:
        if self._closing or self._task is not None:
            return
        if self.source.currentData() == "gitee":
            message = _tr("正在 Gitee 搜索插件并检查版本...")
        else:
            message = _tr("正在搜索 GitHub 插件并检查版本...")
        self.status.setText(message)
        self._rows = []
        self.table.setRowCount(0)
        self._start_task("", None, None, source=self.source.currentData())

    def _start_task(self, index_url: str, target: MarketRow | None,
                    version: Version | None, source: str = "github") -> None:
        self.source.setEnabled(target is None)
        self.scan_button.setEnabled(False)
        self.action.setEnabled(False)
        self.update_all.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self._task = _MarketTask(index_url, target, version, self, source=source)
        self._task.progress.connect(self._show_progress)
        self._task.snapshot.connect(self._show_snapshot)
        self._task.installed.connect(self._show_installed)
        self._task.message.connect(self._show_task_message)
        self._task.finished.connect(self._task_finished)
        self._task.start()

    def _show_progress(self, received: int, total: int) -> None:
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(received)

    def _show_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._rows = snapshot.rows
        self._populate()

    def _show_task_message(self, message: str) -> None:
        self.status.setText(message[:500])

    def _show_installed(self, path: str) -> None:
        self._installed_paths.append(path)
        self.status.setText(_tr("插件和依赖安装完成。"))

    def _refresh_installed_state(self) -> None:
        installed = scan_installed(get_all_plugin_dirs())
        for row in self._rows:
            row.installed = find_installed_for_repository(
                row.entry.repository, installed)
        self._populate()

    def _show_install_complete(self, error: str = "") -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning if error else QMessageBox.Icon.Information)
        dialog.setWindowTitle(_tr("部分安装完成") if error else _tr("安装完成"))
        if error:
            dialog.setText(_tr("部分插件已安装；后续安装失败：{error}\n"
                               "已安装的插件重启插件管理器后生效。")
                           .format(error=error))
        else:
            dialog.setText(_tr("插件及依赖已安装完成，重启插件管理器后生效。"))
        restart = dialog.addButton(_tr("重启"), QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton(_tr("确认"), QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is restart:
            self.accept()
            self.restart_requested.emit()

    def _task_finished(self) -> None:
        task = self._task
        self._task = None
        if (task is not None and task.target is None
                and self._restart_scan_after_cancel and not self._closing):
            self._restart_scan_after_cancel = False
            task.deleteLater()
            self.progress.hide()
            self.scan_button.setEnabled(True)
            self.source.setEnabled(True)
            self.start_scan()
            return
        self._restart_scan_after_cancel = False
        self.progress.hide()
        self.scan_button.setEnabled(True)
        self.update_all.setEnabled(True)
        self._update_action_state()
        if task is not None:
            if task.error:
                self.status.setText(
                    _tr("操作失败：{error}").format(error=task.error))
            elif task.target is None:
                self._report_scan()
            task.deleteLater()
        if self._closing:
            self._queue.clear()
            super().reject()
            return
        if task is not None and task.error:
            self._queue.clear()
        elif self._queue:
            self._install_next()
            return
        self.source.setEnabled(True)
        if self._installed_paths:
            self._refresh_installed_state()
            self._installed_paths.clear()
            self._show_install_complete(task.error if task is not None else "")

    def _report_scan(self) -> None:
        total = len(self._rows)
        updatable = sum(
            1 for row in self._rows if row.state == _tr(STATE_UPDATE))
        failed = sum(
            1 for row in self._rows if row.state == _tr(STATE_FAILED))
        message = _tr("共 {total} 个插件，{updatable} 个可更新。").format(
            total=total, updatable=updatable)
        if failed:
            message += " " + _tr("{failed} 个仓库检查失败。").format(failed=failed)
        self.status.setText(message)

    # ── 列表 ──────────────────────────────────────────────────
    def _visible_rows(self) -> list[MarketRow]:
        keyword = self.search.text().strip().lower()
        mode = self.filter.currentData()
        rows: list[MarketRow] = []
        for row in self._rows:
            if mode == "updatable" and row.state != _tr(STATE_UPDATE):
                continue
            if mode == "not_installed" and row.installed is not None:
                continue
            if keyword:
                haystack = " ".join((
                    row.entry.name, row.entry.description, row.entry.author,
                )).lower()
                if keyword not in haystack:
                    continue
            rows.append(row)
        return rows

    def _populate(self) -> None:
        rows = self._visible_rows()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = (
                row.entry.name,
                row.latest_version or "—",
                row.installed_version or "—",
                row.state,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setToolTip(value)
                elif column == 3 and row.releases is not None and row.releases.error:
                    item.setToolTip(row.releases.error)
                self.table.setItem(index, column, item)
            details = QPushButton(_tr("查看详情"))
            details.setAutoDefault(False)
            set_action_icon(details, "info")
            details.clicked.connect(lambda _checked=False, item=row: self._open_details(item))
            self.table.setCellWidget(index, 4, details)
        self.version.clear()
        self.action.setEnabled(False)

    @Slot(int, int)
    def _open_details_at(self, index: int, _column: int) -> None:
        rows = self._visible_rows()
        if 0 <= index < len(rows):
            self._open_details(rows[index])

    def _open_details(self, row: MarketRow) -> None:
        dialog = _MarketDetailsDialog(row, self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _selected_row(self) -> MarketRow | None:
        rows = self._visible_rows()
        index = self.table.currentRow()
        if 0 <= index < len(rows):
            return rows[index]
        return None

    def _selection_changed(self) -> None:
        row = self._selected_row()
        self.version.clear()
        if row is None or row.releases is None or not row.releases.versions:
            self._update_action_state()
            return
        for version, tag_name, _commit in row.releases.versions:
            self.version.addItem(f"{version}  ({tag_name})", version)
        self.version.setEnabled(True)
        self._update_action_state()

    def _update_action_state(self) -> None:
        row = self._selected_row()
        self.action.setEnabled(row is not None and row.can_install)
        if row is None:
            self.action.setText(_tr("安装"))
        elif row.installed is None:
            self.action.setText(_tr("安装"))
        elif row.state == _tr(STATE_UPDATE):
            self.action.setText(_tr("更新"))
        else:
            self.action.setText(_tr("重装"))

    # ── 安装 ──────────────────────────────────────────────────
    def _install_selected(self) -> None:
        row = self._selected_row()
        if row is None or not row.can_install or self._task is not None:
            return
        version = self.version.currentData()
        if not isinstance(version, Version):
            version = row.releases.latest_version if row.releases else None
        if row.installed is not None:
            answer = QMessageBox.question(
                self, _tr("更新插件"),
                _tr("已安装 {current}，更新到 {latest}。"
                    "现有插件目录会被替换，插件数据目录保留。继续？").format(
                    current=row.installed_version, latest=str(version)))
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.status.setText(
            _tr("正在安装 {name} ...").format(name=row.entry.name))
        self._start_task(self._index_url, row, version)

    def _update_all(self) -> None:
        rows = [row for row in self._rows if row.state == _tr(STATE_UPDATE)]
        if not rows:
            self.status.setText(_tr("没有可更新的插件。"))
            return
        answer = QMessageBox.question(
            self, _tr("全部更新"),
            _tr("将更新 {count} 个插件。继续？").format(count=len(rows)))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._queue = rows[1:]
        self._start_install(rows[0])

    def _install_next(self) -> None:
        if self._queue:
            self._start_install(self._queue.pop(0))

    def _start_install(self, row: MarketRow) -> None:
        self.status.setText(
            _tr("正在安装 {name} ...").format(name=row.entry.name))
        version = row.releases.latest_version if row.releases else None
        self._start_task(self._index_url, row, version)

    def reject(self) -> None:
        self._closing = True
        if self._task is not None:
            self._task.requestInterruption()
            self.status.setText(_tr("正在取消..."))
            self.scan_button.setEnabled(False)
        else:
            super().reject()
