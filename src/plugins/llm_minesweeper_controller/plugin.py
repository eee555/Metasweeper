from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QWidget

from plugin_sdk import BasePlugin, PluginInfo, WindowMode, make_plugin_icon
from plugin_sdk.control_auth import ControlAuthorizationManager
from shared_types.commands import MouseClickCommand, NewGameCommand
from shared_types.events import BoardUpdateEvent, GameStatusChangeEvent

from .command_io import CommandIO
from .config import LlmMinesweeperControllerConfig, sanitize_legacy_configs, valid_port
from .tools import MinesweeperTools, TOOLS
from .mcp_server import McpServer, RequestBridge


class LlmMinesweeperControllerPlugin(BasePlugin[LlmMinesweeperControllerConfig]):
    service_state_changed = Signal(object)

    def __init__(self, info: PluginInfo):
        super().__init__(info)
        self._tools = MinesweeperTools(lambda command_type: False, self._request_control,
                                       self._request_query)
        self._io: CommandIO | None = None
        self._server: McpServer | None = None
        self._state = "stopped"
        self._config_error = ""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="元扫雷 MCP 服务", version="2.0.0",
            description="通过本机 MCP 服务提供可见棋盘和经授权的辅助操作",
            window_mode=WindowMode.TAB, icon=make_plugin_icon("#247F68", "M"),
            other_info=LlmMinesweeperControllerConfig,
            required_controls=[NewGameCommand, MouseClickCommand],
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(BoardUpdateEvent, self._on_board_update)
        self.subscribe(GameStatusChangeEvent, self._on_game_status_change)

    def _create_widget(self) -> QWidget | None:
        try:
            from .widgets import McpControlWidget
        except ImportError:
            self.logger.warning("McpControlWidget 尚未就绪，MCP 服务保持停止")
            return None
        widget = McpControlWidget(parent=None)
        widget.set_port(self.other_info.port)
        widget.start_requested.connect(self.start_mcp, Qt.ConnectionType.QueuedConnection)
        widget.stop_requested.connect(self.stop_mcp, Qt.ConnectionType.QueuedConnection)
        self.service_state_changed.connect(widget.set_service_state, Qt.ConnectionType.QueuedConnection)
        self._widget = widget
        self._publish_state()
        return widget

    def on_initialized(self) -> None:
        try:
            sanitize_legacy_configs(self.data_dir)
            self.save_config()
        except Exception:
            self._config_error = "旧配置清理失败，MCP 服务保持停止"
            self._state = "error"
        self.config_changed.connect(self._on_settings_changed, Qt.ConnectionType.QueuedConnection)
        self._publish_state(self._config_error)

    def _publish_state(self, error: str = "") -> None:
        server = self._server
        running = server is not None and self._state == "running"
        endpoint = server.endpoint if server is not None and running else ""
        prompt = ""
        if server is not None and running:
            prompt = (
                "请在现有 agent 的 MCP 配置中添加一个 Streamable HTTP 服务，保留其他配置。\n"
                f"endpoint: {endpoint}\n"
                "协议版本：2025-11-25。使用客户端已有的 HTTP MCP 支持，不安装任何包，"
                "若客户端不支持 Streamable HTTP，明确报告不支持，不能改用 stdio。"
                "不启动子进程或新游戏，不自动玩游戏。连接后等待用户明确指令。"
                "只读取可见棋盘，控制需用户重新授权并开启主进程相应开关。"
                "click_cell 支持 clicks 数组批量点击（最多128项），也兼容 row/col/button 单点。"
                "批量按顺序逐项确认，首个失败即停止；先检查 completed/results/stopped_index。"
                "动作超时意味着结果未知，不得自动重试。"
            )
        self.service_state_changed.emit({
            "state": self._state, "port": server.port if server else self.other_info.port,
            "endpoint": endpoint, "prompt": prompt, "error": error,
        })

    @Slot(int)
    def start_mcp(self, port: int) -> None:
        if self._config_error:
            self._state = "error"
            self._publish_state(self._config_error)
            return
        if self._server is not None or self._io is not None:
            self._publish_state("服务已运行；更换端口前请先停止")
            return
        self._state = "starting"
        self._publish_state()
        owner = None
        bridge = None
        server = None
        try:
            if not valid_port(port):
                raise ValueError("Invalid MCP port")
            client = self.client
            if client is None:
                raise RuntimeError("官方 SDK client 尚未就绪")
            auth_manager = ControlAuthorizationManager.instance()
            plugin_name = self.name
            self._tools.has_auth = lambda command_type: auth_manager.is_authorized(command_type, plugin_name)
            owner = CommandIO(
                client.endpoint,
                lambda command: self._tools.has_auth(type(command)),
                self._tools.execute_function)
            self._tools.report_progress = owner.report_progress
            bridge = RequestBridge(owner.submit)
            server = McpServer(port, TOOLS, bridge)
            self._io = owner
            owner.start()
            server.start()
            self.other_info.port = port
            self.save_config()
        except Exception:
            if bridge is not None:
                bridge.stop()
            if server is not None:
                server.stop()
            if owner is not None:
                owner.stop()
            self._io = owner if owner is not None and owner.thread.is_alive() else None
            self._state = "error"
            self._publish_state("启动失败；请检查端口、SDK 连接及配置，不会自动重试")
            return
        self._server = server
        self._state = "running"
        self._publish_state()

    @Slot()
    def stop_mcp(self) -> None:
        self._state = "stopping"
        self._publish_state()
        server, self._server = self._server, None
        if server is not None:
            server.stop()
        owner = self._io
        if owner is not None:
            owner.stop()
        alive = owner is not None and owner.thread.is_alive()
        self._io = owner if alive else None
        self._state = "error" if alive else "stopped"
        self._publish_state("私有通信线程尚未退出，禁止重启" if alive else "")

    def _request_control(self, command, timeout: float):
        owner = self._io
        if owner is None:
            raise RuntimeError("Private command transport unavailable")
        return owner.request(command, timeout=timeout)

    def _request_query(self, query, timeout: float):
        """只读查询：不经过控制授权"""
        owner = self._io
        if owner is None:
            raise RuntimeError("Private query transport unavailable")
        return owner.query(query, timeout=timeout)

    @Slot(str, object)
    def _on_settings_changed(self, name: str, _value: object) -> None:
        if name == "port":
            self._publish_state()

    def _on_board_update(self, event: BoardUpdateEvent) -> None:
        self._tools.update_board(event)

    def _on_game_status_change(self, event: GameStatusChangeEvent) -> None:
        self._tools.update_status(event)

    def on_shutdown(self) -> None:
        self.stop_mcp()
