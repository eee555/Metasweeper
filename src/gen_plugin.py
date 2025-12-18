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
import msgspec
import zmq

if getattr(sys, "frozen", False):  # 检查是否为pyInstaller生成的EXE
    application_path = os.path.dirname(sys.executable)
    sys.path.append(application_path + "/../../")
    print(application_path + "/../../")
else:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../")
from mp_plugins import BasePlugin, BaseConfig
from mp_plugins.base.config import *
from mp_plugins.context import AppContext
from mp_plugins.events import *

class {name}Config(BaseConfig):
    pass


class {name}(BasePlugin):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._context: AppContext
        self._config = {name}Config()

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



if __name__ == "__main__":
    try:
        import sys

        args = sys.argv[1:]
        host = args[0]
        port = int(args[1])
        plugin = {name}()
        # 捕获退出信号，优雅关闭
        import signal

        def signal_handler(sig, frame):
            plugin.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        plugin.run(host, port)
    except Exception:
        pass
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
