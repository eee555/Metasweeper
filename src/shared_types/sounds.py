"""音效 / 资源包的跨进程共享定义（纯常量与纯函数）。

本模块被**主进程**与**插件管理器进程**同时 import，因此：
* 不 import QtWidgets、不创建 QApplication、不在模块级做文件 I/O；
* 所有需要翻译的字符串**只在函数被调用时**才取词，避免模块导入期
  在 QApplication 创建前调用 QCoreApplication.translate。

集中放置以下内容，终止此前「SoundEvent / SOUND_FILES / SOUND_PRIORITY /
SOUND_EVENT_NAMES / list_sound_packs / sound.json 解析」在主进程、插件侧、
commands.py 各写一份且彼此不同步的局面。
"""
from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QCoreApplication

# 单层目录名白名单：允许中英文、数字、下划线、连字符；拒绝路径分隔符、..、
# 绝对路径与 Windows 保留字符。用于校验 SetSoundCommand.pack。
_SAFE_PACK_NAME = re.compile(r"^[0-9A-Za-z_\-\u4e00-\u9fff]+$")


class SoundEvent(Enum):
    """游戏性音效事件。新增值只需在此登记 + 放同名 wav。

    注意：项目默认禁用问号（config.constants 未登记问号编码），因此不设
    QUESTION 事件；question.wav 仅为历史遗留素材，不参与播放。
    """

    READY = "ready"          # 程序启动、主窗口就绪
    START = "start"          # 第一次有效左键抬起，埋雷完成
    OPEN = "open"            # 单击开格
    CHORD = "chord"          # 双击（chording）展开
    FLAG_ON = "flag_on"      # 插旗
    FLAG_OFF = "flag_off"    # 拔旗 / 取消标记
    WIN = "win"              # 胜利
    LOSE = "lose"            # 踩雷 / 失败


# 事件 -> 固定文件名。与 skin_manager.skins.CELL_FILES 同一套路。
SOUND_FILES: dict[SoundEvent, str] = {
    event: f"{event.value}.wav" for event in SoundEvent
}

# 同一 tick 内多个 cue 只播优先级最高的一个；同时发声超过上限时按此表
# 停掉优先级最低的 cue。此前该表定义在 SoundManager 里却从未被读取，
# 现在由 SoundManager 直接消费，三套互斥/限流机制合并为这一套。
SOUND_PRIORITY: dict[SoundEvent, int] = {
    SoundEvent.WIN: 100,
    SoundEvent.LOSE: 100,
    SoundEvent.READY: 90,
    SoundEvent.START: 80,
    SoundEvent.CHORD: 60,
    SoundEvent.OPEN: 40,
    SoundEvent.FLAG_ON: 20,
    SoundEvent.FLAG_OFF: 20,
}

# 结局音：播放时清场，并在短时间内压掉其他 cue。
EXCLUSIVE_EVENTS = frozenset({SoundEvent.WIN, SoundEvent.LOSE})

# 音效事件名（供命令参数校验；由枚举派生，不再手工维护第二份清单）
SOUND_EVENT_NAMES: tuple[str, ...] = tuple(e.value for e in SoundEvent)

# ── 音效包 ────────────────────────────────────────────────────────
DEFAULT_PACK = ""                       # 空串 = 使用根目录默认音效
SOUND_META_FILE = "sound.json"
SKIN_META_FILE = "skin.json"


def default_pack_label() -> str:
    """下拉框的「默认音效」选项（按当前界面语言取词）。"""
    return QCoreApplication.translate("Sounds", "默认音效（不替换）")


def default_skin_label() -> str:
    """下拉框的「默认皮肤」选项（按当前界面语言取词）。"""
    return QCoreApplication.translate("Sounds", "默认皮肤（不替换）")


def is_safe_pack_name(name: str) -> bool:
    """`pack` 必须是单层目录名，拒绝 ../、绝对路径与非法字符。"""
    if not name or name.startswith("_"):
        return False
    return bool(_SAFE_PACK_NAME.fullmatch(name))


def read_meta_name(meta: Path, fallback: str) -> str:
    """从 skin.json / sound.json 读显示名；任何异常都静默回退到目录名。

    早期实现只捕获 (OSError, ValueError, TypeError)，而 ``[]`` / ``null`` /
    字符串这类合法 JSON 会让 ``data.get(...)`` 抛 AttributeError，进而使
    插件模块导入失败。这里先做 dict 类型判断，从根上消除该问题。
    """
    if not meta.is_file():
        return fallback
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return fallback
        return str(data.get("name") or fallback)
    except (OSError, ValueError, TypeError, UnicodeError, AttributeError):
        return fallback


def list_packs(root: Path | str | None, meta_file: str = SOUND_META_FILE):
    """扫描资源包目录，返回 [(目录名, 显示名), ...]，按目录名排序。

    跳过 `_` 开头的目录（临时目录、模板目录）。此前该函数在主进程
    ``utils/sound_manager.py`` 与插件侧 ``plugins/skin_manager/sound.py``
    各有一份近乎逐行相同、根目录顺序却不同的实现，导致「下拉框能选、
    主进程 resolve 不到」。现在统一到这一处。
    """
    if root is None:
        return []
    root = Path(root)
    try:
        if not root.is_dir():
            return []
        children = sorted(root.iterdir())
    except OSError:
        return []
    result: list[tuple[str, str]] = []
    for child in children:
        try:
            if not child.is_dir() or child.name.startswith("_"):
                continue
        except OSError:
            continue
        result.append((child.name, read_meta_name(child / meta_file, child.name)))
    return result
