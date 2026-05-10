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

    args = parser.parse_args()

    # 初始化 loguru 日志系统（主日志 + 控制台）
    from .app_paths import get_log_dir
    from .logging_setup import init_logging

    init_logging(get_log_dir(), console=True, level="DEBUG")

    from . import run_plugin_manager_process

    show_main_window = not args.no_gui and args.mode == "window"

    return run_plugin_manager_process(
        endpoint=args.endpoint,
        with_gui=not args.no_gui,
        show_main_window=show_main_window,
    )


if __name__ == "__main__":
    sys.exit(main())
