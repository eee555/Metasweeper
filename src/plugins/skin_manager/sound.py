"""皮肤管理插件内的「音效」功能模块（与皮肤完全独立）。

与 `skins.py` 平级但互不依赖：
- 皮肤：把图片**字节**通过 `SetSkinCommand` 发给主进程；
- 音效：只把音效包**目录名 / 开关 / 音量**通过 `SetSoundCommand` 发给主进程，
  素材由主进程从 `media/sounds/` 自行读取，插件不传输 wav 字节。

音效包目录扫描规则与皮肤一致：一个子目录就是一个包，`sound.json` 提供显示名，
`_` 开头的目录跳过。插件只在自己的资源目录里发现包；主进程侧还有自带
`media/sounds/`，两者以主进程的 `resolve()` 为准。
"""
from __future__ import annotations

import json
from pathlib import Path

from shared_types.commands import SetSoundCommand, SOUND_EVENT_NAMES
from utils.path_utils import resource_path
from .zip_import import imported_dir

# 插件自带音效库（若插件目录里放了 sounds/ 就与主进程自带库合并）
BUILTIN_SOUND_DIR = Path(__file__).resolve().parent / "sounds"
# 主进程自带音效库：只读扫描目录名，不读取 wav 字节（素材由主进程自行加载）
GAME_SOUND_DIR = resource_path("media") / "sounds"
SOUND_META_FILE = "sound.json"


def imported_sound_dir() -> Path:
    """zip 导入到插件数据目录的音效包根目录，同时作为 extra_dir 传给主进程。"""
    return imported_dir("sounds")

DEFAULT_PACK = ""
DEFAULT_PACK_LABEL = "默认音效（不替换）"


def list_sound_packs(root: Path | str | None) -> list[tuple[str, str]]:
    """扫描音效包目录，返回 [(目录名, 显示名), ...]，按目录名排序。"""
    if root is None:
        return []
    root = Path(root)
    if not root.is_dir():
        return []
    result: list[tuple[str, str]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        display = child.name
        meta = child / SOUND_META_FILE
        if meta.is_file():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                display = str(data.get("name") or child.name)
            except (OSError, ValueError, TypeError):
                pass
        result.append((child.name, display))
    return result


def discover_sound_choices(extra_dir: Path | str | None = None) -> list[tuple[str, str]]:
    """返回设置页下拉框选项 `[(值, 显示名), ...]`。

    扫描顺序：主进程自带 `media/sounds/` → 插件数据目录 `sounds/`（zip 导入）
    → 插件自带 `sounds/` → 可选额外目录。只发现目录名（不传输 wav 字节），
    同名以先扫描到的为准。首个选项固定为「默认音效」。
    """
    choices: dict[str, str] = {}
    roots = [GAME_SOUND_DIR, imported_sound_dir(), BUILTIN_SOUND_DIR]
    if extra_dir:
        roots.append(Path(str(extra_dir).strip()))
    for root in roots:
        for name, display in list_sound_packs(root):
            choices.setdefault(name, display)
    return [
        (DEFAULT_PACK, DEFAULT_PACK_LABEL),
        *[(name, choices[name]) for name in sorted(choices)],
    ]


def build_sound_command(
    *,
    enabled: bool | None = None,
    volume: int | None = None,
    pack: str | None = None,
    extra_dir: str | None = None,
    play_event: str | None = None,
) -> SetSoundCommand:
    """构造 `SetSoundCommand`（只传参数，不传输 wav 字节）。"""
    if play_event is not None and play_event not in SOUND_EVENT_NAMES:
        raise ValueError(f"未知音效事件: {play_event!r}")
    if volume is not None and not (0 <= volume <= 100):
        raise ValueError(f"音量超出范围: {volume}")
    # 未显式指定时，始终把「插件数据目录 sounds/」作为主进程的额外音效库，
    # 这样 zip 导入的包主进程也能 resolve 到（主进程自己不读插件目录）。
    if extra_dir is None:
        extra_dir = str(imported_sound_dir())
    return SetSoundCommand(
        enabled=enabled,
        volume=volume,
        pack=pack,
        extra_dir=extra_dir,
        play_event=play_event,
    )
