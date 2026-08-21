"""
openms - 插件主类
"""
from __future__ import annotations

from plugin_sdk import BasePlugin, PluginInfo, WindowMode
from .config import OpenmsConfig
from plugins.services.openms import OpenmsService


def _load_icon():
    """从插件目录加载图标（取自 https://openms.top/favicon.ico）"""
    try:
        from pathlib import Path
        from PyQt5.QtGui import QIcon
        icon_path = Path(__file__).parent / "icon.svg"
        if icon_path.exists():
            return QIcon(str(icon_path))
    except Exception:
        pass
    return None


class OpenmsPlugin(BasePlugin[OpenmsConfig]):
    """无窗口开源扫雷网服务接口插件"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="openms",
            version="1.0.0",
            author="developer",
            description="无窗口开源扫雷网服务接口插件",
            window_mode=WindowMode.CLOSED,
            icon=_load_icon(),
            other_info=OpenmsConfig,
        )

    def _setup_subscriptions(self) -> None:
        pass

    def on_initialized(self) -> None:
        self.logger.info("OpenmsPlugin 已初始化")
        
        # 注册服务接口
        self.register_service(self, protocol=OpenmsService)
        self.logger.info("OpenmsService 已注册")
        
        self.config_changed.connect(self._on_config_changed)

    def _on_config_changed(self, name: str, value) -> None:
        """配置变化回调"""
        self.logger.info(f"配置变化: {name} = {value}")
