"""
{plugin_name} - {description}

带配置系统的插件示例。
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

from plugin_sdk import (
    BasePlugin, PluginInfo, make_plugin_icon, WindowMode,
    OtherInfoBase, BoolConfig, IntConfig,
)
from shared_types.events import VideoSaveEvent


class {PluginName}Config(OtherInfoBase):
    """插件配置"""

    enable_logging = BoolConfig(
        default=True,
        label="启用日志",
        description="是否记录游戏数据到日志",
    )

    max_records = IntConfig(
        default=100,
        label="最大记录数",
        min_value=10,
        max_value=1000,
    )


class {PluginName}Widget(QWidget):
    """插件 UI"""

    _update_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._label = QLabel("等待游戏数据...")
        layout.addWidget(self._label)

        self._update_signal.connect(self._on_update)

    def _on_update(self, text: str):
        self._label.setText(text)


class {PluginName}(BasePlugin):
    """{description}"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="{plugin_name}",
            version="1.0.0",
            description="{description}",
            window_mode=WindowMode.TAB,
            icon=make_plugin_icon("#2196F3", "C"),
            other_info={PluginName}Config,  # 绑定配置类
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget | None:
        self._widget = {PluginName}Widget()
        return self._widget

    def on_initialized(self) -> None:
        self.logger.info("{PluginName} 已初始化")

        # 连接配置变化信号
        self.config_changed.connect(self._on_config_changed)

        # 读取配置
        if self.other_info:
            self.logger.info(
                f"配置: enable_logging={self.other_info.enable_logging}")

    def _on_config_changed(self, name: str, value):
        self.logger.info(f"配置变化: {name} = {value}")

    def _on_video_save(self, event: VideoSaveEvent):
        if self.other_info and self.other_info.enable_logging:
            self.logger.info(f"游戏数据: 用时={event.rtime}s")
        self._widget._update_signal.emit(f"用时: {event.rtime:.2f}s")
