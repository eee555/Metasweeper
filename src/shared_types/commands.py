"""
扫雷游戏控制指令定义
"""
from __future__ import annotations

from typing import List, Optional

import msgspec

from PySide6.QtCore import QCoreApplication

from lib_zmq_plugins.shared.base import BaseCommand

from .enums import GameLevel, GameMode

_translate = QCoreApplication.translate


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


class SetSoundCommand(BaseCommand, tag="set_sound"):
    """热更新游戏音效（纯内存、不写 gameSetting.ini、不重启）。

    与 `SetSkinCommand` 完全独立：独立的 tag、独立的控制授权，插件可以只
    申请音效权限而不影响皮肤权限。主进程只把它转调给
    `utils.sound_manager.SoundManager`，游戏逻辑代码不感知。

    Attributes:
        enabled: 是否启用音效；None 表示保持当前值
        volume: 音量 0~100；None 表示保持当前值
        pack: 音效包目录名；空串表示默认音效；None 表示保持当前值
        extra_dir: 额外音效库目录；None 表示保持当前值
        reset: True 时恢复主进程启动时从 ini 读入的音效设置（忽略以上字段）
        play_event: 可选，应用设置后试听一个事件（如 "open" / "win"）；
            仅用于插件界面试听，不属于游戏性音效触发
    """
    enabled: Optional[bool] = None
    volume: Optional[int] = None
    pack: Optional[str] = None
    extra_dir: Optional[str] = None
    reset: bool = False
    play_event: Optional[str] = None


# 音效事件名（与 SoundManager.SoundEvent.value 一致），供命令校验
SOUND_EVENT_NAMES = (
    "ready", "start", "open", "chord", "flag_on", "flag_off",
    "question", "win", "lose",
)


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
                 MouseClickCommand, InitOpenCommand, SetSkinCommand,
                 SetSoundCommand]

# ── 控制命令说明（可多语言）────────────────────────────────────
# 供插件管理器「控制授权」对话框、插件详情对话框，以及主程序
# 「高级设置」里的作弊开关统一使用，避免各处各写一份、新增命令漏配。
#
# 键为 msgspec tag；值为「中文源文本」。运行时由 command_label()/
# command_hint() 经 _translate(COMMANDS_I18N_CONTEXT, <源文本>) 返回
# 当前语言译文，因此这里始终保存中文作为 lupdate 抽取用的 source text。
# 新增命令时：① 在两张 dict 各补一行 ② 在 _i18n_command_strings() 补
# translate 调用 ③ 确认本文件在 src/ui/生成ts文件.bat 的 SHARED 清单里。
COMMAND_LABELS: dict[str, str] = {
    "new_random_game": "重开新局",
    "new_preset_game": "预设局面",
    "mouse_click": "鼠标点击",
    "init_open": "初始化翻开",
    "set_skin": "更换皮肤",
    "set_sound": "更改音效",
}

COMMAND_HINTS: dict[str, str] = {
    "new_random_game": "插件随机重开一局（结果非 official / 非 fair）",
    "new_preset_game": "按指定棋盘开局（模式为 UPK，可含官方记录）",
    "mouse_click": "对指定格子模拟左 / 中 / 右键点击",
    "init_open": "预设局面初始化时翻开指定格子",
    "set_skin": "热替换主窗口图片皮肤（纯内存、不重启、独立授权）",
    "set_sound": "热更新游戏音效开关 / 音量 / 音效包（独立于皮肤授权）",
}

# 翻译上下文（对应 .ts 里的 <context><name>，三处界面共用同一份词条）
COMMANDS_I18N_CONTEXT = "Commands"


def _i18n_command_strings() -> None:
    """pyside6-lupdate 扫描用哑函数，运行时不调用。

    command_label()/command_hint() 以变量向 translate() 传源文本，扫描器
    无法抽取；这里把源文本逐条硬编码进 translate() 调用，让它们进入 .ts。
    与 plugins/XianNiUpgrade/models.py 的 _i18n_hints() 同一套路。

    ⚠️ context 必须是字符串字面量 "Commands"（不能用变量）：
    pyside6-lupdate 静态分析要求 context 为字面量，否则整条词条被跳过。
    运行时 command_label()/command_hint() 用常量 COMMANDS_I18N_CONTEXT，
    其值同为 "Commands"，与 .ts 里的 <name>Commands</name> 对齐。
    新增命令时在此同步补行。
    """
    _translate("Commands", "重开新局")
    _translate("Commands", "预设局面")
    _translate("Commands", "鼠标点击")
    _translate("Commands", "初始化翻开")
    _translate("Commands", "更换皮肤")
    _translate("Commands", "更改音效")
    _translate("Commands",
               "插件随机重开一局（结果非 official / 非 fair）")
    _translate("Commands",
               "按指定棋盘开局（模式为 UPK，可含官方记录）")
    _translate("Commands",
               "对指定格子模拟左 / 中 / 右键点击")
    _translate("Commands",
               "预设局面初始化时翻开指定格子")
    _translate("Commands",
               "热替换主窗口图片皮肤（纯内存、不重启、独立授权）")
    _translate("Commands",
               "热更新游戏音效开关 / 音量 / 音效包（独立于皮肤授权）")


def command_tag(cmd_type: type) -> str:
    """取命令类的 msgspec tag；失败返回类名兜底。tag 是技术标识，不翻译。"""
    cfg = getattr(cmd_type, "__struct_config__", None)
    tag = getattr(cfg, "tag", None) if cfg is not None else None
    return str(tag) if tag else cmd_type.__name__


def command_label(cmd_type: type) -> str:
    """简短名称，按当前界面语言返回译文；无对应 tag 时回退类名（不翻译）。"""
    src = COMMAND_LABELS.get(command_tag(cmd_type))
    if src is None:
        return cmd_type.__name__
    return _translate(COMMANDS_I18N_CONTEXT, src)


def command_hint(cmd_type: type) -> str:
    """一句话说明，按当前语言返回译文；无对应 tag 时回退 docstring 首行
    （技术兜底，不翻译）。"""
    src = COMMAND_HINTS.get(command_tag(cmd_type))
    if src is not None:
        return _translate(COMMANDS_I18N_CONTEXT, src)
    doc = (cmd_type.__doc__ or "").strip().splitlines()
    return doc[0] if doc else cmd_type.__name__
