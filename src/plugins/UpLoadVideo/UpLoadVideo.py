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
from mp_plugins.events import GameEndEvent


class UpLoadVideoConfig(BaseConfig):
    user: TextSetting
    passwd: TextSetting
    upload_circle: NumberSetting
    auto_upload: BoolSetting
    upload_type: SelectSetting


class UpLoadVideo(BasePlugin):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._context: AppContext
        self._config = UpLoadVideoConfig(
            TextSetting("用户名", "user"),
            TextSetting("密码", "passwd"),
            NumberSetting(name="上传周期", value=0, min_value=1,
                          max_value=10, step=1),
            BoolSetting("自动上传", True),
            SelectSetting("上传类型", "自动上传", options=["自动上传", "手动上传"]),
        )

    def build_plugin_context(self) -> None:
        self._plugin_context.name = "UpLoadVideo"
        self._plugin_context.display_name = "上传录像"
        self._plugin_context.version = "1.0.0"
        self._plugin_context.description = "上传录像"
        self._plugin_context.author = "LjzLoser"

    def initialize(self) -> None:
        return super().initialize()

    def shutdown(self) -> None:
        return super().shutdown()

    @BasePlugin.event_handler(GameEndEvent)
    def on_game_end(self, event: GameEndEvent) -> GameEndEvent:
        return event


if __name__ == "__main__":
    try:
        import sys

        args = sys.argv[1:]
        host = args[0]
        port = int(args[1])
        plugin = UpLoadVideo()
        plugin.run(host, port)
    except Exception as e:
        with open("UpLoadVideo_error.log", "w", encoding="utf-8") as f:
            f.write(str(e))
