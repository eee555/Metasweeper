from policy_guard import enforce_policy_integrity

if __name__ == "__main__":
    enforce_policy_integrity()

import time
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalSocket, QLocalServer
import sys
import os
import argparse
import json
import mainWindowGUI as mainWindowGUI
import mineSweeperGUI as mineSweeperGUI
import ms_toollib as ms
import ctypes
from pathlib import Path
from utils.app_logger import logger
from utils.path_utils import get_executable_dir, get_runtime_mode
from utils.capture_guard import macos_capture_guard

# 插件系统（新）
from plugin_sdk import GameServerBridge
from plugin_manager.app_paths import get_env_for_subprocess
from shared_types.commands import (
    NewGameCommand, NewPresetGameCommand, MouseClickCommand, InitOpenCommand,
)
from shared_types.queries import (
    GetBoardStateQuery, GetGameStatusQuery, GetGameContextQuery,
    BoardStateResult, GameStatusResult, GameContextResult, ControlPermissions,
)
from shared_types.enums import GameLevel, GameMode
import subprocess
from config.constants import (
    BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT, GAME_EVENT_STATE_MAP,
)

os.environ["QT_FONT_DPI"] = "96"

# 打包模式下，把工作目录切到资源目录，保证相对路径（media/ 等）可用
if getattr(sys, "frozen", False):
    os.chdir(str(Path(__file__).resolve().parent))


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
                        logger.warning(
                            "Failed to parse evf file", exc_info=True)
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
                        logger.warning(
                            "Failed to parse evfs file", exc_info=True)
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

    if sys.platform == "win32" or not getattr(sys, "frozen", False):
        output_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "out.json")
    else:
        # macOS 打包模式下程序目录在 .app 包内（只读封印），写到当前目录
        output_file = os.path.join(os.getcwd(), "out.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return 0


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
        GameServerBridge.instance().start()
        mainWindow = mainWindowGUI.MainWindow()
        ui = mineSweeperGUI.MineSweeperGUI(mainWindow, sys.argv)
        ui.mainWindow.show()

        # ── 启动 ZMQ Server + 插件管理器 ──

        _translate = QtCore.QCoreApplication.translate
        data_dir = str(ui.setting_path / "data")

        # 检查插件管理器是否已在运行（上一次崩溃后残存的互斥体）
        _plugin_manager_running = False
        if sys.platform == "win32":
            try:
                import win32api
                import win32event
                import winerror
                hMutex = win32event.OpenMutex(
                    0x001F0001, False, "Metasweeper-PluginManager")
                if hMutex:
                    win32api.CloseHandle(hMutex)
                    _plugin_manager_running = True
            except win32api.error:
                pass  # 互斥体不存在，正常启动

        plugin_process = None

        if not _plugin_manager_running:
            # 打包后直接调用 plugin_manager.exe，开发模式用 python -m
            if get_runtime_mode() != "source":
                base_dir = str(get_executable_dir())
                if sys.platform == "darwin":
                    # macOS：插件管理器以内嵌 .app 形式随主程序分发
                    plugin_exe = os.path.join(
                        base_dir, "..", "Resources", "plugin_manager.app",
                        "Contents", "MacOS", "plugin_manager")
                else:
                    plugin_exe = os.path.join(base_dir, "plugin_manager.exe")
                if not os.path.exists(plugin_exe):
                    QtWidgets.QMessageBox.warning(
                        mainWindow, _translate("MainWindow", "插件管理器"),
                        _translate("MainWindow", "找不到 plugin_manager.exe：\n{path}\n\n插件将被禁用。").replace(
                            "{path}", plugin_exe),
                    )
                    plugin_process = None
                else:
                    cmd = [plugin_exe, "--mode",
                           "tray", "--data-dir", data_dir]
                    cwd = base_dir
                    try:
                        plugin_process = subprocess.Popen(
                            cmd, cwd=cwd, env=get_env_for_subprocess(),
                        )
                    except Exception as e:
                        QtWidgets.QMessageBox.warning(
                            mainWindow, _translate("MainWindow", "插件管理器"),
                            _translate("MainWindow", "启动 plugin_manager 失败：\n{err}").replace(
                                "{err}", str(e)),
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

        # 等插件连接后同步初始语言
        from PySide6.QtCore import QTimer
        from shared_types.events import LanguageChangeEvent
        QTimer.singleShot(2000, lambda: GameServerBridge.instance().send_event(
            LanguageChangeEvent(language=ui.language)))

        # 注册控制命令处理器（自动在主线程执行）
        def handle_new_game(cmd: NewGameCommand):
            """处理随机新游戏命令"""
            from lib_zmq_plugins.shared.base import CommandResponse

            if 'new_random_game' not in ui._allowed_controls:
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
                f"[NewGameCommand] level={cmd.level}, rows={rows}, cols={cols}, mines={mines}, mode={cmd.mode}")
            ui.gameMode = cmd.mode
            ui.setBoard_and_start(rows, cols, mines)
            return CommandResponse(request_id=cmd.request_id, success=True)

        def handle_new_preset_game(cmd: NewPresetGameCommand):
            """处理新预设游戏命令"""
            from lib_zmq_plugins.shared.base import CommandResponse

            logger.info(
                f"[NewPresetGameCommand] board={cmd.board}, mode={cmd.mode}")

            ui.engine.pending_boards.append({
                "board": cmd.board,
                "game_mode": cmd.mode,
            })
            ui.gameMode = cmd.mode
            ui.setBoard_and_start(len(cmd.board), len(
                cmd.board[0]), sum(row.count(-1) for row in cmd.board))
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

        def handle_init_open(cmd: InitOpenCommand):
            """处理初始化翻开命令"""
            from lib_zmq_plugins.shared.base import CommandResponse

            if not ui.engine.pending_boards or ui.game_state != 'ready':
                return CommandResponse(request_id=cmd.request_id, success=False)
            logger.info(
                f"[InitOpenCommand] row={cmd.row}, col={cmd.col}")
            success = ui.execute_cell_click(cmd.row, cmd.col, 0)
            return CommandResponse(request_id=cmd.request_id, success=success)

        # ── 只读状态查询（共用可见局面，不读取隐藏雷） ──
        def _as_int(value, default=0):
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float) and value == value and abs(value) != float("inf"):
                return int(value)
            return default

        def _as_float(value, default=0.0):
            if isinstance(value, bool):
                return float(value)
            if isinstance(value, (int, float)):
                number = float(value)
                if number == number and abs(number) != float("inf"):
                    return number
            return default

        def _enum_name(enum_type, value):
            try:
                return enum_type(int(value)).display_name
            except (TypeError, ValueError):
                return ""

        def _is_parsed_video(ms_board):
            """
            只有已解析的录像对象才能安全读取 rtime / bbbv_solved 等统计字段。

            注意：在实时对局的 ms.BaseVideo（尚未生成/解析）上读取 rtime 或
            bbbv_solved 会在 ms_toollib 的 Rust 层直接崩溃（0xC0000409），
            不能捕获，只能避免访问。
            """
            return isinstance(ms_board, (ms.EvfVideo, ms.AvfVideo,
                                         ms.MvfVideo, ms.RmvVideo))

        def _game_status_fields():
            ms_board = getattr(getattr(ui, "label", None), "ms_board", None)
            state = str(getattr(ui, "_game_state", "") or "")
            level = _as_int(getattr(ms_board, "level", 0))
            mode = _as_int(getattr(ui, "gameMode", 0))
            parsed = _is_parsed_video(ms_board)
            return {
                "game_status": state,
                "game_status_code": _as_int(GAME_EVENT_STATE_MAP.get(state, 0)),
                "game_time": _as_float(getattr(ms_board, "time", 0.0)),
                # 实时对局读取 rtime 会导致原生崩溃，仅在录像对象上读取
                "rtime": _as_float(getattr(ms_board, "rtime", 0.0)) if parsed else 0.0,
                "mines_remaining": _as_int(ui.mineUnFlagedNum),
                "rows": _as_int(ui.row),
                "cols": _as_int(ui.column),
                "mines": _as_int(ui.minenum),
                "level": level,
                "level_name": _enum_name(GameLevel, level),
                "mode": mode,
                "mode_name": _enum_name(GameMode, mode),
            }

        def _board_state_payload():
            ms_board = getattr(getattr(ui, "label", None), "ms_board", None)
            if ms_board is None or not hasattr(ms_board, "game_board"):
                raise ValueError("board object unavailable")
            payload = _game_status_fields()
            game_board = [list(row) for row in ms_board.game_board]
            rows = len(game_board)
            cols = len(game_board[0]) if rows else 0
            if rows <= 0 or cols <= 0 or any(len(row) != cols for row in game_board):
                raise ValueError("inconsistent board dimensions")
            # 以实际棋盘为准，避免录像/展示态下 ui.row/ui.column 与棋盘不一致
            payload["rows"] = rows
            payload["cols"] = cols
            payload["cells"] = game_board
            return payload

        def _game_context_payload():
            ms_board = getattr(getattr(ui, "label", None), "ms_board", None)
            payload = _game_status_fields()
            parsed = _is_parsed_video(ms_board)
            bbbv = _as_int(getattr(ms_board, "bbbv", 0))
            # 实时对局读取 bbbv_solved 会导致原生崩溃，仅在录像对象上读取
            solved = _as_int(
                getattr(ms_board, "bbbv_solved", 0)) if parsed else 0
            payload.update({
                "bbbv": bbbv,
                "bbbv_solved": solved,
                "progress": (solved / bbbv) if (parsed and bbbv > 0) else None,
                "is_official": getattr(ms_board, "is_official", None),
                "is_fair": getattr(ms_board, "is_fair", None),
                "software": str(getattr(ms_board, "software", "") or ""),
                "permissions": {
                    "allowed_controls": sorted(ui._allowed_controls),
                    "board_update": "board_update" in ui._allowed_controls,
                    "mouse_click": "mouse_click" in ui._allowed_controls,
                    "new_random_game": "new_random_game" in ui._allowed_controls,
                },
            })
            return payload

        def _deny_board_read(query, result_type):
            """统一处理棋盘读取权限关闭的情况"""
            return result_type(
                request_id=query.request_id, success=False,
                error="board_update permission disabled; enable it in advanced settings")

        def handle_board_state_query(query: GetBoardStateQuery) -> BoardStateResult:
            """查询：当前可见棋盘快照"""
            if 'board_update' not in ui._allowed_controls:
                return _deny_board_read(query, BoardStateResult)
            try:
                payload = _board_state_payload()
                return BoardStateResult(
                    request_id=query.request_id,
                    cells=payload["cells"],
                    rows=payload["rows"],
                    cols=payload["cols"],
                    mines_remaining=payload["mines_remaining"],
                    game_time=payload["game_time"],
                    game_status=payload["game_status"],
                    game_status_code=payload["game_status_code"],
                )
            except Exception as e:
                logger.opt(exception=True).warning(
                    f"[GetBoardStateQuery] unavailable: {e}")
                return BoardStateResult(
                    request_id=query.request_id, success=False,
                    error=f"board state unavailable: {e}")

        def handle_game_status_query(query: GetGameStatusQuery) -> GameStatusResult:
            """查询：当前游戏状态"""
            if 'board_update' not in ui._allowed_controls:
                return _deny_board_read(query, GameStatusResult)
            try:
                return GameStatusResult(
                    request_id=query.request_id, **_game_status_fields())
            except Exception as e:
                logger.opt(exception=True).warning(
                    f"[GetGameStatusQuery] unavailable: {e}")
                return GameStatusResult(
                    request_id=query.request_id, success=False,
                    error=f"game status unavailable: {e}")

        def handle_game_context_query(query: GetGameContextQuery) -> GameContextResult:
            """查询：当前游戏上下文（状态、参数、统计、权限）

            不包含任何棋盘格子内容，因此不受 board_update 权限限制；
            仍然只返回可见数据，不读取隐藏雷。
            """
            try:
                payload = _game_context_payload()
                permissions = payload.pop("permissions")
                return GameContextResult(
                    request_id=query.request_id,
                    permissions=ControlPermissions(**permissions),
                    **payload)
            except Exception as e:
                logger.opt(exception=True).warning(
                    f"[GetGameContextQuery] unavailable: {e}")
                return GameContextResult(
                    request_id=query.request_id, success=False,
                    error=f"game context unavailable: {e}")

        GameServerBridge.instance().register_handler(NewGameCommand, handle_new_game)
        GameServerBridge.instance().register_handler(
            NewPresetGameCommand, handle_new_preset_game)
        GameServerBridge.instance().register_handler(
            MouseClickCommand, handle_mouse_click)
        GameServerBridge.instance().register_handler(
            InitOpenCommand, handle_init_open)
        GameServerBridge.instance().register_query_handler(
            GetBoardStateQuery, handle_board_state_query)
        GameServerBridge.instance().register_query_handler(
            GetGameStatusQuery, handle_game_status_query)
        GameServerBridge.instance().register_query_handler(
            GetGameContextQuery, handle_game_context_query)

        # _translate = QtCore.QCoreApplication.translate
        if sys.platform == "win32":
            hwnd = int(ui.mainWindow.winId())

            SetWindowDisplayAffinity = ctypes.windll.user32.SetWindowDisplayAffinity
            ui.disable_screenshot = lambda: ... if SetWindowDisplayAffinity(
                hwnd, 0x00000011) else 1/0
            ui.enable_screenshot = lambda: (
                ... if SetWindowDisplayAffinity(hwnd, 0x00000000) else 1 / 0
            )
        elif sys.platform == "darwin":
            # 防截屏属锦上添花，任何失败都降级为空实现，不影响启动
            try:
                hwnd = int(ui.mainWindow.winId())
                ui.disable_screenshot, ui.enable_screenshot = \
                    macos_capture_guard(hwnd)
            except Exception as e:
                logger.warning(f"capture guard 初始化失败，防截屏禁用: {e}")
                ui.disable_screenshot = lambda: None
                ui.enable_screenshot = lambda: None
        else:
            # 其他平台没有等价的防截屏 API，保持空实现
            ui.disable_screenshot = lambda: None
            ui.enable_screenshot = lambda: None

        def _cleanup():
            GameServerBridge.instance().stop()
            if plugin_process is not None and plugin_process.poll() is None:
                plugin_process.terminate()
                try:
                    plugin_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # macOS 下插件管理器的 SIGTERM 优雅关闭依赖其 Qt 事件循环，
                    # 可能永远不执行；超时后强制结束，避免退出阶段报错
                    logger.warning("plugin_manager 未在 5 秒内退出，强制结束")
                    plugin_process.kill()
                    try:
                        plugin_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.error("plugin_manager 强制结束失败")

        app.aboutToQuit.connect(_cleanup)
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
