"""管理插件进程的 Qt 翻译器；所有操作都在应用线程执行。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import loguru
from PySide6.QtCore import QCoreApplication, QObject, QThread, QTranslator, Qt, Signal, Slot

from .app_paths import get_bundle_dir

logger = loguru.logger.bind(name="PluginTranslations")

# 应用、SDK 及 Qt 自身使用的上下文不得被第三方目录覆盖。插件应使用独有的类名或上下文。
_PUBLIC_CONTEXTS = frozenset({
    "", "Application", "CheckUpdateGui", "Commands", "ConnectionStatusWidget",
    "ControlAuthorizationDialog", "CsvExportProgressDialog", "DetachableTabWidget",
    "DetachedPluginWindow", "Dialog", "Form", "LogViewerDialog", "MainWindow",
    "PluginDownloadDialog", "PluginEnvironmentDialog", "PluginInfoDialog",
    "PluginManagerWindow", "PluginSettingsDialog", "ReleaseFrame", "ReplayAnalysis",
    "SettingsDialog", "SkinManager", "Sounds", "VideoLoadProgress",
    "_InstallProgressDialog", "_InstalledPackagesDialog", "_PluginReadmeDialog", "parent",
})
# 禁止插件替换 Qt 的标准按钮、对话框和内置控件文本。
_QT_CONTEXTS = frozenset({
    "QApplication", "QDateTimeEdit", "QDialog", "QDialogButtonBox", "QFontDatabase",
    "QFontDialog", "QInputDialog", "QListView", "QMessageBox", "QPlatformTheme",
    "QPushButton", "QShortcut", "QSplitter", "QSpinBox", "QStandardItemModel",
    "QStyle", "QTabWidget", "QTextDocument", "QTextEdit", "QToolBar", "QWidget",
})
_LOCALE = re.compile(r"[A-Za-z0-9_-]+\Z")


class _PluginTranslator(QTranslator):
    def translate(self, context, sourceText, disambiguation=None, n=-1):
        if context in _PUBLIC_CONTEXTS or context in _QT_CONTEXTS:
            return None
        return super().translate(context, sourceText, disambiguation, n) or None


class TranslationManager(QObject):
    """持有翻译器直到移除；排队操作和完成回调均在 Qt 应用线程执行。"""
    _requested = Signal(object)

    def __init__(self):
        super().__init__()
        app = QCoreApplication.instance()
        if app is not None and self.thread() != app.thread():
            self.moveToThread(app.thread())
        self._requested.connect(self._execute, Qt.ConnectionType.QueuedConnection)
        self._language = "zh_CN"
        self._catalogs: dict[str, Path] = {}
        self._translators: list[QTranslator] = []
        self._closed = False

    def _run(self, action: Callable[[], None]) -> None:
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() == self.thread():
            action()
        else:
            self._requested.emit(action)

    @Slot(object)
    def _execute(self, action: Callable[[], None]) -> None:
        action()

    def set_catalogs(self, catalogs: dict[str, Path]) -> None:
        snapshot = catalogs.copy()
        self._run(lambda: self._set_catalogs(snapshot))

    def _set_catalogs(self, catalogs: dict[str, Path]) -> None:
        if not self._closed and self._catalogs != catalogs:
            self._catalogs = catalogs
            self._replace()

    def install(self, language: str, done: Callable[[], None]) -> None:
        def apply() -> None:
            if not self._closed:
                self._language = language
                try:
                    self._replace()
                except Exception:
                    logger.exception("Failed to switch translation catalogs")
                finally:
                    done()
        self._run(apply)

    def close(self) -> None:
        def cleanup() -> None:
            self._closed = True
            self._remove()
            self._catalogs.clear()
        self._run(cleanup)

    def _remove(self) -> None:
        app = QCoreApplication.instance()
        if app is not None:
            for translator in reversed(self._translators):
                app.removeTranslator(translator)
        self._translators.clear()

    def _replace(self) -> None:
        self._remove()
        app = QCoreApplication.instance()
        if app is None or not _LOCALE.fullmatch(self._language):
            return
        # 插件在应用翻译器之前安装，应用自身的已翻译消息优先。
        paths = [(path / f"{self._language}.qm", True) for path in self._catalogs.values()]
        if self._language != "zh_CN":
            paths.append((get_bundle_dir() / f"{self._language}.qm", False))
        for path, is_plugin in paths:
            if not path.is_file():
                continue
            translator = _PluginTranslator() if is_plugin else QTranslator()
            if not translator.load(str(path)):
                logger.warning(f"Invalid translation catalog: {path}")
                continue
            if app.installTranslator(translator):
                self._translators.append(translator)
