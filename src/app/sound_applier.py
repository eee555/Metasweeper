"""主进程音效控制命令处理（与 skin_applier 完全独立）。

插件通过 `SetSoundCommand` 热更新音效，这里只在主线程转调
`utils.sound_manager.SoundManager`：纯内存、不写 gameSetting.ini、不重启。
主进程退出即还原（下次启动仍以 ini 为准）。

不修改游戏逻辑，也不触碰任何 GUI 控件，因此 handler 天然线程安全。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from lib_zmq_plugins.shared.base import CommandResponse
from shared_types.commands import SetSoundCommand, SOUND_EVENT_NAMES
from utils.app_logger import logger
from utils.sound_manager import SoundEvent, SoundManager

if TYPE_CHECKING:
    from mineSweeperGUI import MineSweeperGUI


class SoundError(ValueError):
    """音效控制参数校验失败"""


# 主进程启动时从 ini 读入的原始设置，供 reset 精确还原
_STARTUP_SETTINGS: dict[str, object] = {}


def capture_startup_settings(ui: "MineSweeperGUI") -> None:
    """记录启动时的音效设置（由 superGUI 初始化完成后调用一次）。"""
    _STARTUP_SETTINGS.clear()
    _STARTUP_SETTINGS.update({
        "enabled": bool(getattr(ui, "sound_enabled", False)),
        "volume": int(getattr(ui, "sound_volume", 70)),
        "pack": str(getattr(ui, "sound_pack", "") or ""),
        "extra_dir": str(getattr(ui, "sound_extra_dir", "") or ""),
    })


def _resolve_event(name: str) -> SoundEvent:
    try:
        return SoundEvent(name)
    except ValueError as exc:
        raise SoundError(f"未知音效事件: {name!r}") from exc


def handle_set_sound(ui: "MineSweeperGUI", cmd: SetSoundCommand) -> CommandResponse:
    """`SetSoundCommand` 的主线程 handler 入口。"""
    try:
        if not _STARTUP_SETTINGS:
            capture_startup_settings(ui)

        mgr = SoundManager.instance()
        if cmd.reset:
            mgr.configure(
                enabled=bool(_STARTUP_SETTINGS["enabled"]),
                volume=int(_STARTUP_SETTINGS["volume"]),
                pack=str(_STARTUP_SETTINGS["pack"]),
                extra_dir=str(_STARTUP_SETTINGS["extra_dir"]),
            )
        else:
            if cmd.volume is not None and not (0 <= cmd.volume <= 100):
                raise SoundError(f"音量超出范围: {cmd.volume}")
            if cmd.play_event is not None and cmd.play_event not in SOUND_EVENT_NAMES:
                raise SoundError(f"未知音效事件: {cmd.play_event!r}")

            enabled = cmd.enabled if cmd.enabled is not None else mgr._enabled
            volume = cmd.volume if cmd.volume is not None else int(mgr._volume * 100)
            pack = cmd.pack if cmd.pack is not None else mgr.current_pack()
            extra_dir = (cmd.extra_dir if cmd.extra_dir is not None
                         else str(mgr._extra_dir) if mgr._extra_dir else "")
            mgr.configure(enabled=enabled, volume=volume,
                          pack=pack, extra_dir=extra_dir)

            if cmd.play_event:
                mgr.play(_resolve_event(cmd.play_event))

        return CommandResponse(request_id=cmd.request_id, success=True)
    except SoundError as exc:
        logger.warning(f"[Sound] 音效设置被拒绝: {exc}")
        return CommandResponse(
            request_id=cmd.request_id, success=False, error=str(exc))
    except Exception as exc:
        logger.opt(exception=True).warning(f"[Sound] 应用音效设置失败: {exc}")
        return CommandResponse(
            request_id=cmd.request_id, success=False, error=str(exc))
