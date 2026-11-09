"""平台相关的启动辅助功能。"""

import ctypes
import sys

from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication

import mainWindowGUI
from utils.app_logger import logger
from utils.capture_guard import macos_capture_guard


def on_new_connection(local_server):
    socket = local_server.nextPendingConnection()
    if socket:
        socket.readyRead.connect(lambda: on_ready_read(socket))


def on_ready_read(socket):
    if socket and socket.state() == QLocalSocket.ConnectedState:
        socket.waitForReadyRead(500)
        file_path = socket.readAll().data().decode()
        for win in QApplication.topLevelWidgets():
            if isinstance(win, mainWindowGUI.MainWindow):
                win.dropFileSignal.emit(file_path)
        socket.disconnectFromServer()


def configure_capture_guard(ui):
    if sys.platform == "win32":
        hwnd = int(ui.mainWindow.winId())
        set_affinity = ctypes.windll.user32.SetWindowDisplayAffinity
        ui.disable_screenshot = lambda: ... if set_affinity(
            hwnd, 0x00000011) else 1 / 0
        ui.enable_screenshot = lambda: ... if set_affinity(
            hwnd, 0x00000000) else 1 / 0
    elif sys.platform == "darwin":
        try:
            hwnd = int(ui.mainWindow.winId())
            ui.disable_screenshot, ui.enable_screenshot = macos_capture_guard(
                hwnd)
        except Exception as e:
            logger.warning(f"capture guard 初始化失败，防截屏禁用: {e}")
            ui.disable_screenshot = lambda: None
            ui.enable_screenshot = lambda: None
    else:
        ui.disable_screenshot = lambda: None
        ui.enable_screenshot = lambda: None
