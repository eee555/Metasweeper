import time
from PyQt5 import QtWidgets
# from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtNetwork import QLocalSocket, QLocalServer
import sys
import os
import argparse
import mainWindowGUI as mainWindowGUI
import mineSweeperGUI as mineSweeperGUI
import ms_toollib as ms
import ctypes
# from ctypes import wintypes
from mp_plugins.context import AppContext
from mp_plugins.events import *
from mp_plugins import PluginManager
from pathlib import Path
# import os

os.environ["QT_FONT_DPI"] = "96"


# def patch_env():
#     import os


#     env = os.environ.copy()
#     root = os.path.dirname(os.path.abspath(__file__))  # 你的项目根目录
#     env["PYTHONPATH"] = root
#     return env
def get_paths():
    if getattr(sys, "frozen", False):
        # 打包成 exe
        dir = os.path.dirname(sys.executable)  # exe 所在目录
    else:
        dir = os.path.dirname(os.path.abspath(__file__))

    return dir


def patch_env():
    import os
    import sys

    env = os.environ.copy()

    if getattr(sys, "frozen", False):
        # 打包成 exe，库解压到 _MEIPASS
        root = getattr(sys, "_MEIPASS", None)
    else:
        # 调试模式，库在项目目录
        root = os.path.dirname(os.path.abspath(__file__))

    env["PYTHONPATH"] = root
    return env


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
    if not os.path.exists(file_path):
        print("ERROR: file not found")
        return 2

    # 搜集目录或文件下的所有evf和evfs文件
    evf_evfs_files = []
    if os.path.isfile(file_path) and (
        file_path.endswith(".evf") or file_path.endswith(".evfs")
    ):
        evf_evfs_files = [os.path.abspath(file_path)]
    elif os.path.isdir(file_path):
        evf_evfs_files = [
            os.path.abspath(os.path.join(root, file))
            for root, dirs, files in os.walk(file_path)
            for file in files
            if file.endswith(".evf") or file.endswith(".evfs")
        ]

    if not evf_evfs_files:
        print("ERROR: must be evf or evfs files or directory")
        return 2

    # 实例化一个MineSweeperGUI出来
    app = QtWidgets.QApplication(sys.argv)
    mainWindow = mainWindowGUI.MainWindow()
    ui = mineSweeperGUI.MineSweeperGUI(mainWindow, sys.argv)

    for ide, e in enumerate(evf_evfs_files):
        if not ui.checksum_module_ok():
            print("ERROR: ???")
            return 2
        if e.endswith(".evf"):
            # 检验evf文件是否合法
            video = ms.EvfVideo(e)
            try:
                video.parse()
            except:
                evf_evfs_files[ide] = (e, 2)
            else:
                checksum = ui.checksum_guard.get_checksum(
                    video.raw_data[: -(len(video.checksum) + 2)]
                )
                if video.checksum == checksum:
                    evf_evfs_files[ide] = (e, 0)
                else:
                    evf_evfs_files[ide] = (e, 1)
        elif e.endswith(".evfs"):
            # 检验evfs文件是否合法
            videos = ms.Evfs(e)
            try:
                videos.parse()
            except:
                evf_evfs_files[ide] = (e, 2)
            else:
                if videos.len() <= 0:
                    evf_evfs_files[ide] = (e, 2)
                checksum = ui.checksum_guard.get_checksum(
                    videos[0].evf_video.raw_data)
                if video.checksum != checksum:
                    evf_evfs_files[ide] = (e, 1)
                    continue
                for idcell, cell in enumerate(videos[1:]):
                    checksum = ui.checksum_guard.get_checksum(
                        cell.evf_video.raw_data + videos[idcell - 1].checksum
                    )
                    if cell.evf_file.checksum != checksum:
                        evf_evfs_files[ide] = (e, 1)
                        continue
                evf_evfs_files[ide] = (e, 0)
    # print(evf_evfs_files)
    return 0


if __name__ == "__main__":
    # metaminesweeper.exe -c filename.evf用法，检查文件的合法性
    # metaminesweeper.exe -c filename.evfs
    # metaminesweeper.exe -c ./somepath/replay
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--check", help="检查文件合法性")
    args, _ = parser.parse_known_args()

    if args.check:
        exit_code = cli_check_file(args.check)
        sys.exit(exit_code)
    env = patch_env()
    context = AppContext(name="Metasweeper", version="1.0.0", display_name="元扫雷",
                         plugin_dir=(Path(get_paths()) / "plugins").as_posix(),
                         app_dir=get_paths()
                         )
    PluginManager.instance().context = context

    PluginManager.instance().start(Path(get_paths()) / "plugins", env)

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
        # ui.mainWindow.game_setting = ui.game_setting

        # _translate = QtCore.QCoreApplication.translate
        hwnd = int(ui.mainWindow.winId())

        SetWindowDisplayAffinity = ctypes.windll.user32.SetWindowDisplayAffinity
        ui.disable_screenshot = lambda: ... if SetWindowDisplayAffinity(
            hwnd, 0x00000011) else 1/0
        ui.enable_screenshot = lambda: ... if SetWindowDisplayAffinity(
            hwnd, 0x00000000) else 1/0

        sys.exit(app.exec_())
        PluginManager.instance().stop()
        ...
    # except:
    #     pass

# 最高优先级
# 计时器快捷键切换
# 可信的历史记录
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
#           bbbv_s, (op_solved), (isl_solved)
# 录像静态类：bbbv，op, isl, cell0, cell1, cell2, cell3, cell4, cell5, cell6,
#           cell7, cell8, fps, (hizi)
# 录像动态类（依赖分析）：pluck
# 其他类：checksum_ok, race_identifier, mode, is_offical, is_fair

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
