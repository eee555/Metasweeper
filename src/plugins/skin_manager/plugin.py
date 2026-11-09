"""皮肤管理插件：运行时热替换主窗口图片资源（纯内存，不重启）。

皮肤选择由 config.py 自动注册成设置页里的下拉框（ChoiceConfig），
插件本身只负责把选中皮肤的图片字节通过 SetSkinCommand 发给主进程。
"""
from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

from plugin_sdk import BasePlugin, PluginInfo, WindowMode
from shared_types.commands import SetSkinCommand

from .config import (
    BUILTIN_SKINS_DIR, SkinManagerConfig, discover_choices, register_skins,
)
from .skins import build_command
from .widgets import SkinManagerWidget


class SkinManagerPlugin(BasePlugin[SkinManagerConfig]):
    """把皮肤图片字节发给主进程，主进程只改内存缓存。"""

    def __init__(self, info: PluginInfo):
        super().__init__(info)
        self._widget: QWidget | None = None
        # 缓存上一次成功应用的皮肤名，避免重复发送
        self._applied: str | None = None

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="皮肤管理",
            version="1.0.0",
            description="设置页下拉框选皮肤，运行时热替换主窗口图片资源（纯内存）",
            icon=QIcon(str(Path(__file__).resolve().with_name("icon.svg"))),
            window_mode=WindowMode.TAB,
            other_info=SkinManagerConfig,
            required_controls=[SetSkinCommand],
        )

    def _setup_subscriptions(self) -> None:
        # 本插件只发指令，不订阅游戏事件
        pass

    def _create_widget(self) -> QWidget:
        widget = SkinManagerWidget()
        self._widget = widget
        widget.apply_requested.connect(
            self._on_apply_requested, Qt.ConnectionType.QueuedConnection)
        return widget

    @property
    def _ui(self) -> SkinManagerWidget | None:
        return cast("SkinManagerWidget | None", self._widget)

    # ── 皮肤库根目录（自带 + 可选额外目录）──────────────────────
    def _roots(self) -> list[Path]:
        roots = [BUILTIN_SKINS_DIR]
        configured = str(self.other_info.skins_dir or "").strip()
        if configured:
            roots.append(Path(configured))
        return roots

    def _refresh_choices(self) -> None:
        """重新扫描皮肤目录并刷新配置类上的 ChoiceConfig 选项。

        与 clipboard_replay 的自动注册一致：扫描发生在模块导入时，
        这里额外支持用户在设置页改了「额外皮肤库目录」后立即刷新。
        """
        choices = discover_choices(self.other_info.skins_dir or None)
        register_skins(SkinManagerConfig, choices)
        # 已实例化的配置对象持有自己的 _fields，需同步替换
        if self.other_info is not None:
            fields = self.other_info._fields
            if "skin" in fields:
                fields["skin"] = getattr(SkinManagerConfig, "skin")
        if self._applied is not None and self._applied not in dict(choices):
            self._applied = None

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
        widget = self._ui
        if widget is not None:
            # 插件工作线程 -> GUI 线程
            self.run_on_gui(widget.set_status, text)

    def _on_apply_requested(self) -> None:
        """界面上「重新应用」按钮：强制重发一次当前皮肤。"""
        self._apply(str(self.other_info.skin or ""), force=True)

    # ── 生命周期 ─────────────────────────────────────────────────
    def on_initialized(self) -> None:
        self.config_changed.connect(
            self._on_config_changed, Qt.ConnectionType.QueuedConnection)
        self._refresh_choices()
        if self.other_info.auto_apply and self.other_info.skin:
            # 稍等主进程 ZMQ 就绪后自动应用上次选择
            from PySide6.QtCore import QTimer
            QTimer.singleShot(
                1500,
                lambda: self._apply(str(self.other_info.skin), force=True),
            )

    def _on_config_changed(self, name: str, value) -> None:
        if name == "skins_dir":
            self._refresh_choices()
            # 目录变了，若当前皮肤已不在列表里则还原默认
            choices = dict(discover_choices(str(value or "").strip() or None))
            current = str(self.other_info.skin or "")
            if current and current not in choices:
                self._apply("", force=True)
        elif name == "skin":
            self._apply(str(value or ""))

    def on_shutdown(self) -> None:
        # 插件关闭时还原主进程内存皮肤（主进程退出本身也会自动还原）
        try:
            self.request(SetSkinCommand(reset=True), timeout=2.0)
        except Exception:
            pass
