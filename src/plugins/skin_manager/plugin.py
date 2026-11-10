"""皮肤管理插件：运行时热替换主窗口图片资源（纯内存，不重启）。

皮肤选择由 config.py 自动注册成设置页里的下拉框（ChoiceConfig），
插件本身只负责把选中皮肤的图片字节通过 SetSkinCommand 发给主进程。
"""
from __future__ import annotations

import warnings
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

from plugin_sdk import BasePlugin, PluginInfo, WindowMode
from shared_types.commands import SetSkinCommand, SetSoundCommand

from .config import (
    BUILTIN_SKINS_DIR, SkinManagerConfig, discover_choices, register_choices,
)
from .skins import build_command
from .sound import (
    build_sound_command, discover_sound_choices, imported_sound_dir,
    seed_builtin_sound_packs,
)
from .zip_import import imported_dir
from .widgets import SkinManagerWidget


def _safe_disconnect(signal, slot) -> None:
    """断开信号连接，且容忍「本来就没连上」。

    PySide6 的 `Signal.disconnect()` 在连接不存在时**不抛异常**，而是发出
    `RuntimeWarning: libpyside: Failed to disconnect ...`，因此
    `try/except (RuntimeError, TypeError)` 抓不住，会在每次插件初始化时
    刷一条告警。这里把该警告就地忽略（仅限这一句调用），并用
    try/except 兜住真正抛异常的其他绑定类型。
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=".*Failed to disconnect.*",
            category=RuntimeWarning)
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass


class SkinManagerPlugin(BasePlugin[SkinManagerConfig]):
    """把皮肤图片字节发给主进程，主进程只改内存缓存。"""

    def __init__(self, info: PluginInfo):
        super().__init__(info)
        # 缓存上一次成功应用的皮肤名，避免重复发送
        self._applied: str | None = None
        # 音效状态与皮肤状态完全独立，单独缓存
        self._sound_applied: tuple | None = None

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="皮肤与音效",
            version="1.1.0",
            description=(
                "设置页分别选择皮肤与音效包，运行时热替换（纯内存、不重启）；"
                "两者为相互独立的功能与授权"
            ),
            icon=QIcon(str(Path(__file__).resolve().with_name("icon.svg"))),
            window_mode=WindowMode.TAB,
            other_info=SkinManagerConfig,
            # 两条独立授权：只授权其中一个也能正常使用对应功能
            required_controls=[SetSkinCommand, SetSoundCommand],
        )

    def _setup_subscriptions(self) -> None:
        # 本插件只发指令，不订阅游戏事件
        pass

    def _create_widget(self) -> QWidget:
        widget = SkinManagerWidget()
        widget.apply_requested.connect(
            self._on_apply_requested, Qt.ConnectionType.QueuedConnection)
        widget.sound_preview_requested.connect(
            self._on_sound_preview_requested,
            Qt.ConnectionType.QueuedConnection)
        return widget

    # ── 皮肤库根目录（自带 + zip 导入落地目录）────────────────────
    def _roots(self) -> list[Path]:
        return [BUILTIN_SKINS_DIR, imported_dir("skins")]

    def _refresh_choices(self) -> None:
        """重新扫描皮肤目录并刷新配置类上的 ChoiceConfig 选项。"""
        choices = discover_choices()
        register_choices(SkinManagerConfig, "skin", choices)
        # 已实例化的配置对象持有自己的 _fields，需同步替换
        if self.other_info is not None:
            fields = self.other_info._fields
            if "skin" in fields:
                fields["skin"] = getattr(SkinManagerConfig, "skin")
        if self._applied is not None and self._applied not in dict(choices):
            # 已应用的皮肤包被删除/改名：清缓存的同时必须让主进程还原，
            # 否则插件认为「未应用」，主窗口却仍显示已消失的皮肤。
            self._applied = None
            self._apply("", force=True)
        # 配置值可能仍指向已失效的包名，同步修正回默认，避免下次 auto_apply
        # 用一个不存在的名字反复发请求。
        current = str(self.other_info.skin or "") if self.other_info else ""
        if current and current not in dict(choices):
            self.other_info.skin = ""

    # ── 应用 / 还原 ──────────────────────────────────────────────
    def _apply(self, skin_name: str, force: bool = False) -> None:
        if not force and skin_name == self._applied:
            return
        roots = self._roots()
        if not skin_name:
            cmd = SetSkinCommand(reset=True)
            detail = "默认皮肤"
        else:
            cmd = build_command(roots, skin_name)
            if cmd.reset:
                self.logger.warning(f"皮肤目录不存在: {skin_name}")
                self._notify(f"皮肤目录不存在：{skin_name}")
                return
            detail = (
                f"{skin_name}（格子 {len(cmd.cells)}、LED {len(cmd.leds)}、"
                f"笑脸 {len(cmd.faces)}）"
            )

        resp = self.request(cmd, timeout=10.0)
        if resp is None:
            self._notify("主进程未响应（可能尚未连接或未授权）")
            self.logger.warning("SetSkinCommand 无响应，请检查连接与控制授权")
            return
        if not resp.success:
            self._notify(f"应用失败：{resp.error}")
            self.logger.warning(f"SetSkinCommand 被拒绝: {resp.error}")
            return

        self._applied = skin_name
        self.logger.info(f"已应用皮肤: {detail}")
        self._notify(f"已应用：{detail}")

    def _notify(self, text: str) -> None:
        # 在 GUI 执行时读取当前窗口，关闭期间自动跳过通知。
        self.run_on_widget(
            lambda widget, message: widget.set_status(message), text)

    def _on_apply_requested(self) -> None:
        """界面上「重新应用」按钮：强制重发一次当前皮肤。"""
        self._apply(str(self.other_info.skin or ""), force=True)

    # ═══════════════════════════════════════════════════════════════
    # 音效（与皮肤完全独立：独立目录扫描、独立命令、独立状态缓存）
    # ═══════════════════════════════════════════════════════════════
    def _refresh_sound_choices(self) -> None:
        """重新扫描音效包目录并刷新配置类上的 ChoiceConfig 选项。"""
        choices = discover_sound_choices()
        register_choices(SkinManagerConfig, "sound_pack", choices)
        if self.other_info is not None:
            fields = self.other_info._fields
            if "sound_pack" in fields:
                fields["sound_pack"] = getattr(SkinManagerConfig, "sound_pack")
        current = str(self.other_info.sound_pack or "") if self.other_info else ""
        if current and current not in dict(choices):
            self.other_info.sound_pack = ""

    def _apply_sound(self, force: bool = False, *,
                     play_event: str | None = None) -> None:
        """把当前音效设置通过独立的 SetSoundCommand 发给主进程。"""
        cfg = self.other_info
        state = (
            bool(cfg.sound_enabled),
            int(cfg.sound_volume),
            str(cfg.sound_pack or ""),
            str(imported_sound_dir()),
        )
        # 试听不参与去重，否则连点试听会被跳过
        if not force and play_event is None and state == self._sound_applied:
            return
        try:
            cmd = build_sound_command(
                enabled=state[0], volume=state[1], pack=state[2],
                extra_dir=state[3], play_event=play_event)
        except ValueError as exc:
            self._notify(f"音效参数无效：{exc}")
            return

        resp = self.request(cmd, timeout=10.0)
        if resp is None:
            self._notify("主进程未响应（可能尚未连接或未授权 SetSoundCommand）")
            self.logger.warning("SetSoundCommand 无响应，请检查连接与控制授权")
            return
        if not resp.success:
            self._notify(f"音效应用失败：{resp.error}")
            self.logger.warning(f"SetSoundCommand 被拒绝: {resp.error}")
            return

        self._sound_applied = state
        label = f"音效（{'开' if state[0] else '关'}，音量 {state[1]}，包 {state[2] or '默认'}）"
        self.logger.info(f"已应用{label}")
        self._notify(f"已应用：{label}")

    def _on_sound_preview_requested(self, event: str) -> None:
        """界面试听按钮：先应用当前设置，再让主进程播一个事件。"""
        self._apply_sound(force=True, play_event=event)

    # ── 生命周期 ─────────────────────────────────────────────────
    def on_initialized(self) -> None:
        # 音效包完全由本插件管理：先把随插件分发的示例包播种到两进程共享
        # 的可写数据目录，再刷新下拉框，用户即可直接选到 soft/ 等包。
        seed_builtin_sound_packs()
        # 停用→再启用会二次调用 on_initialized；Qt 默认不去重相同连接，
        # 先断开再连，避免一次配置变化触发两次 _on_config_changed（force
        # 分支会重复发送最多 4MB 图片、试听双响）。
        _safe_disconnect(self.config_changed, self._on_config_changed)
        self.config_changed.connect(
            self._on_config_changed, Qt.ConnectionType.QueuedConnection)
        self._refresh_choices()
        self._refresh_sound_choices()
        if self.other_info.auto_apply:
            # 固定 1500/1600ms 是竞态：慢启动机器上 ZMQ 未就绪时
            # request() 返回 None 后无重试，此后不再应用。改为带一次重试的
            # 短延时，并在成功后不再重复发送。
            from PySide6.QtCore import QTimer

            def _auto_apply(retry: int = 1) -> None:
                skin = str(self.other_info.skin or "")
                if skin:
                    self._apply(skin, force=True)
                self._apply_sound(force=True)
                if retry and (self._applied is None and skin):
                    QTimer.singleShot(2000, lambda: _auto_apply(retry - 1))

            QTimer.singleShot(1500, lambda: _auto_apply(1))

    def _on_config_changed(self, name: str, value) -> None:
        if name == "skin_zip":
            # zip 已解压到插件数据目录；_refresh_choices 内部会处理失效包还原
            self._refresh_choices()
        elif name == "sound_zip":
            self._refresh_sound_choices()
            self._apply_sound(force=True)
        elif name == "skin":
            self._apply(str(value or ""))
        elif name in ("sound_enabled", "sound_volume", "sound_pack"):
            self._apply_sound()

    def on_shutdown(self) -> None:
        # 断开持久信号，避免停用→再启用时重复连接累积。
        _safe_disconnect(self.config_changed, self._on_config_changed)
        # 插件关闭时分别还原主进程内存皮肤与音效（主进程退出本身也会自动还原）
        try:
            self.request(SetSkinCommand(reset=True), timeout=2.0)
        except Exception:
            pass
        try:
            self.request(SetSoundCommand(reset=True), timeout=2.0)
        except Exception:
            pass
