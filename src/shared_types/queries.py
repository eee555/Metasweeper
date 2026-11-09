"""
插件 → 主进程的只读查询协议。

与「命令」（commands.py）和「事件」（events.py）并列的第三类消息：

- 请求与响应都是强类型类，IDE 可以补全字段和跳转定义。
- 不进入插件控制授权（ControlAuthorizationManager）：查询不是控制指令。
- 含棋盘格子的 board_state 受 allowed_controls 的 board_update 开关把关，
  以保持公平性语义；读取的是与 BoardUpdateEvent 相同的可见局面，不包含
  隐藏地雷。game_status / game_context 只返回界面可见信息与统计元数据，
  不受该开关限制。
- 仅在控制通道传输，通过 msgspec 的 type 标记与命令区分。
"""
from __future__ import annotations

import msgspec

from lib_zmq_plugins.shared.base import BaseQuery, BaseQueryResult


# ═══════════════════════════════════════════════════════════════════
# 棋盘
# ═══════════════════════════════════════════════════════════════════

class GetBoardStateQuery(BaseQuery, tag="query.board_state"):
    """请求当前可见棋盘快照（只读）"""


class BoardStateResult(BaseQueryResult, tag="query.board_state.result"):
    """
    棋盘快照。

    Attributes:
        cells: 二维列表，编码与 BoardUpdateEvent 相同
            - -1: 未揭开
            - 0-8: 已揭开的数字
            - "F": 已插旗
            - "X": 错误插旗（游戏结束时显示）
            - "M" / "m": 已显示的雷
        rows, cols: 行列数（以实际棋盘为准）
        mines_remaining: 剩余未标出的雷数
        game_time: 当前计时（秒）
        game_status: 状态名称，例如 ready / playing / win / fail / joking
        game_status_code: 状态名称映射后的数值（GAME_EVENT_STATE_MAP）
    """
    cells: list[list[int | str]] = []
    rows: int = 0
    cols: int = 0
    mines_remaining: int = 0
    game_time: float = 0.0
    game_status: str = ""
    game_status_code: int = 0


# ═══════════════════════════════════════════════════════════════════
# 游戏状态
# ═══════════════════════════════════════════════════════════════════

class GetGameStatusQuery(BaseQuery, tag="query.game_status"):
    """请求当前游戏状态（只读）"""


class GameStatusResult(BaseQueryResult, tag="query.game_status.result"):
    """
    游戏状态。

    Attributes:
        game_status: 状态名称
        game_status_code: 映射后的状态数值
        game_time: 当前计时（秒）
        rtime: 已记录的用时（秒）
        mines_remaining: 剩余未标出的雷数
        rows, cols, mines: 局面尺寸与总雷数
        level, level_name: 难度值及显示名
        mode, mode_name: 模式值及显示名
    """
    game_status: str = ""
    game_status_code: int = 0
    game_time: float = 0.0
    rtime: float = 0.0
    mines_remaining: int = 0
    rows: int = 0
    cols: int = 0
    mines: int = 0
    level: int = 0
    level_name: str = ""
    mode: int = 0
    mode_name: str = ""


# ═══════════════════════════════════════════════════════════════════
# 游戏上下文
# ═══════════════════════════════════════════════════════════════════

class GetGameContextQuery(BaseQuery, tag="query.game_context"):
    """请求当前游戏上下文（只读）"""


class ControlPermissions(msgspec.Struct):
    """当前开放的作弊开关，供外部 agent 判断能做什么"""
    allowed_controls: list[str] = []
    board_update: bool = False
    mouse_click: bool = False


class GameContextResult(BaseQueryResult, tag="query.game_context.result"):
    """
    游戏上下文。

    Attributes:
        bbbv, bbbv_solved: 3BV 总量与已完成量
        progress: 完成度（0..1），无法计算时为 None
        is_official, is_fair: 当前对局是否仍为官方 / 公平成绩
        software: 生成当前成绩的软件标识
        permissions: 当前 allowed_controls 及常用作弊开关状态
    """
    game_status: str = ""
    game_status_code: int = 0
    game_time: float = 0.0
    rtime: float = 0.0
    mines_remaining: int = 0
    rows: int = 0
    cols: int = 0
    mines: int = 0
    level: int = 0
    level_name: str = ""
    mode: int = 0
    mode_name: str = ""
    bbbv: int = 0
    bbbv_solved: int = 0
    progress: float | None = None
    is_official: bool | None = None
    is_fair: bool | None = None
    software: str = ""
    permissions: ControlPermissions = msgspec.field(
        default_factory=ControlPermissions)


QUERY_TYPES = [GetBoardStateQuery, GetGameStatusQuery, GetGameContextQuery]
QUERY_RESULT_TYPES = [BoardStateResult, GameStatusResult, GameContextResult]
