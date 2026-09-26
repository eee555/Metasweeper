"""
gen_plugin.py - Plugin Generator / 插件生成器

Usage / 用法:
    python gen_plugin.py <PluginName>

Generates a plugin skeleton under src/plugins/<PluginName>/.
<PluginName> must be a valid Python class name (PascalCase).
生成插件骨架到 src/plugins/<PluginName>/，名称须为有效帕斯卡命名类名。

Example / 示例:
    python gen_plugin.py MyPlugin
    -> creates / 创建 src/plugins/MyPlugin/MyPlugin.py

The generated plugin imports BasePlugin from plugin_sdk and subscribes
to common events (GameFinishedEvent, BoardUpdateEvent, etc.).
生成的插件从 plugin_sdk 导入 BasePlugin，并订阅常见事件。
"""

import os
import sys
from pathlib import Path


def is_valid_class_name(name: str) -> bool:
    """检查是否为有效的Python类名"""
    if not name or not isinstance(name, str):
        return False
    if not name.isidentifier():
        return False
    if name[0].islower():
        return False
    return True


def build_py_file_content(name: str) -> str:
    """生成Python文件内容"""
    template = f'''
import sys
import os
from pathlib import Path
import msgspec
import zmq

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

from plugin_sdk import (
    BasePlugin, PluginInfo, make_plugin_icon, WindowMode,
    OtherInfoBase, IntConfig, TextConfig, ChoiceConfig,
)
from plugin_sdk.server_bridge import GameServerBridge
from shared_types.commands import NewGameCommand
from shared_types.events import (
    GameFinishedEvent, BoardUpdateEvent,
    GameStatusChangeEvent, ShowPluginManagerEvent,
)


class {name}(BasePlugin):
    def __init__(self) -> None:
        super().__init__()
        self._config_widget: QWidget | None = None

    def build_plugin_context(self) -> None:
        self._plugin_context.name = "{name}"
        self._plugin_context.display_name = "{name}"
        self._plugin_context.version = "1.0.0"
        self._plugin_context.description = "{name}"
        self._plugin_context.author = ""

    def initialize(self) -> None:
        return super().initialize()

    def shutdown(self) -> None:
        return super().shutdown()
'''
    return template


if __name__ == "__main__":
    print("Building plugin...")
    args = sys.argv[1:]
    if len(args) != 1:
        print("Usage: gen_plugin.py <plugin_name>")
        exit(1)
    name = args[0]
    if not is_valid_class_name(name):
        print("Invalid plugin name")
        exit(1)
    current_path = os.path.dirname(os.path.abspath(__file__))
    plugin_path = Path(current_path) / "plugins" / name
    plugin_path.mkdir(parents=True, exist_ok=True)
    plugin_file = plugin_path / f"{name}.py"
    with open(plugin_file, "w", encoding="utf-8") as f:
        context = build_py_file_content(name)
        f.write(context)
    print("gen py file success")
