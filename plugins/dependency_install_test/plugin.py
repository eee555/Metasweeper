"""
dependency_install_test - 插件主类
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget
from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
import humanize

from .widgets import DependencyInstallTestWidget


class DependencyInstallTestPlugin(BasePlugin):
    """Extra dependency installation test"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="依赖安装测试",
            version="1.0.0",
            author="Local test",
            description="Extra dependency installation test",
            window_mode=WindowMode.TAB,
            icon=make_plugin_icon("#4CAF50", "D"),
        )

    def _setup_subscriptions(self) -> None:
        pass

    def _create_widget(self) -> QWidget | None:
        self._widget = DependencyInstallTestWidget(
            humanize.__version__, humanize.__file__, humanize.intcomma(1234567))
        return self._widget

    def on_initialized(self) -> None:
        self.logger.info("DependencyInstallTestPlugin 已初始化")
