# from fbs_runtime.application_context.PyQt5 import ApplicationContext
import time
import time
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtNetwork import QLocalSocket, QLocalServer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtNetwork import QLocalSocket, QLocalServer
import sys
import os
import mainWindowGUI as mainWindowGUI
import mineSweeperGUI as mineSweeperGUI
import ctypes
from ctypes import wintypes
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


def find_window(class_name, window_name):
    """
    查找指定窗口的句柄。

    Args:
        class_name (str): 要查找的窗口的类名。
        window_name (str): 要查找的窗口的标题。

    Returns:
        int: 查找到的窗口的句柄。如果未找到窗口，则抛出异常。

    Raises:
        ctypes.WinError: 如果未找到指定窗口，则抛出此异常。

    """
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND

    hwnd = user32.FindWindowW(class_name, window_name)
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())
    return hwnd


if __name__ == "__main__":
    # QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    try:
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
                lambda: on_new_connection(localServer=localServer))
            mainWindow = mainWindowGUI.MainWindow()
            ui = mineSweeperGUI.MineSweeperGUI(mainWindow, sys.argv)
            ui.mainWindow.show()
            # ui.mainWindow.game_setting = ui.game_setting

            _translate = QtCore.QCoreApplication.translate
            hwnd = find_window(None, _translate("MainWindow", "元扫雷"))

            SetWindowDisplayAffinity = ctypes.windll.user32.SetWindowDisplayAffinity
            ui.disable_screenshot = lambda: ... if SetWindowDisplayAffinity(
                hwnd, 0x00000011) else 1/0
            ui.enable_screenshot = lambda: ... if SetWindowDisplayAffinity(
                hwnd, 0x00000000) else 1/0

            sys.exit(app.exec_())
            ...
    except:
        pass

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
