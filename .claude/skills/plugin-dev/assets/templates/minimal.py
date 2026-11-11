"""
{plugin_name} - {description}

一个最小可行插件示例。
图标优先使用同级有效的 icon.svg；否则依次使用 PluginInfo.icon 和默认图标。
"""
from __future__ import annotations

from plugin_sdk import BasePlugin, PluginInfo
from shared_types.events import VideoSaveEvent


class {PluginName}(BasePlugin):
    """{description}"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="{plugin_name}",
            version="1.0.0",
            description="{description}",
            window_mode=WindowMode.CLOSED,  # 无界面
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def on_initialized(self) -> None:
        self.logger.info("{PluginName} 已初始化")

    def _on_video_save(self, event: VideoSaveEvent):
        self.logger.info(f"游戏结束: 用时={event.rtime}s, 3BV={event.bbbv}")
