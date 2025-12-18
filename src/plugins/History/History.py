
import sys
import os
import msgspec
import zmq
import sqlite3


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


class HistoryConfig(BaseConfig):
    pass


class History(BasePlugin):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._context: AppContext
        self._config = HistoryConfig()

    def build_plugin_context(self) -> None:
        self._plugin_context.name = "History"
        self._plugin_context.display_name = "历史记录"
        self._plugin_context.version = "1.0.0"
        self._plugin_context.description = "History"
        self._plugin_context.author = "ljzloser"

    def initialize(self) -> None:
        db_path = self.path / "history.db"
        if not db_path.exists():
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
create table main.history
(
    replay_id        INTEGER
        primary key,
    termination_type INTEGER not null,
    player_nick      TEXT    not null,
    level            TEXT    not null,
    nf               BOOLEAN not null,
    timeth           INTEGER not null,
    bbbv_board       INTEGER not null,
    bbbv_completed   INTEGER not null
);
                """
            )
            conn.commit()
            cursor.execute(
                """
create table main.replays
(
    id        INTEGER
        primary key,
    date      DATETIME              not null,
    replay    BLOB                  not null,
    processed BOOLEAN default FALSE not null
);
                """
            )
            conn.close()
        return super().initialize()

    def shutdown(self) -> None:
        return super().shutdown()

    @BasePlugin.event_handler(GameEndEvent)
    def on_game_end(self, event: GameEndEvent) -> None:
        pass


if __name__ == "__main__":
    try:
        import sys

        args = sys.argv[1:]
        host = args[0]
        port = int(args[1])
        plugin = History()
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
