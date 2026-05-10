"""
插件管理器独立入口（供 PyInstaller 打包使用）

替代 __main__.py，避免相对导入问题。
python -m plugin_manager 仍走 __main__.py（开发模式）
打包后使用此脚本作为入口。
"""

import argparse
import os
import sys

# 高分屏支持：必须在导入 PyQt 之前设置
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")


def main() -> int:
    parser = argparse.ArgumentParser(description="Solvable-Minesweeper 插件管理器")
    parser.add_argument(
        "--endpoint",
        default="tcp://127.0.0.1:5555",
        help="ZMQ Server 地址 (默认: tcp://127.0.0.1:5555)",
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
        default=False,
        help="启用 debugpy 远程调试，等待 VS Code 附加 (端口 5678)",
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=5678,
        help="debugpy 监听端口 (默认: 5678)",
    )

    args = parser.parse_args()

    # 可选：启动 debugpy 等待远程调试附加
    if args.debug:
        try:
            import debugpy
            # in_process_debug_adapter=True: 不启动子进程，直接在当前进程中运行 adapter
            # 解决 PyInstaller 打包后子进程找不到 Python/debugpy 的问题
            debugpy.listen(("0.0.0.0", args.debug_port), in_process_debug_adapter=True)
            print(f"[debug] Waiting for debugger attach on port {args.debug_port}...")
            debugpy.wait_for_client()
            print("[debug] Debugger attached, continuing...")
        except ImportError as e:
            print(f"[WARN] --debug set but debugpy import failed: {e}")

    from plugin_manager.app_paths import get_log_dir
    from plugin_manager.logging_setup import init_logging

    init_logging(get_log_dir(), console=True, level="DEBUG")

    from plugin_manager import run_plugin_manager_process

    show_main_window = not args.no_gui and args.mode == "window"

    return run_plugin_manager_process(
        endpoint=args.endpoint,
        with_gui=not args.no_gui,
        show_main_window=show_main_window,
    )


if __name__ == "__main__":
    sys.exit(main())
