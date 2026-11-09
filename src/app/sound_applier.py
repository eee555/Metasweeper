"""主进程音效控制命令处理（与 skin_applier 完全独立）。

插件通过 `SetSoundCommand` 热更新音效，这里转调
`utils.sound_manager.SoundManager`：纯内存、不写 gameSetting.ini、不重启。
主进程退出即还原（下次启动仍以 ini 为准）。

handler 由 `GameServerBridge` 的 `Qt.QueuedConnection` 编组到主线程执行，
因此本模块自身无需加锁；并非「天然线程安全」。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from lib_zmq_plugins.shared.base import CommandResponse
from shared_types.commands import SetSoundCommand
from shared_types.sounds import SoundEvent, SOUND_EVENT_NAMES, is_safe_pack_name
from utils.app_logger import logger
from utils.sound_manager import SoundManager

if TYPE_CHECKING:
    from mineSweeperGUI import MineSweeperGUI


class SoundError(ValueError):
    """音效控制参数校验失败"""


# 主进程启动时从 ini 读入的原始设置，供 reset 精确还原。
# 只含开关/音量：音效包完全由插件侧管理，主程序没有也不需要 ini 里的
# pack / extra_dir 状态，reset 不应把插件设置的音效包一起抹掉。
_STARTUP_SETTINGS: dict[str, object] = {}


def capture_startup_settings(ui: "MineSweeperGUI") -> None:
    """记录启动时的音效开关与音量（由 superGUI 初始化完成后调用一次）。"""
    _STARTUP_SETTINGS.clear()
    _STARTUP_SETTINGS.update({
        "enabled": bool(getattr(ui, "sound_enabled", False)),
        "volume": int(getattr(ui, "sound_volume", 70)),
    })


def _resolve_event(name: str) -> SoundEvent:
    try:
        return SoundEvent(name)
    except ValueError as exc:
        raise SoundError(f"未知音效事件: {name!r}") from exc


def _validate_pack(pack: str | None) -> None:
    """`pack` 必须是单层目录名；拒绝 ../、绝对路径与非法字符。"""
    if pack and not is_safe_pack_name(pack):
        raise SoundError(f"非法音效包名: {pack!r}")


def _validate_extra_dir(extra_dir: str | None) -> None:
    """额外音效库只允许指向已存在的目录，拒绝路径穿越与任意路径探测。

    注意：插件侧传来的 `imported_sound_dir()` 本身就是绝对路径，不能一律
    拒绝绝对路径；只拒绝 `..` 穿越与不存在的路径。
    """
    if not extra_dir:
        return
    from pathlib import Path
    try:
        path = Path(extra_dir)
    except (TypeError, ValueError) as exc:
        raise SoundError(f"非法音效库目录: {extra_dir!r}") from exc
    if ".." in path.parts or not path.is_dir():
        raise SoundError(f"非法音效库目录: {extra_dir!r}")


def handle_set_sound(ui: "MineSweeperGUI", cmd: SetSoundCommand) -> CommandResponse:
    """`SetSoundCommand` 的主线程 handler 入口。"""
    try:
        if not _STARTUP_SETTINGS:
            capture_startup_settings(ui)

        mgr = SoundManager.instance()
        if cmd.reset:
            # 只还原主程序职责（开关/音量）；音效包属于插件侧状态，
            # reset 不越权清空，避免插件关闭/重连时把选中的包丢掉。
            mgr.configure(
                enabled=bool(_STARTUP_SETTINGS["enabled"]),
                volume=int(_STARTUP_SETTINGS["volume"]),
                pack=mgr.current_pack(),
                extra_dir=mgr.current_extra_dir(),
            )
        else:
            if cmd.volume is not None and not (0 <= cmd.volume <= 100):
                raise SoundError(f"音量超出范围: {cmd.volume}")
            if cmd.play_event is not None and cmd.play_event not in SOUND_EVENT_NAMES:
                raise SoundError(f"未知音效事件: {cmd.play_event!r}")
            _validate_pack(cmd.pack)
            _validate_extra_dir(cmd.extra_dir)

            # 部分更新时精确回读整数音量 / 状态，避免浮点漂移与读私有属性。
            enabled = (cmd.enabled if cmd.enabled is not None
                       else mgr.current_enabled())
            volume = cmd.volume if cmd.volume is not None else mgr.current_volume()
            pack = cmd.pack if cmd.pack is not None else mgr.current_pack()
            extra_dir = (cmd.extra_dir if cmd.extra_dir is not None
                         else mgr.current_extra_dir())
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
