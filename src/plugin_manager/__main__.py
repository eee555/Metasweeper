"""
插件管理器命令行入口

用法：
  开发模式:  python -m plugin_manager [--endpoint tcp://127.0.0.1:5555] [--mode window|tray] [--no-gui]
  打包后:    plugin_manager.exe [--endpoint tcp://127.0.0.1:5555] [--mode window|tray] [--no-gui]

启动模式:
  window  - 启动后显示主窗口 (默认)
  tray    - 启动后在系统托盘运行，不弹出主窗口
  --no-gui - 完全无界面（后台模式）
"""

import argparse
import os
import sys

from . import _pip_worker
from .plugin_lib_env import prepare_plugin_dependency_environment

# 高分屏支持：必须在导入 PyQt 之前设置
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

# ── 互斥体：防止重复实例 ──

_MUTEX_NAME = "Metasweeper-PluginManager"
_mutex_handle = None
_fallback_mutex_handle = None
_posix_lock_file = None


def _acquire_fallback_mutex() -> bool:
    """Use Win32 directly when pywin32 is missing or fails."""
    global _fallback_mutex_handle
    if _fallback_mutex_handle is not None:
        return True
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    ctypes.set_last_error(0)
    handle = kernel.CreateMutexW(None, False, _MUTEX_NAME)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(handle)
        return False
    _fallback_mutex_handle = handle
    return True


def _acquire_posix_lock() -> bool:
    global _posix_lock_file
    import fcntl
    import tempfile
    if _posix_lock_file is not None:
        return True
    path = os.path.join(tempfile.gettempdir(), f"metasweeper-plugin-manager-{os.getuid()}.lock")
    lock_file = open(path, "a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return False
    except Exception:
        lock_file.close()
        raise
    _posix_lock_file = lock_file
    return True


def _acquire_mutex() -> bool:
    """Acquire a process-lifetime singleton lock."""
    global _mutex_handle
    if sys.platform != "win32":
        return _acquire_posix_lock()
    try:
        import win32api
        import win32event
        import winerror
        _mutex_handle = win32event.CreateMutex(None, False, _MUTEX_NAME)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            win32api.CloseHandle(_mutex_handle)
            _mutex_handle = None
            return False
        return True
    except Exception:
        return _acquire_fallback_mutex()


def main() -> int:
    if sys.argv[1:2] == [_pip_worker.FLAG]:
        return _pip_worker.main(sys.argv[2:])

    from . import restart

    is_restart = bool(os.environ.get(restart._RESTART_PORT))
    try:
        is_restart = restart.wait_for_predecessor()
        acquired = (restart.acquire_after_restart(_acquire_mutex)
                    if is_restart else _acquire_mutex())
        if not acquired:
            if is_restart:
                raise RuntimeError("The previous plugin manager did not release its lock")
            print("[plugin_manager] 已有实例在运行，退出")
            return 0
        return _run_manager()
    except restart.RestartCancelled:
        return 1
    except Exception as exc:
        if not is_restart:
            raise
        restart.report_restart_failure(exc)
        return 1


def _run_manager() -> int:
    parser = argparse.ArgumentParser(description="Solvable-Minesweeper 插件管理器")
    parser.add_argument(
        "--endpoint",
        default=os.environ.get(
            "METASWEEPER_ZMQ_ENDPOINT", "tcp://127.0.0.1:5555"),
        help="ZMQ Server 基准地址 (默认: tcp://127.0.0.1:5555)",
    )
    parser.add_argument(
        "--pub-endpoint",
        default=os.environ.get("METASWEEPER_ZMQ_PUB_ENDPOINT"),
        help="主进程实际绑定的 PUB 端点（全随机端口模式由命令行传入）",
    )
    parser.add_argument(
        "--ctrl-endpoint",
        default=os.environ.get("METASWEEPER_ZMQ_CTRL_ENDPOINT"),
        help="主进程实际绑定的 CTRL 端点（全随机端口模式由命令行传入）",
    )
    parser.add_argument(
        "--mode",
        choices=["window", "tray"],
        default="window",
        help="GUI 模式: window=显示主窗口, tray=系统托盘 (默认: window)",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        default=False,
        help="不显示界面（后台模式）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用 debugpy 远程调试，等待 VS Code 附加",
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=5678,
        help="debugpy 监听端口 (默认: 5678)",
    )
    parser.add_argument(
        "--data-dir",
        help="可写数据目录（由主进程传入，已通过权限测试）",
    )

    parser.add_argument("--host-pid", type=int, help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.data_dir:
        from .app_paths import set_data_dir_override
        set_data_dir_override(args.data_dir)

    # 初始化 loguru 日志系统（主日志 + 控制台）
    from .app_paths import get_data_dir, get_log_dir
    from .logging_setup import init_logging
    from .restart import configure_invocation

    configure_invocation(str(get_data_dir().resolve()))
    init_logging(get_log_dir(), console=True, level="DEBUG")

    # 启动时只准备/识别环境，不自动安装包；必须在插件导入和调试功能之前接入 sys.path。
    from loguru import logger
    from .plugin_uninstall import apply_queued_removal

    uninstall_error = apply_queued_removal(get_data_dir())
    if uninstall_error:
        logger.error(uninstall_error)
    setup_result = prepare_plugin_dependency_environment(get_data_dir())
    for error in setup_result.errors:
        logger.warning(f"插件依赖环境准备失败: {error}")

    if args.debug:
        try:
            import debugpy
            debugpy.listen(("127.0.0.1", args.debug_port), in_process_debug_adapter=True)
            print(f"[debug] Waiting for debugger attach on port {args.debug_port}...")
            debugpy.wait_for_client()
            print("[debug] Debugger attached, continuing...")
        except ImportError as e:
            print(f"[WARN] --debug set but debugpy import failed: {e}")

    from . import run_plugin_manager_process

    show_main_window = not args.no_gui and args.mode == "window"

    return run_plugin_manager_process(
        endpoint=args.endpoint,
        with_gui=not args.no_gui,
        show_main_window=show_main_window,
        pub_endpoint=args.pub_endpoint,
        ctrl_endpoint=args.ctrl_endpoint,
        **({"host_pid": args.host_pid} if args.host_pid else {}),
    )


if __name__ == "__main__":
    sys.exit(main())
