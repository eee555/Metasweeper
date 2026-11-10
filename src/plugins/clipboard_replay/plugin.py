"""
clipboard_replay - 插件主类
"""
from __future__ import annotations

from datetime import datetime
from threading import Event

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QWidget

from plugin_sdk import BasePlugin, PluginInfo, WindowMode
from .config import ClipboardReplayConfig
from .handlers import HANDLER_TYPES, ClipboardHandler
from .widgets import ClipboardReplayWidget


class _ClipboardWatcher(QObject):
    text_changed = Signal(str)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._clipboard = QApplication.clipboard()
        self._last_text: str | None = None

    def start(self) -> None:
        self._clipboard.dataChanged.connect(self.read_text)
        self.read_text()

    @Slot()
    def refresh(self) -> None:
        self._last_text = None
        self.read_text()

    @Slot()
    def read_text(self) -> None:
        mime = self._clipboard.mimeData()
        text = mime.text() if mime is not None and mime.hasText() else ""
        if text != self._last_text:
            self._last_text = text
            self.text_changed.emit(text)

    @Slot()
    def stop(self) -> None:
        self._clipboard.dataChanged.disconnect(self.read_text)
        self.deleteLater()


class ClipboardReplayPlugin(BasePlugin[ClipboardReplayConfig]):
    """Monitor clipboard changes and dispatch content to registered handlers."""

    _stop_watcher = Signal()
    _output = Signal(object)

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="剪贴板助手",
            version="1.0.0",
            description="监听剪贴板内容，识别后交给对应处理器执行",
            window_mode=WindowMode.TAB,
            other_info=ClipboardReplayConfig,
        )

    def _setup_subscriptions(self) -> None:
        pass

    def _create_widget(self) -> QWidget:
        widget = ClipboardReplayWidget()
        self._output.connect(
            widget.handle_output, Qt.ConnectionType.QueuedConnection)
        return widget

    def on_widget_created(self, widget: QWidget) -> None:
        self._report("剪贴板监听已启动" if self._enabled() else "剪贴板监听已暂停",
                     kind="state", enabled=self._enabled())

    def _report(self, message: str, **details: object) -> None:
        self._output.emit({
            "kind": "log",
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "source": "系统",
            **details,
        })

    def on_initialized(self) -> None:
        self._stopped = Event()
        self._watcher: _ClipboardWatcher | None = None
        self._handlers: list[ClipboardHandler] = []
        for handler_type in HANDLER_TYPES:
            try:
                handler = handler_type(self.data_dir, self.logger, parent=self)
                handler.output.connect(self._output)
                handler.set_enabled(self._handler_enabled(handler))
                self._handlers.append(handler)
            except Exception as error:
                self.logger.error(
                    f"Cannot initialize {handler_type.__name__}: {error}")
                self._report(
                    f"无法初始化 {handler_type.__name__}：{error}", kind="error")
        self.config_changed.connect(self._on_settings_changed)
        for callback in list(getattr(self, "_watcher_stop_callbacks", [])):
            try:
                self._stop_watcher.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._watcher_stop_callbacks = []
        self.run_on_gui(self._start_watcher)
        self.logger.info("Clipboard replay monitoring initialized")
        self._report("剪贴板监听已启动" if self._enabled() else "剪贴板监听已暂停",
                     kind="state", enabled=self._enabled())

    def _start_watcher(self) -> None:
        if self._stopped.is_set():
            return
        application = QApplication.instance()
        if application is None:
            self.logger.error("Clipboard monitoring requires QApplication")
            return
        self._watcher = _ClipboardWatcher(application)
        self._watcher.text_changed.connect(
            self._on_text_changed, Qt.ConnectionType.QueuedConnection)
        self._stop_watcher.connect(
            self._watcher.stop, Qt.ConnectionType.QueuedConnection)
        self._watcher_stop_callbacks = [self._watcher.stop]
        self._watcher.start()

    def _enabled(self) -> bool:
        return not self._stopped.is_set() and bool(
            self.other_info and self.other_info.enable_feature)

    def _handler_enabled(self, handler: ClipboardHandler) -> bool:
        return self._enabled() and bool(
            getattr(self.other_info, handler.config_key(), True))

    @Slot(str)
    def _on_text_changed(self, text: str) -> None:
        if not self._enabled():
            return
        for handler in self._handlers:
            try:
                handler.process(text)
            except Exception as error:
                self.logger.error(
                    f"Clipboard handler {type(handler).__name__} failed: {error}")
                handler.report(f"处理失败：{error}", kind="error")

    @Slot(str, object)
    def _on_settings_changed(self, name: str, value) -> None:
        if name == "enable_feature":
            self._report("剪贴板监听已启动" if self._enabled() else "剪贴板监听已暂停",
                         kind="state", enabled=self._enabled())
        refresh = False
        for handler in self._handlers:
            if name not in ("enable_feature", handler.config_key()):
                continue
            try:
                enabled = self._handler_enabled(handler)
                if handler.enabled != enabled:
                    handler.set_enabled(enabled)
                    refresh = refresh or enabled
            except Exception as error:
                self.logger.error(
                    f"Cannot update {type(handler).__name__}: {error}")
                self._report(
                    f"无法更新 {type(handler).__name__}：{error}", kind="error")
        if value and refresh and self._watcher is not None:
            self.run_on_gui(self._watcher.refresh)

    def on_shutdown(self) -> None:
        self._stopped.set()
        self._report("插件已停止", kind="state", enabled=False)
        self._stop_watcher.emit()
        for handler in self._handlers:
            try:
                handler.shutdown()
            except Exception as error:
                self.logger.error(
                    f"Cannot stop {type(handler).__name__}: {error}")
