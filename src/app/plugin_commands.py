"""主进程插件控制命令。"""

import json
from pathlib import Path

from config.constants import BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT
from shared_types.commands import (
    NewGameCommand, NewPresetGameCommand, MouseClickCommand,
    InitOpenCommand, SetSkinCommand, SetSoundCommand,
)
from shared_types.enums import GameLevel
from utils.app_logger import logger
from app.skin_applier import handle_set_skin
from app.sound_applier import handle_set_sound


def _is_appearance_authorized(tag: str) -> bool:
    """主进程侧复查外观命令授权。

    此前授权只在插件进程 BasePlugin._check_control_auth() 里检查，任何直连
    ZMQ 端口、绕过 SDK 构造 msgspec 包的进程都能发换肤/音效命令。这里读
    插件管理器持久化的授权文件做二次确认。

    `data/control_authorization.json` 由 ControlAuthorizationManager 维护；
    文件不存在或不可读时保持宽松（放行），避免授权系统尚未初始化时把合法
    插件挡在门外；文件存在但对应 tag 未授权则明确拒绝。
    """
    try:
        from plugin_manager.app_paths import get_data_dir
        auth_file = Path(get_data_dir()) / "control_authorization.json"
    except Exception:
        return True
    if not auth_file.is_file():
        return True                     # 降级：授权系统尚未初始化
    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        logger.warning("[Auth] 控制授权文件不可读，外观命令按放行处理")
        return True
    if not isinstance(data, dict):
        return True
    return tag in data


def register_plugin_commands(bridge, ui):
    def handle_new_game(cmd: NewGameCommand):
        from lib_zmq_plugins.shared.base import CommandResponse as Response

        if 'new_random_game' not in ui._allowed_controls:
            return Response(request_id=cmd.request_id, success=False)
        if cmd.level == GameLevel.BEGINNER.value:
            rows, cols, mines = BOARD_BEGINNER
        elif cmd.level == GameLevel.INTERMEDIATE.value:
            rows, cols, mines = BOARD_INTERMEDIATE
        elif cmd.level == GameLevel.EXPERT.value:
            rows, cols, mines = BOARD_EXPERT
        else:
            rows, cols, mines = cmd.rows, cmd.cols, cmd.mines
        logger.info(
            f"[NewGameCommand] level={cmd.level}, rows={rows}, cols={cols}, mines={mines}, mode={cmd.mode}")
        ui.gameMode = cmd.mode
        ui.setBoard_and_start(rows, cols, mines)
        return Response(request_id=cmd.request_id, success=True)

    def handle_new_preset_game(cmd: NewPresetGameCommand):
        from lib_zmq_plugins.shared.base import CommandResponse

        logger.info(
            f"[NewPresetGameCommand] board={cmd.board}, mode={cmd.mode}")
        ui.engine.pending_boards.append(
            {"board": cmd.board, "game_mode": cmd.mode})
        ui.gameMode = cmd.mode
        ui.setBoard_and_start(len(cmd.board), len(
            cmd.board[0]), sum(row.count(-1) for row in cmd.board))
        return CommandResponse(request_id=cmd.request_id, success=True)

    def handle_mouse_click(cmd: MouseClickCommand):
        from lib_zmq_plugins.shared.base import CommandResponse

        if 'mouse_click' not in ui._allowed_controls:
            return CommandResponse(request_id=cmd.request_id, success=False)
        logger.info(
            f"[MouseClickCommand] row={cmd.row}, col={cmd.col}, button={cmd.button}")
        success = ui.execute_cell_click(cmd.row, cmd.col, cmd.button)
        return CommandResponse(request_id=cmd.request_id, success=success)

    def handle_init_open(cmd: InitOpenCommand):
        from lib_zmq_plugins.shared.base import CommandResponse

        if not ui.engine.pending_boards or ui.game_state != 'ready':
            return CommandResponse(request_id=cmd.request_id, success=False)
        logger.info(f"[InitOpenCommand] row={cmd.row}, col={cmd.col}")
        success = ui.execute_cell_click(cmd.row, cmd.col, 0)
        return CommandResponse(request_id=cmd.request_id, success=success)

    def handle_set_skin_cmd(cmd: SetSkinCommand):
        # 换肤是外观操作，不受 allowed_controls（作弊开关）约束；
        # 除插件侧授权外，主进程再复查一次持久化授权。
        from lib_zmq_plugins.shared.base import CommandResponse
        if not _is_appearance_authorized("set_skin"):
            return CommandResponse(request_id=cmd.request_id, success=False,
                                   error="未授权 SetSkinCommand")
        return handle_set_skin(ui, cmd)

    def handle_set_sound_cmd(cmd: SetSoundCommand):
        # 音效与皮肤同为外观操作，不受 allowed_controls 约束；
        # 使用独立的 SetSoundCommand 授权，与 SetSkinCommand 互不影响。
        from lib_zmq_plugins.shared.base import CommandResponse
        if not _is_appearance_authorized("set_sound"):
            return CommandResponse(request_id=cmd.request_id, success=False,
                                   error="未授权 SetSoundCommand")
        return handle_set_sound(ui, cmd)

    bridge.register_handler(NewGameCommand, handle_new_game)
    bridge.register_handler(NewPresetGameCommand, handle_new_preset_game)
    bridge.register_handler(MouseClickCommand, handle_mouse_click)
    bridge.register_handler(InitOpenCommand, handle_init_open)
    bridge.register_handler(SetSkinCommand, handle_set_skin_cmd)
    bridge.register_handler(SetSoundCommand, handle_set_sound_cmd)
