import sys
import os

# ── 重定向所有 stdout/stderr 到日志文件（打包后无终端时捕获所有输出） ──
class _TeeWriter:
    def __init__(self, original, log_path):
        self._original = original
        self._log = open(log_path, "a", encoding="utf-8", buffering=1)
    def write(self, msg):
        if msg and msg.strip():
            self._log.write(msg)
            self._log.flush()
        if self._original:
            try:
                self._original.write(msg)
            except Exception:
                pass
    def flush(self):
        self._log.flush()
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass

_log_dir = os.path.join(os.path.expanduser("~"), ".metasweeper")
os.makedirs(_log_dir, exist_ok=True)
_log_path = os.path.join(_log_dir, "crash.log")
sys.stdout = _TeeWriter(sys.__stdout__, _log_path)
sys.stderr = _TeeWriter(sys.__stderr__, _log_path)

import time
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication
from PyQt5.QtNetwork import QLocalSocket, QLocalServer
import argparse
import json
import mainWindowGUI as mainWindowGUI
import mineSweeperGUI as mineSweeperGUI
import ms_toollib as ms
import ctypes
from pathlib import Path
from utils.app_logger import logger

# 插件系统（新）
from plugin_sdk import GameServerBridge
from plugin_manager.app_paths import get_env_for_subprocess
from shared_types.commands import NewGameCommand, MouseClickCommand
from shared_types.enums import GameLevel
import subprocess
from config.constants import (
    BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT,
)

os.environ["QT_FONT_DPI"] = "96"


def on_new_connection(localServer: QLocalServer):
    """当新连接进来时，接受连接并将文件路径传递给主窗口"""
    socket = localServer.nextPendingConnection()
    if socket:
        socket.readyRead.connect(lambda: on_ready_read(socket))


def on_ready_read(socket: QLocalSocket):
    """从socket读取文件路径并传递给主窗口"""
    if socket and socket.state() == QLocalSocket.ConnectedState:
        # 读取文件路径并调用打开文件
        socket.waitForReadyRead(500)
        file_path = socket.readAll().data().decode()
        for win in QApplication.topLevelWidgets():
            if isinstance(win, mainWindowGUI.MainWindow):
                win.dropFileSignal.emit(file_path)
        socket.disconnectFromServer()  # 断开连接


def cli_check_file(file_path: str) -> int:
    result = {"error": "", "data": []}

    if not os.path.exists(file_path):
        result["error"] = "file not found"
    else:
        evf_evfs_files = []
        if os.path.isfile(file_path):
            if file_path.endswith((".evf", ".evfs")):
                evf_evfs_files = [os.path.abspath(file_path)]
        elif os.path.isdir(file_path):
            for root, _, files in os.walk(file_path):
                for file in files:
                    if file.endswith((".evf", ".evfs")):
                        evf_evfs_files.append(
                            os.path.abspath(os.path.join(root, file)))

        if not evf_evfs_files:
            result["error"] = "must be evf or evfs files or directory"
        else:
            app = QtWidgets.QApplication(sys.argv)
            mainWindow = mainWindowGUI.MainWindow()
            ui = mineSweeperGUI.MineSweeperGUI(mainWindow, sys.argv)

            for ide, e in enumerate(evf_evfs_files):
                if not ui.checksum_module_ok():
                    result["error"] = "checksum module error"
                    break

                if e.endswith(".evf"):
                    video = ms.EvfVideo(e)
                    try:
                        video.parse()
                    except Exception:
                        logger.warning("Failed to parse evf file", exc_info=True)
                        evf_evfs_files[ide] = (e, 2)
                    else:
                        checksum = ui.checksum_guard.get_checksum(
                            video.raw_data[: -(len(video.checksum) + 2)]
                        )
                        evf_evfs_files[ide] = (e, 0 if list(
                            video.checksum) == list(checksum) else 1)
                elif e.endswith(".evfs"):
                    videos = ms.Evfs(e)
                    try:
                        videos.parse()
                    except Exception:
                        logger.warning("Failed to parse evfs file", exc_info=True)
                        evf_evfs_files[ide] = (e, 2)
                    else:
                        if videos.len() <= 0:
                            evf_evfs_files[ide] = (e, 2)
                            continue

                        checksum = ui.checksum_guard.get_checksum(
                            videos[0].evf_video.raw_data)
                        if list(videos[0].checksum) != list(checksum):
                            evf_evfs_files[ide] = (e, 1)
                            continue

                        for idcell, cell in enumerate(videos[1:]):
                            checksum = ui.checksum_guard.get_checksum(
                                cell.evf_video.raw_data +
                                videos[idcell - 1].checksum
                            )
                            if list(cell.evf_video.checksum) != list(checksum):
                                evf_evfs_files[ide] = (e, 1)
                                break
                        else:
                            evf_evfs_files[ide] = (e, 0)

            if not result["error"]:
                result["data"] = [
                    {"file": item[0], "status": item[1]}
                    for item in evf_evfs_files
                    if isinstance(item, tuple) and len(item) == 2
                ]

    output_file = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "out.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    sys.excepthook = lambda typ, val, tb: (
        print("".join(__import__("traceback").format_exception(typ, val, tb)), file=sys.stderr),
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
            lambda: on_new_connection(localServer=localServer)
        )
        mainWindow = mainWindowGUI.MainWindow()
        ui = mineSweeperGUI.MineSweeperGUI(mainWindow, sys.argv)
        ui.mainWindow.show()

        # ── 启动 ZMQ Server + 插件管理器 ──

        _translate = QtCore.QCoreApplication.translate
        data_dir = str(ui.setting_path / "data")

        # 检查插件管理器是否已在运行（上一次崩溃后残存的互斥体）
        _plugin_manager_running = False
        try:
            import win32api
            import win32event
            import winerror
            hMutex = win32event.OpenMutex(0x001F0001, False, "Metasweeper-PluginManager")
            if hMutex:
                win32api.CloseHandle(hMutex)
                _plugin_manager_running = True
        except win32api.error:
            pass  # 互斥体不存在，正常启动

        plugin_process = None

        if not _plugin_manager_running:
            # 打包后直接调用 plugin_manager.exe，开发模式用 python -m
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                plugin_exe = os.path.join(base_dir, "plugin_manager.exe")
                if not os.path.exists(plugin_exe):
                    QtWidgets.QMessageBox.warning(
                        mainWindow, _translate("MainWindow", "插件管理器"),
                        _translate("MainWindow", "找不到 plugin_manager.exe：\n{path}\n\n插件将被禁用。").replace("{path}", plugin_exe),
                    )
                    plugin_process = None
                else:
                    cmd = [plugin_exe, "--mode", "tray", "--data-dir", data_dir]
                    cwd = base_dir
                    try:
                        plugin_process = subprocess.Popen(
                            cmd, cwd=cwd, env=get_env_for_subprocess(),
                        )
                    except Exception as e:
                        QtWidgets.QMessageBox.warning(
                            mainWindow, _translate("MainWindow", "插件管理器"),
                            _translate("MainWindow", "启动 plugin_manager 失败：\n{err}").replace("{err}", str(e)),
                        )
                        plugin_process = None
            else:
                cmd = [sys.executable, "-m", "plugin_manager", "--mode", "tray",
                       "--data-dir", data_dir]
                cwd = os.path.dirname(os.path.abspath(__file__))
                try:
                    plugin_process = subprocess.Popen(
                        cmd, cwd=cwd, env=get_env_for_subprocess(),
                    )
                except Exception as e:
                    logger.warning(f"Failed to start plugin_manager: {e}")
                    plugin_process = None

        ui._plugin_process = plugin_process  # 保存引用，防止被 GC

        GameServerBridge.instance().start()

        # 等插件连接后同步初始语言
        from PyQt5.QtCore import QTimer
        from shared_types.events import LanguageChangeEvent
        QTimer.singleShot(2000, lambda: GameServerBridge.instance().send_event(
            LanguageChangeEvent(language=ui.language)))

        # 注册控制命令处理器（自动在主线程执行）
        def handle_new_game(cmd: NewGameCommand):
            """处理新游戏命令"""
            from lib_zmq_plugins.shared.base import CommandResponse

            if 'new_game' not in ui._allowed_controls:
                return CommandResponse(request_id=cmd.request_id, success=False)

            # 根据 level 确定参数
            if cmd.level == GameLevel.BEGINNER.value:
                rows, cols, mines = BOARD_BEGINNER
            elif cmd.level == GameLevel.INTERMEDIATE.value:
                rows, cols, mines = BOARD_INTERMEDIATE
            elif cmd.level == GameLevel.EXPERT.value:
                rows, cols, mines = BOARD_EXPERT
            else:
                # 自定义模式，使用传入的参数
                rows, cols, mines = cmd.rows, cmd.cols, cmd.mines

            logger.info(
                f"[NewGameCommand] level={cmd.level}, rows={rows}, cols={cols}, mines={mines}")
            ui.setBoard_and_start(rows, cols, mines)
            return CommandResponse(request_id=cmd.request_id, success=True)

        def handle_mouse_click(cmd: MouseClickCommand):
            """处理鼠标点击命令"""
            from lib_zmq_plugins.shared.base import CommandResponse

            if 'mouse_click' not in ui._allowed_controls:
                return CommandResponse(request_id=cmd.request_id, success=False)

            logger.info(
                f"[MouseClickCommand] row={cmd.row}, col={cmd.col}, button={cmd.button}")
            success = ui.execute_cell_click(cmd.row, cmd.col, cmd.button)
            return CommandResponse(request_id=cmd.request_id, success=success)

        GameServerBridge.instance().register_handler(NewGameCommand, handle_new_game)
        GameServerBridge.instance().register_handler(
            MouseClickCommand, handle_mouse_click)

        # _translate = QtCore.QCoreApplication.translate
        hwnd = int(ui.mainWindow.winId())

        SetWindowDisplayAffinity = ctypes.windll.user32.SetWindowDisplayAffinity
        ui.disable_screenshot = lambda: ... if SetWindowDisplayAffinity(
            hwnd, 0x00000011) else 1/0
        ui.enable_screenshot = lambda: (
            ... if SetWindowDisplayAffinity(hwnd, 0x00000000) else 1 / 0
        )

        def _cleanup():
            GameServerBridge.instance().stop()
            if plugin_process is not None and plugin_process.poll() is None:
                plugin_process.terminate()
                plugin_process.wait(timeout=5)

        app.aboutToQuit.connect(_cleanup)
        sys.exit(app.exec_())

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
