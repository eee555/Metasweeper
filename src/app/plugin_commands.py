"""主进程插件控制命令。"""

from config.constants import BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT
from shared_types.commands import (
    NewGameCommand, NewPresetGameCommand, MouseClickCommand,
    InitOpenCommand, SetSkinCommand, SetSoundCommand,
)
from shared_types.enums import GameLevel
from utils.app_logger import logger
from app.skin_applier import handle_set_skin
from app.sound_applier import handle_set_sound


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
        # 权限由插件侧 ControlAuthorizationManager 独占授权保证。
        return handle_set_skin(ui, cmd)

    def handle_set_sound_cmd(cmd: SetSoundCommand):
        # 音效与皮肤同为外观操作，不受 allowed_controls 约束；
        # 使用独立的 SetSoundCommand 授权，与 SetSkinCommand 互不影响。
        return handle_set_sound(ui, cmd)

    bridge.register_handler(NewGameCommand, handle_new_game)
    bridge.register_handler(NewPresetGameCommand, handle_new_preset_game)
    bridge.register_handler(MouseClickCommand, handle_mouse_click)
    bridge.register_handler(InitOpenCommand, handle_init_open)
    bridge.register_handler(SetSkinCommand, handle_set_skin_cmd)
    bridge.register_handler(SetSoundCommand, handle_set_sound_cmd)
