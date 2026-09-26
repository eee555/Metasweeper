"""
{plugin_name} - {description}

带 GUI 界面的插件示例。
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PySide6.QtCore import Signal

from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from shared_types.events import VideoSaveEvent


class {PluginName}Widget(QWidget):
    """插件 UI"""

    _update_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._title = QLabel("{PluginName}")
        self._title.setStyleSheet(
            "font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(self._title)

        self._info = QLabel("等待游戏数据...")
        layout.addWidget(self._info)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        self._update_signal.connect(self._on_update)

    def _on_update(self, text: str):
        self._log.append(text)


class {PluginName}(BasePlugin):
    """{description}"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="{plugin_name}",
            version="1.0.0",
            author="{author}",
            description="{description}",
            window_mode=WindowMode.TAB,
            icon=make_plugin_icon("#4CAF50", "{icon_char}"),
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget | None:
        self._widget = {PluginName}Widget()
        return self._widget

    def on_initialized(self) -> None:
        self.logger.info("{PluginName} 已初始化")

    def _on_video_save(self, event: VideoSaveEvent):
        self.logger.info(f"游戏结束: 用时={event.rtime}s")
        self._widget._update_signal.emit(
            f"[{event.rtime:.2f}s] 3BV={event.bbbv}")
