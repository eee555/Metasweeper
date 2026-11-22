"""
所有插件可能获得的事件类型定义。
"""
from __future__ import annotations

from typing import List

from lib_zmq_plugins.shared.base import BaseEvent

from .enums import GameBoardState, ButtonEventType, MouseState


class BoardUpdateEvent(BaseEvent, tag="board_update"):
    """
    棋盘更新事件 - 每次棋盘状态变化时发送

    Attributes:
        rows: 行数
        cols: 列数
        game_board: 游戏局面二维数组
            - 0-8: 已揭开的数字格子
            - 10: 未揭开的格子
            - 11: 标旗的格子
            - 14: 错误标旗（游戏结束时显示）
            - 15: 爆炸的地雷
            - 16: 未爆炸的地雷（游戏结束时显示）
        mines_remaining: 剩余未标出的地雷数（总地雷数 - 已标旗数）
        game_time: 游戏时间（秒）
    """
    rows: int = 0
    cols: int = 0
    game_board: List[List[int]] = []
    mines_remaining: int = 0
    game_time: float = 0.0


class GameStatusChangeEvent(BaseEvent, tag="game_status_change"):
    """
    游戏状态变化事件

    Attributes:
        last_status: 上一个游戏状态
        current_status: 当前游戏状态
    """
    last_status: int = 0
    current_status: int = 0


class ContextChangeEvent(BaseEvent, tag="context_change"):
    """上下文变化事件。"""
    pix_size: int = 20
    rows: int = 16
    cols: int = 30
    mine_num: int = 99
    game_mode: int = 0
    # “自动重开比例”，大于等于该比例时，不自动重开。负号表示禁用，负数表示禁用的值。0相当于禁用，但可以编辑。
    auto_replay: int = 30
    end_then_flag: bool = False
    cursor_limit: bool = False
    # 是否自动弹窗
    auto_notification: bool = True
    player_identifier:str = ""
    race_identifier: str = ""
    unique_identifier: str = ""
    # 用户的国家或地区名的全称，例如”中国“。必须是country_name中有的或None
    # 播放录像时，self.country不会遭到修改
    country: str = ""
    autosave_video: bool = True
    autosave_video_set: bool = True
    # 是否永远使用筛选法取得无猜局面
    filter_forever: bool = False
    board_constraint: str = ""
    attempt_times_limit: int = 100000


class ButtonClickEvent(BaseEvent, tag="button_click"):
    """鼠标按键事件"""
    col: int = 0
    row: int = 0
    button: ButtonEventType = ButtonEventType.MV
    old_state: MouseState = MouseState.UpUp
    new_state: MouseState = MouseState.UpUp


class GameFinishedEvent(BaseEvent, tag="game_end"):
    """
    游戏结束事件。发生在游戏胜利、失败、重开、游戏关闭、游戏设置关闭、切换游戏状态关闭、
    游戏状态变为非正式等情况。
    playing状态切换为其他状态时触发此消息。自定义难度、各种模式均会触发。正式的游戏中间转为
    非正式状态（例如用空格看概率）也会触发此消息。
    """

    # 游戏的新状态（旧状态必为playing），'ready'、'study'、'show'、'playing'、'joking'、
    # 'fail'、'win'、'jofail'、'jowin'、'display'、'showdisplay'分别记作0-10
    game_state: int = 0
    # False-flag, True-nf
    nf: bool = False
    row: int = 16
    column: int = 30
    mine_num: int = 99
    rtime: float = 0.0
    left: int = 126
    right: int = 11
    double: int = 14
    # 游戏难度（级别）。3是初级；4是中级；5是高级；6是自定义。
    level: int = 5
    cl: int = 151
    ce: int = 144
    rce: int = 11
    lce: int = 119
    dce: int = 14
    bbbv: int = 127
    bbbv_solved: int = 127
    zini: int = 105
    flag: int = 11
    path: float = 6082.352554578606
    # 时间戳，微秒
    start_time: int = 1666124135606000
    end_time: int = 1666124184868000
    # 标准0、win74、经典无猜5、强无猜6、弱无猜7、准无猜8、强可猜9、弱可猜10
    mode: int = 0
    software: str = "元 3.2.2"
    player_identifier: str = "Wang Jianing"
    race_identifier: str = "G1234"
    unique_identifier: str = ""
    is_official: bool = False
    is_fair: bool = False
    op: int = 0
    isl: int = 0
    pluck: float = 0
    # 带有计算好的数字
    board: List[List[int]] = []
    # evf4版本的二进制数据
    raw_data: bytes = b""



class CloseEvent(BaseEvent, tag="close"):
    """游戏即将关闭事件"""
    pass


class ShowPluginManagerEvent(BaseEvent, tag="show_plugin_manager"):
    """请求显示插件管理器窗口事件"""
    pass


class LanguageChangeEvent(BaseEvent, tag="language_change"):
    """语言变化及快照；同一来源的 revision 递增，快照沿用原版本。

    新字段均有默认值：旧发送端仍可解码，新发送端也兼容忽略未知字段的旧接收端。
    source_id 为空或 revision 为 0 表示旧协议，不提供跨通道顺序保证。
    """
    language: str = "en_US"
    source_id: str = ""
    revision: int = 0


EVENT_TYPES = [
    BoardUpdateEvent,
    GameStatusChangeEvent,
    ButtonClickEvent,
    GameFinishedEvent,
    CloseEvent,
    ShowPluginManagerEvent,
    LanguageChangeEvent,
]
