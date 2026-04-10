"""
插件管理器模块

基于 lib_zmq_plugins 实现的插件系统，支持：
- 插件同时具备后台数据处理和界面交互能力
- 事件分发机制
- 动态加载插件
- 独立的主界面窗口
- 插件自定义配置系统
"""

from .plugin_base import BasePlugin, PluginInfo, make_plugin_icon, WindowMode, LogLevel
from .logging_setup import LogConfig
from .plugin_manager import PluginManager, run_plugin_manager_process
from .event_dispatcher import EventDispatcher
from .plugin_loader import PluginLoader
from .server_bridge import GameServerBridge
from .main_window import PluginManagerWindow
from .config_types import (
    BaseConfig,
    BoolConfig,
    IntConfig,
    FloatConfig,
    ChoiceConfig,
    TextConfig,
    ColorConfig,
    FileConfig,
    PathConfig,
    LongTextConfig,
    RangeConfig,
    OtherInfoBase,
)
from .config_widget import OtherInfoWidget, OtherInfoScrollArea
from .config_manager import PluginConfigManager

__all__ = [
    # 核心类
    "BasePlugin",
    "PluginInfo",
    "WindowMode",
    "LogLevel",
    "LogConfig",
    "make_plugin_icon",
    # 管理器
    "PluginManager",
    "PluginManagerWindow",
    "EventDispatcher",
    "PluginLoader",
    "GameServerBridge",
    "run_plugin_manager_process",
    # 配置系统
    "BaseConfig",
    "BoolConfig",
    "IntConfig",
    "FloatConfig",
    "ChoiceConfig",
    "TextConfig",
    "ColorConfig",
    "FileConfig",
    "PathConfig",
    "LongTextConfig",
    "RangeConfig",
    "OtherInfoBase",
    "OtherInfoWidget",
    "OtherInfoScrollArea",
    "PluginConfigManager",
]