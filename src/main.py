from policy_guard import enforce_policy_integrity

if __name__ == "__main__":
    enforce_policy_integrity()

import time
from PySide6 import QtWidgets
from PySide6.QtNetwork import QLocalSocket, QLocalServer
import sys
import os
import argparse
import mainWindowGUI as mainWindowGUI
import mineSweeperGUI as mineSweeperGUI
import ms_toollib as ms
from pathlib import Path
from utils.app_logger import logger
from app.startup_platform import on_new_connection, configure_capture_guard
from app.cli_check import cli_check_file
from app.plugin_process import start_plugin_process, cleanup_plugin_process
from app.plugin_commands import register_plugin_commands
from app.plugin_queries import register_plugin_queries

# 插件系统（新）
from plugin_sdk import GameServerBridge
from shared_types.queries import (
    GetBoardStateQuery, GetGameStatusQuery, GetGameContextQuery,
    BoardStateResult, GameStatusResult, GameContextResult, ControlPermissions,
)
from shared_types.enums import GameLevel, GameMode
from config.constants import GAME_EVENT_STATE_MAP

os.environ["QT_FONT_DPI"] = "96"

# 打包模式下，把工作目录切到资源目录，保证相对路径（media/ 等）可用
if getattr(sys, "frozen", False):
    os.chdir(str(Path(__file__).resolve().parent))


if __name__ == "__main__":
    sys.excepthook = lambda typ, val, tb: (
        QtWidgets.QMessageBox.critical(
            None, "程序错误",
            "".join(__import__("traceback").format_exception(typ, val, tb)),
        ) if QtWidgets.QApplication.instance() else None
    ) or sys.exit(1) or None

    # metasweeper.exe -c filename.evf用法，检查文件的合法性
    # metasweeper.exe -c filename.evfs
    # metasweeper.exe -c ./somepath/replay
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--check", help="检查文件合法性")
    args, _ = parser.parse_known_args()

    if args.check:
        exit_code = cli_check_file(args.check)
        sys.exit(exit_code)

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("windowsvista" if sys.platform == "win32" else "Fusion")

    if sys.platform == "darwin":
        # macOS 下 Finder 双击录像时，文件通过 QFileOpenEvent 传递而非命令行参数；
        # 已有实例在运行时同样由系统把打开事件投递到当前实例。
        class _FileOpenEventFilter(QtCore.QObject):
            def eventFilter(self, obj, event):
                if event.type() == QtCore.QEvent.FileOpen and event.file():
                    for win in QApplication.topLevelWidgets():
                        if isinstance(win, mainWindowGUI.MainWindow):
                            win.dropFileSignal.emit(event.file())
                            break
                return False

        _file_open_filter = _FileOpenEventFilter()
        app.installEventFilter(_file_open_filter)
    serverName = "MineSweeperServer"
    socket = QLocalSocket()
    socket.connectToServer(serverName)
    if socket.waitForConnected(500):
        if len(sys.argv) == 2:
            filePath = sys.argv[1]
            socket.write(filePath.encode())
            socket.flush()
        time.sleep(0.5)
        app.quit()
    else:
        localServer = QLocalServer()
        localServer.listen(serverName)
        localServer.newConnection.connect(
            lambda: on_new_connection(localServer)
        )
        # 插件通信端口被占用时（如崩溃残留的进程），降级为禁用插件而不是崩溃
        plugins_disabled = False
        try:
            GameServerBridge.instance().start()
        except Exception as e:
            GameServerBridge.instance().stop()  # 清理半初始化状态
            plugins_disabled = True
            logger.error(f"GameServerBridge 启动失败: {e}")
            QtWidgets.QMessageBox.warning(
                None, "元扫雷",
                "插件通信端口被占用（可能存在残留的元扫雷进程），"
                "本次启动插件功能将被禁用。\n"
                "关闭所有元扫雷相关进程后重新打开即可恢复。")
        mainWindow = mainWindowGUI.MainWindow()
        ui = mineSweeperGUI.MineSweeperGUI(mainWindow, sys.argv)
        ui.mainWindow.show()

        # 程序就绪音：主窗口已显示、音效设置也已由 superGUI 初始化完成。
        # 内部延迟一小段等待音频后端，默认关闭音效时此方法直接返回。
        # 同时记录启动设置，供 SetSoundCommand(reset=True) 精确还原。
        try:
            from utils.sound_manager import SoundManager
            from app.sound_applier import capture_startup_settings
            capture_startup_settings(ui)
            SoundManager.instance().play_ready()
        except Exception as exc:
            from utils.app_logger import logger
            logger.warning(f"启动音效初始化失败，已静默: {exc}")

        # ── 启动 ZMQ Server + 插件管理器 ──

        plugin_process = start_plugin_process(ui, mainWindow, plugins_disabled)

        ui._plugin_process = plugin_process  # 保存引用，防止被 GC

        # 等插件连接后同步初始语言
        from PySide6.QtCore import QTimer
        from shared_types.events import LanguageChangeEvent
        if not plugins_disabled:
            QTimer.singleShot(2000, lambda: GameServerBridge.instance().send_event(
                LanguageChangeEvent(language=ui.language)))

        register_plugin_commands(GameServerBridge.instance(), ui)
        register_plugin_queries(GameServerBridge.instance(), ui)

        configure_capture_guard(ui)

        def _on_about_to_quit():
            # 退出前停掉所有在响的音效并取消未播出的补播，避免 Qt 音频后端
            # 在播放中被销毁导致告警/崩溃。
            try:
                from utils.sound_manager import SoundManager
                SoundManager.instance().stop_all()
            except Exception:
                pass
            cleanup_plugin_process(plugin_process)

        app.aboutToQuit.connect(_on_about_to_quit)
        sys.exit(app.exec())

# 最高优先级
# 计时器快捷键切换
# 选择某些国家报错，布维岛(难复现)
# OBR修改局面还会报错的情况（不确定，需要跟踪）
# 筛选局面的条件设置错误时，不能显式报告

# 次优先级
# 自定义模式弹窗
# 记录pop的读写改到ui后（？？？）

# 最低优先级
# 优化判雷引擎


# 局面标记的约定：
# 其中0代表空；1到8代表数字1到8；10代表未打开；11代表玩家或算法确定是雷；12代表算法确定不是雷；
# 14表示踩到了雷游戏失败以后显示的标错的雷对应叉雷，15表示踩到了雷游戏失败了对应红雷；
# 16表示白雷
# 18表示局面中，由于双击的高亮，导致看起来像0的格子

# 游戏模式的约定：
# 0，4, 5, 6, 7, 8, 9, 10代表：标准0、win74、经典无猜5、强无猜6、弱无猜7、准无猜8、强可猜9、弱可猜10

# 局面状态的约定：
# 'ready'：预备状态。表示局面完全没有左键点过，可能被右键标雷；刚打开或点脸时进入这种状态。
#         此时可以改雷数、改格子大小（ctrl+滚轮）、行数、列数（拖拉边框）。
# 'study': 研究状态。截图后进入。应该设计第二种方式进入研究状态，没想好。
# 'show': 游戏中，展示智能分析结果，按住空格进入。
# 'modify': 调整状态。'ready'下，拖拉边框时进入，拖拉结束后自动转为'ready'。未使用，拟废弃。
# 'playing': 正在游戏状态、标准模式、不筛选3BV、且没有看概率计算结果，游戏结果是official的。
# 'joking': 正在游戏状态，游戏中看过概率计算结果，游戏结果不是official的。
# 'fail': 游戏失败，踩雷了。
# 'win': 游戏成功。
# 'jofail': 游戏失败，游戏结果不是official的。
# 'jowin': 游戏成功，游戏结果不是official的。
# 'display':正在播放录像。
# 'showdisplay':正在一边播放录像、一边看概率。播放录像时按空格进入。

# 指标命名：
# 游戏静态类：race_identifier, mode
# 游戏动态类：rtime, left, right, double，cl，left_s，right_s, double_s, cl_s, path,
#           flag, flag_s
# 录像动态类：etime, stnb, rqp, qg, ioe, thrp, corr, ce, ce_s, bbbv_solved,
#           bbbv_s, (op_solved), (isl_solved), (fps)
# 录像静态类：bbbv，op, isl, cell0, cell1, cell2, cell3, cell4, cell5, cell6,
#           cell7, cell8, zini, hzini
# 录像动态类（依赖分析）：pluck
# 其他类：race_identifier, mode, is_offical, is_fair

# 工具箱中局面状态和鼠标状态的定义：

# GameBoardState::Ready => Ok(1),
# GameBoardState::Playing => Ok(2),
# GameBoardState::Win => Ok(3),
# GameBoardState::Loss => Ok(4),
# GameBoardState::PreFlaging => Ok(5),
# GameBoardState::Display => Ok(6),

# MouseState::UpUp => Ok(1),
# MouseState::UpDown => Ok(2),
# MouseState::UpDownNotFlag => Ok(3),
# MouseState::DownUp => Ok(4),
# MouseState::Chording => Ok(5),
# MouseState::ChordingNotFlag => Ok(6),
# MouseState::DownUpAfterChording => Ok(7),
# MouseState::Undefined => Ok(8),
