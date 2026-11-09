"""插件管理器进程生命周期。"""

import os
import subprocess
import sys

from PySide6 import QtCore, QtWidgets
from plugin_manager.app_paths import get_env_for_subprocess
from plugin_sdk import GameServerBridge
from utils.app_logger import logger
from utils.path_utils import get_executable_dir, get_runtime_mode


def start_plugin_process(ui, main_window, plugins_disabled):
    translate = QtCore.QCoreApplication.translate
    data_dir = str(ui.setting_path / "data")
    running = False
    if sys.platform == "win32":
        import win32api
        import win32event
        import winerror
        try:
            mutex = win32event.OpenMutex(
                0x001F0001, False, "Metasweeper-PluginManager")
            if mutex:
                win32api.CloseHandle(mutex)
                running = True
        except win32api.error:
            pass

    if running or plugins_disabled:
        return None
    if get_runtime_mode() != "source":
        base_dir = str(get_executable_dir())
        if sys.platform == "darwin":
            plugin_exe = os.path.join(base_dir, "..", "Resources", "plugin_manager.app",
                                      "Contents", "MacOS", "plugin_manager")
        else:
            plugin_exe = os.path.join(base_dir, "plugin_manager.exe")
        if not os.path.exists(plugin_exe):
            QtWidgets.QMessageBox.warning(
                main_window, translate("MainWindow", "插件管理器"),
                translate("MainWindow", "找不到 plugin_manager.exe：\n{path}\n\n插件将被禁用。").replace(
                    "{path}", plugin_exe),
            )
            return None
        cmd = [plugin_exe, "--mode", "tray", "--data-dir", data_dir]
        cwd = base_dir
        try:
            return subprocess.Popen(cmd, cwd=cwd, env=get_env_for_subprocess())
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                main_window, translate("MainWindow", "插件管理器"),
                translate("MainWindow", "启动 plugin_manager 失败：\n{err}").replace(
                    "{err}", str(e)),
            )
            return None
    cmd = [sys.executable, "-m", "plugin_manager",
           "--mode", "tray", "--data-dir", data_dir]
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        return subprocess.Popen(cmd, cwd=cwd, env=get_env_for_subprocess())
    except Exception as e:
        logger.warning(f"Failed to start plugin_manager: {e}")
        return None


def cleanup_plugin_process(plugin_process):
    GameServerBridge.instance().stop()
    if plugin_process is not None and plugin_process.poll() is None:
        plugin_process.terminate()
        try:
            plugin_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("plugin_manager 未在 5 秒内退出，强制结束")
            plugin_process.kill()
            try:
                plugin_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.error("plugin_manager 强制结束失败")
