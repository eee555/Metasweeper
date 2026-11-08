"""
扫雷游戏控制指令定义
"""
from __future__ import annotations

from typing import List, Optional

import msgspec

from lib_zmq_plugins.shared.base import BaseCommand

from .enums import GameLevel, GameMode


class NewGameCommand(BaseCommand, tag="new_random_game"):
    """
    新随机游戏指令，不安全，official和fair为false。

    Attributes:
        level: 游戏难度，使用 GameLevel 枚举值
            - 3: 初级 (8x8, 10雷)
            - 4: 中级 (16x16, 40雷)
            - 5: 高级 (16x30, 99雷)
            - 6: 自定义（使用 rows/cols/mines）
        rows: 行数（自定义模式时使用）
        cols: 列数（自定义模式时使用）
        mines: 地雷数（自定义模式时使用）
        mode: 可选，游戏模式，使用 GameMode 枚举值
    """
    level: int = 5
    rows: Optional[int] = None
    cols: Optional[int] = None
    mines: Optional[int] = None
    mode: Optional[int] = GameMode.Standard.value


class NewPresetGameCommand(BaseCommand, tag="new_preset_game"):
    """
    新预设游戏指令，official和fair可能为true。但是gamemode必定为upk。

    Attributes:
        board: 可选，预设局面，-1表示雷
        mode: 可选，游戏模式，使用 GameMode 枚举值
    """
    board: List[List[int]] = None  # type: ignore
    mode: Optional[int] = GameMode.Standard.value


class MouseClickCommand(BaseCommand, tag="mouse_click"):
    """
    鼠标点击指令

    Attributes:
        row: 行索引（从 0 开始）
        col: 列索引（从 0 开始）
        button: 鼠标按钮
            - 0: 左键（揭开格子）
            - 1: 中键
            - 2: 右键（标旗）
        modifiers: 键盘修饰符（保留）
    """
    row: int = 0
    col: int = 0
    button: int = 0
    modifiers: int = 0


class InitOpenCommand(BaseCommand, tag="init_open"):
    """
    初始化翻开指令。此指令是安全的，但是要求局面使用预设局面，且最终模式为upk。
    此指令仅会在局面初始化时，翻开指定的格子。游戏过程中是否使用，还需要讨论，目前不可以。

    Attributes:
        row: 行索引（从 0 开始）
        col: 列索引（从 0 开始）
    """
    row: int = 0
    col: int = 0


class SetSkinCommand(BaseCommand, tag="set_skin"):
    """
    热替换主窗口图片资源（纯内存，不写磁盘、不重启）。

    所有资源以原始图片字节（SVG/PNG）传输，由主进程解码为 QPixmap 后
    写入各控件的内存缓存，重绘后立即生效；主进程退出即自动还原。

    Attributes:
        cells: 格子图 {key: bytes}，key 见 SKIN_CELL_KEYS（16 张）
        leds:  LED 数字 {0..9: bytes}（10 张）
        faces: 笑脸 {FACE_*: bytes}，key 见 SKIN_FACE_KEYS（5 张）
        colors: 框架/计数器配色 {键名: #RRGGBB}，见 SKIN_COLOR_KEYS；
            只替换给定的键；提供 frame_svg 时，部分框架纯色背景键由 SVG 接管
        frame_svg: 可选的大幅 SVG 背景，整张绘制在现有 centralwidget 上，子控件透出
        reset: True 时忽略以上所有字段，恢复默认图片、背景与配色
    """
    cells: dict[int, bytes] = msgspec.field(default_factory=dict)
    leds: dict[int, bytes] = msgspec.field(default_factory=dict)
    faces: dict[int, bytes] = msgspec.field(default_factory=dict)
    colors: dict[str, str] = msgspec.field(default_factory=dict)
    frame_svg: bytes | None = None
    reset: bool = False


# 皮肤资源 key（主进程解码校验与插件打包共用；不含窗口图标）
SKIN_CELL_KEYS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 14, 15, 16, 17, 100)
SKIN_LED_KEYS = tuple(range(10))
SKIN_FACE_KEYS = (14, 15, 16, 17, 18)  # FACE_SMILE/CLICK/LOST/WIN/SMILE_DOWN

# 框架配色键：主窗口里非图片的浅灰区域（QPalette / QFrame 原生绘制）
# window        : 主窗口/中央部件背景（原 #c0c0c0）
# frame         : frame_1 外框、frame 雷区边框、顶部条边框（原灰色 3D 边框）
# topbar        : MinenumTimeWigdet 顶部条背景（原浅灰）
# infobar       : 底部 label_info 背景
# text          : 底部信息文字（原黑色）
# flag_bg       : 右下角国旗标签的白底（原 #ffffff；国旗图案本身不变）
# sb_bg         : 计数器（计分板）窗口背景
# sb_text       : 计数器标题与表格文字
# sb_grid       : 计数器表格网格线
# sb_header     : 计数器表格表头/选中底色（可选）
# 注：菜单栏（背景/文字）按需求保持系统原样，不提供配色键
SKIN_COLOR_KEYS = (
    "window", "frame", "topbar", "infobar", "text", "flag_bg",
    "sb_bg", "sb_text", "sb_grid", "sb_header",
)


COMMAND_TYPES = [NewGameCommand, NewPresetGameCommand,
                 MouseClickCommand, InitOpenCommand, SetSkinCommand]
