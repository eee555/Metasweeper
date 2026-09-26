"""
{plugin_name} - {description}

带控制权限的插件示例。
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal

from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from shared_types.events import VideoSaveEvent
from shared_types.commands import NewGameCommand


class {PluginName}Widget(QWidget):
    """插件 UI"""

    _update_signal = Signal(str)
    _auth_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._status = QLabel("控制权限: 未知")
        layout.addWidget(self._status)

        self._btn_new_game = QPushButton("开始新游戏")
        self._btn_new_game.clicked.connect(self._on_new_game_click)
        layout.addWidget(self._btn_new_game)

        self._update_signal.connect(self._on_update)
        self._auth_signal.connect(self._on_auth)

    def _on_update(self, text: str):
        self._status.setText(text)

    def _on_auth(self, granted: bool):
        self._status.setText(f"控制权限: {'已授权' if granted else '未授权'}")
        self._btn_new_game.setEnabled(granted)

    def _on_new_game_click(self):
        # 由插件类处理
        pass


class {PluginName}(BasePlugin):
    """{description}"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="{plugin_name}",
            version="1.0.0",
            description="{description}",
            window_mode=WindowMode.TAB,
            icon=make_plugin_icon("#FF5722", "G"),
            required_controls=[NewGameCommand],  # 声明需要的控制权限
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget | None:
        self._widget = {PluginName}Widget()
        # 连接按钮点击
        self._widget._btn_new_game.clicked.connect(self._start_new_game)
        return self._widget

    def on_initialized(self) -> None:
        self.logger.info("{PluginName} 已初始化")

        # 检查控制权限
        has_auth = self.has_control_auth(NewGameCommand)
        self._widget._auth_signal.emit(has_auth)

    def on_control_auth_changed(self, cmd_type, granted: bool):
        """控制权限变更回调"""
        if cmd_type == NewGameCommand:
            self.logger.info(f"权限变更: {granted}")
            self._widget._auth_signal.emit(granted)

    def _start_new_game(self):
        """开始新游戏"""
        if self.has_control_auth(NewGameCommand):
            self.send_command(NewGameCommand(rows=16, cols=30, mines=99))
            self.logger.info("已发送 NewGameCommand")
        else:
            self.logger.warning("没有控制权限")

    def _on_video_save(self, event: VideoSaveEvent):
        self._widget._update_signal.emit(f"用时: {event.rtime:.2f}s")
