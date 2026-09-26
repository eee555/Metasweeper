"""
ZMQ Server 集成模块

提供将 ZMQ Server 集成到扫雷主进程的便捷方法

使用方式::

    # 初始化
    bridge = GameServerBridge.instance()

    # 注册指令处理器（在 start 之前）
    bridge.register_handler(NewGameCommand, my_handler)

    # 启动服务
    bridge.start()

    # 发送事件
    bridge.send_event(event)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeVar
import threading
from concurrent.futures import Future

from PySide6.QtCore import QObject, Signal, Qt

from lib_zmq_plugins.server.zmq_server import ZMQServer
from lib_zmq_plugins.shared.base import BaseEvent, BaseCommand, CommandResponse

from shared_types import EVENT_TYPES, COMMAND_TYPES

if TYPE_CHECKING:
    from lib_zmq_plugins.log import LogHandler

import loguru
logger = loguru.logger.bind(name="ServerBridge")

# 泛型：指令类型
_C = TypeVar("_C", bound=BaseCommand)
_E = TypeVar("_E", bound=BaseEvent)


class GameServerBridge(QObject):
    """
    游戏服务端桥接器（全局单例）

    只负责 ZMQ 通信层封装，不绑定任何业务逻辑。
    指令处理器由外部注册。

    处理器自动在主线程中执行（通过信号槽机制）。
    """

    # 内部信号：用于调度到主线程
    # (handler, cmd, future_or_none)
    _execute_signal = Signal(object, object, object)

    _instance: GameServerBridge | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = QObject.__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def instance(
        cls,
        endpoint: str | None = None,
        log_handler: LogHandler | None = None,
    ) -> GameServerBridge:
        """
        获取全局单例

        Args:
            endpoint: ZMQ端点地址
            log_handler: 日志处理器

        Returns:
            GameServerBridge 实例
        """
        if cls._instance is None:
            cls._instance = cls(endpoint, log_handler)
        return cls._instance

    def __init__(
        self,
        endpoint: str | None = None,
        log_handler: LogHandler | None = None,
    ):
        # 防止重复初始化
        if getattr(self, '_initialized', False):
            return

        super().__init__()

        # 默认端点
        if endpoint is None:
            endpoint = "tcp://127.0.0.1:5555"

        self._endpoint = endpoint
        self._server = ZMQServer(endpoint=endpoint, log_handler=log_handler)

        # 保存主线程引用
        self._main_thread = threading.main_thread()

        # 保存处理器
        self._handlers: dict[str, Callable] = {}

        # 连接内部信号
        self._execute_signal.connect(
            self._on_execute, Qt.QueuedConnection)  # type: ignore

        # 注册类型
        self._server.register_event_types(*EVENT_TYPES)
        self._server.register_command_types(*COMMAND_TYPES)

        self._initialized = True

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def server(self) -> ZMQServer:
        """获取底层 ZMQ Server 实例"""
        return self._server

    def _on_execute(
        self,
        handler: Callable,
        cmd: BaseCommand,
        future: Future | None,
    ) -> None:
        """在主线程执行处理器"""
        try:
            result = handler(cmd)
            if future is not None:
                future.set_result(result)
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            if future is not None:
                future.set_exception(e)

    def register_handler(
        self,
        command_type: type[_C],
        handler: Callable[[_C], CommandResponse],
    ) -> None:
        """
        注册指令处理器

        处理器会自动在主线程中执行。

        Args:
            command_type: 指令类型
            handler: 处理函数，接收指令，返回响应

        Usage::

            def handle_new_game(cmd: NewGameCommand) -> CommandResponse:
                # 处理逻辑（cmd 类型被正确推断）
                return CommandResponse(request_id=cmd.request_id, success=True)

            bridge.register_handler(NewGameCommand, handle_new_game)
        """
        # 获取 tag
        tag = command_type.__struct_config__.tag
        str_tag = str(tag)
        logger.info(f"注册处理器: tag={tag}, command_type={command_type.__name__}")

        # 保存 handler
        self._handlers[str_tag] = handler

        # 注册到 server
        def wrapped_handler(cmd: _C) -> CommandResponse | None:
            if cmd.request_id:
                # 同步请求：需要等待结果
                future: Future[CommandResponse] = Future()
                self._execute_signal.emit(handler, cmd, future)
                return future.result(timeout=5.0)
            else:
                # 异步命令：不等待结果
                self._execute_signal.emit(handler, cmd, None)
                return None

        self._server.register_handler(
            command_type, wrapped_handler)  # type: ignore
        logger.info(f"处理器已注册: tag={tag}")

    def start(self) -> None:
        """启动服务"""
        self._server.start()
        logger.info(f"Game server bridge started at {self._endpoint}")

    def stop(self) -> None:
        """停止服务"""
        self._server.stop()
        logger.info("Game server bridge stopped")

    def send_event(self, event: BaseEvent) -> None:
        """
        发送事件到客户端

        Args:
            event: 事件对象
        """
        if self._server._pub_socket is None:  # type: ignore[attr-defined]
            return  # 服务未启动，跳过（如命令行加载录像时）
        self._server.publish(event.__class__, event)
