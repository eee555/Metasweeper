"""主进程插件只读查询。"""

import ms_toollib as ms

from config.constants import GAME_EVENT_STATE_MAP
from shared_types.enums import GameLevel, GameMode
from shared_types.queries import (
    GetBoardStateQuery, GetGameStatusQuery, GetGameContextQuery,
    BoardStateResult, GameStatusResult, GameContextResult, ControlPermissions,
)
from utils.app_logger import logger


def register_plugin_queries(bridge, ui):
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
        # 实时 BaseVideo 读取 rtime / bbbv_solved 会导致原生崩溃。
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
        # 录像/展示态下以实际棋盘尺寸为准。
        payload["rows"] = rows
        payload["cols"] = cols
        payload["cells"] = game_board
        return payload

    def _game_context_payload():
        ms_board = getattr(getattr(ui, "label", None), "ms_board", None)
        payload = _game_status_fields()
        parsed = _is_parsed_video(ms_board)
        bbbv = _as_int(getattr(ms_board, "bbbv", 0))
        solved = _as_int(getattr(ms_board, "bbbv_solved", 0)) if parsed else 0
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
            },
        })
        return payload

    def _deny_board_read(query, result_type):
        return result_type(
            request_id=query.request_id, success=False,
            error="board_update permission disabled; enable it in advanced settings")

    def handle_board_state_query(query: GetBoardStateQuery) -> BoardStateResult:
        if 'board_update' not in ui._allowed_controls:
            return _deny_board_read(query, BoardStateResult)
        try:
            payload = _board_state_payload()
            return BoardStateResult(
                request_id=query.request_id,
                cells=payload["cells"], rows=payload["rows"], cols=payload["cols"],
                mines_remaining=payload["mines_remaining"],
                game_time=payload["game_time"], game_status=payload["game_status"],
                game_status_code=payload["game_status_code"],
            )
        except Exception as e:
            logger.opt(exception=True).warning(
                f"[GetBoardStateQuery] unavailable: {e}")
            return BoardStateResult(
                request_id=query.request_id, success=False,
                error=f"board state unavailable: {e}")

    def handle_game_status_query(query: GetGameStatusQuery) -> GameStatusResult:
        # 状态、计时、尺寸等均为界面可见信息，不含棋盘格子，不需要
        # board_update 作弊开关；含格子的 board_state 才受该开关约束。
        try:
            return GameStatusResult(request_id=query.request_id, **_game_status_fields())
        except Exception as e:
            logger.opt(exception=True).warning(
                f"[GetGameStatusQuery] unavailable: {e}")
            return GameStatusResult(
                request_id=query.request_id, success=False,
                error=f"game status unavailable: {e}")

    def handle_game_context_query(query: GetGameContextQuery) -> GameContextResult:
        # 上下文不包含棋盘格子，因此不受 board_update 权限限制。
        try:
            payload = _game_context_payload()
            permissions = payload.pop("permissions")
            return GameContextResult(
                request_id=query.request_id,
                permissions=ControlPermissions(**permissions), **payload)
        except Exception as e:
            logger.opt(exception=True).warning(
                f"[GetGameContextQuery] unavailable: {e}")
            return GameContextResult(
                request_id=query.request_id, success=False,
                error=f"game context unavailable: {e}")

    bridge.register_query_handler(GetBoardStateQuery, handle_board_state_query)
    bridge.register_query_handler(GetGameStatusQuery, handle_game_status_query)
    bridge.register_query_handler(
        GetGameContextQuery, handle_game_context_query)
