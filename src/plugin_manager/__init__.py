"""
插件管理器包。

公共符号按需导入，避免主进程仅导入 ``plugin_manager.app_paths`` 时
加载完整 Qt 窗口与插件运行时。
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "LogConfig",
    "PluginManager",
    "PluginManagerWindow",
    "EventDispatcher",
    "PluginLoader",
    "run_plugin_manager_process",
    "OtherInfoWidget",
    "OtherInfoScrollArea",
    "PluginConfigManager",
]

_EXPORTS = {
    "LogConfig": (".logging_setup", "LogConfig"),
    "PluginManager": (".plugin_manager", "PluginManager"),
    "run_plugin_manager_process": (".plugin_manager", "run_plugin_manager_process"),
    "EventDispatcher": (".event_dispatcher", "EventDispatcher"),
    "PluginLoader": (".plugin_loader", "PluginLoader"),
    "PluginManagerWindow": (".main_window", "PluginManagerWindow"),
    "OtherInfoWidget": (".config_widget", "OtherInfoWidget"),
    "OtherInfoScrollArea": (".config_widget", "OtherInfoScrollArea"),
    "PluginConfigManager": (".config_manager", "PluginConfigManager"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
