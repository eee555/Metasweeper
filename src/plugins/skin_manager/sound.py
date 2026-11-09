"""皮肤管理插件内的「音效」功能模块（与皮肤完全独立）。

与 `skins.py` 平级但互不依赖：
- 皮肤：把图片**字节**通过 `SetSkinCommand` 发给主进程；
- 音效：只把音效包**目录名 / 开关 / 音量**通过 `SetSoundCommand` 发给主进程，
  素材由主进程自行读取，插件不传输 wav 字节。

**音效包的选择完全由本插件负责**：主程序只保留 `media/sounds/*.wav` 这一组
默认资源，不再有任何音效包下拉框。插件自带示例包位于
`plugins/skin_manager/sounds/`，在插件初始化时播种到两进程共享的可写数据
目录 `data/plugin_data/SkinManagerPlugin/sounds/`（zip 导入也落在这里）。
主进程通过 `SetSoundCommand.extra_dir` 指向该目录，从而能 resolve 到包名。

扫描统一使用 `shared_types.sounds.list_packs`，只认这一个根，避免此前
「下拉框能选、主进程 resolve 不到」的不一致。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from shared_types.commands import SetSoundCommand, SOUND_EVENT_NAMES
from shared_types.sounds import (
    SOUND_META_FILE, default_pack_label, is_safe_pack_name, list_packs,
)
from utils.app_logger import logger
from .zip_import import imported_dir

# 随插件一起分发的示例/内置音效包（只读）
BUILTIN_SOUND_DIR = Path(__file__).resolve().parent / "sounds"


def imported_sound_dir() -> Path:
    """zip 导入到插件数据目录的音效包根目录，同时作为 extra_dir 传给主进程。"""
    return imported_dir("sounds")


def seed_builtin_sound_packs() -> None:
    """把插件自带的音效包播种到「插件数据目录/sounds/」。

    只补目标不存在的包（不覆盖用户 zip 导入或已修改的同名包），因此每次
    插件启动都安全。主进程与插件管理器共享同一个可写 data 目录
    （由 --data-dir 传递），所以播到这里主进程就能通过 extra_dir 加载。
    """
    if not BUILTIN_SOUND_DIR.is_dir():
        return
    dest_root = imported_sound_dir()
    try:
        candidates = sorted(
            p for p in BUILTIN_SOUND_DIR.iterdir()
            if p.is_dir() and not p.name.startswith("_")
        )
    except OSError as exc:
        logger.warning(f"[SkinManager] 无法读取内置音效包目录: {exc}")
        return
    for src in candidates:
        dest = dest_root / src.name
        if dest.exists():
            continue                       # 已存在：尊重用户数据，不覆盖
        try:
            shutil.copytree(
                src, dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        except OSError as exc:
            logger.warning(f"[SkinManager] 播种音效包 {src.name} 失败: {exc}")


def discover_sound_choices() -> list[tuple[str, str]]:
    """返回设置页下拉框选项 `[(值, 显示名), ...]`。

    扫描插件数据目录下的音效包（内置示例 + zip 导入）；主程序自带的
    `media/sounds/*.wav` 为默认资源，不作为可选包列出。
    """
    choices: dict[str, str] = dict(
        list_packs(imported_sound_dir(), SOUND_META_FILE))
    return [
        ("", default_pack_label()),
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
    if pack and not is_safe_pack_name(pack):
        raise ValueError(f"非法音效包名: {pack!r}")
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
