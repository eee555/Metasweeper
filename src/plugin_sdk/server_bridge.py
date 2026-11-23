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

import os
from typing import TYPE_CHECKING, Callable, TypeVar
import threading
from concurrent.futures import Future
from uuid import uuid4

from msgspec.structs import replace
from PySide6.QtCore import QObject, Signal, Qt

from lib_zmq_plugins.server.zmq_server import ZMQServer
from lib_zmq_plugins.shared.base import (
    BaseCommand, BaseEvent, BaseQuery, BaseQueryResult, CommandResponse,
)

from shared_types import COMMAND_TYPES, EVENT_TYPES, QUERY_RESULT_TYPES, QUERY_TYPES
from shared_types.events import LanguageChangeEvent

if TYPE_CHECKING:
    from lib_zmq_plugins.log import LogHandler

import loguru
logger = loguru.logger.bind(name="ServerBridge")

# 泛型：指令类型
_C = TypeVar("_C", bound=BaseCommand)
_E = TypeVar("_E", bound=BaseEvent)
_Q = TypeVar("_Q", bound=BaseQuery)


def _safe_tag(cmd: BaseCommand) -> str:
    """取命令 tag 用于日志；非 msgspec 命令（如测试桩）时回退类名，绝不抛错。"""
    cfg = getattr(type(cmd), "__struct_config__", None)
    tag = getattr(cfg, "tag", None)
    return str(tag) if tag else type(cmd).__name__


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
        bind_to_random_port: bool = True,
    ):
        # 防止重复初始化
        if getattr(self, '_initialized', False):
            return

        super().__init__()

        # 默认端点（允许用环境变量覆盖 host 前缀）。随机端口模式下端口由
        # 系统分配，endpoint 仅提供 scheme + host，端口会被忽略。
        if endpoint is None:
            endpoint = os.environ.get(
                "METASWEEPER_ZMQ_ENDPOINT", "tcp://127.0.0.1")

        self._endpoint = endpoint
        self._server = ZMQServer(
            endpoint=endpoint,
            log_handler=log_handler,
            bind_to_random_port=bind_to_random_port,
        )

        # 保存主线程引用
        self._main_thread = threading.main_thread()

        # 保存处理器
        self._handlers: dict[str, Callable] = {}
        self._language_lock = threading.Lock()
        self._language_source_id = uuid4().hex
        self._language_revision = 0
        self._last_language_event: LanguageChangeEvent | None = None
        # 插件系统开关。关闭后 start() 不启动服务，send_event() 直接返回。
        self._enabled = True
        self._started = False

        # 连接内部信号
        self._execute_signal.connect(
            self._on_execute, Qt.ConnectionType.QueuedConnection)

        # 注册类型
        self._server.register_event_types(*EVENT_TYPES)
        self._server.register_command_types(*COMMAND_TYPES)
        self._server.register_query_types(*QUERY_TYPES)
        self._server.register_query_result_types(*QUERY_RESULT_TYPES)
        # 预先注册，主进程须在启动插件管理器之前缓存实际语言。
        self._server.register_snapshot_provider(
            LanguageChangeEvent, self._language_snapshot)

        self._initialized = True

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def pub_endpoint(self) -> str:
        """PUB 实际绑定的端点（随机端口由系统分配）。"""
        return self._server.pub_endpoint

    @property
    def ctrl_endpoint(self) -> str:
        """ROUTER/CTRL 实际绑定的端点（随机端口由系统分配）。"""
        return self._server.ctrl_endpoint

    @property
    def server(self) -> ZMQServer:
        """获取底层 ZMQ Server 实例"""
        return self._server

    @property
    def enabled(self) -> bool:
        """插件系统是否启用。"""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """启用或停用插件系统。

        停用只改变桥接器状态，不负责终止插件管理器进程；调用方还应停止
        已启动的服务与子进程。重新启用后可以再次调用 start()。
        """
        self._enabled = bool(enabled)

    def _on_execute(
        self,
        handler: Callable,
        cmd: BaseCommand,
        future: Future | None,
    ) -> None:
        """在主线程执行处理器。

        future 非 None 为同步请求（结果经 future 回传 I/O 线程）；
        future 为 None 为异步命令，调用方不阻塞、也不回传 CommandResponse。
        #26 兜底：异步命令没有 request_id，服务端不会回响应，失败原本被静默
        丢弃——这里把 handler 异常与 success=False 明确记录，便于排障。不新增
        request_id、不改帧格式/tag，避免把异步命令误判为同步阻塞请求。
        """
        try:
            result = handler(cmd)
            if future is not None:
                future.set_result(result)
            elif result is not None and getattr(result, "success", True) is False:
                logger.warning(
                    f"Async command failed (no response sent): tag={_safe_tag(cmd)}, "
                    f"error={getattr(result, 'error', None)!r}")
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            if future is not None:
                future.set_exception(e)
            else:
                logger.warning(
                    f"Async command raised (no response sent): "
                    f"tag={_safe_tag(cmd)}, error={e!r}")

    def register_query_handler(
        self,
        query_type: type[_Q],
        handler: Callable[[_Q], BaseQueryResult],
    ) -> None:
        """
        注册只读查询处理器（自动在主线程执行，不检查控制授权）

        Usage::

            def handle_board(query: GetBoardStateQuery) -> BoardStateResult:
                return BoardStateResult(cells=..., rows=...)

            bridge.register_query_handler(GetBoardStateQuery, handle_board)
        """

        def wrapped_handler(query: _Q) -> BaseQueryResult:
            future: Future[BaseQueryResult] = Future()
            self._execute_signal.emit(handler, query, future)
            return future.result(timeout=5.0)

        self._server.register_query_handler(query_type, wrapped_handler) # pyright: ignore[reportArgumentType]
        logger.info(
            f"查询处理器已注册: {query_type.__struct_config__.tag}")

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
        if not self._enabled:
            logger.info("Plugin system is disabled; server start skipped")
            return
        if self._started:
            return
        self._server.start()
        self._started = True
        logger.info(
            f"Game server bridge started: pub={self.pub_endpoint}, "
            f"ctrl={self.ctrl_endpoint}")

    def stop(self) -> None:
        """停止服务"""
        self._server.stop()
        self._started = False
        logger.info("Game server bridge stopped")

    def send_event(self, event: BaseEvent) -> None:
        """
        发送事件到客户端

        Args:
            event: 事件对象
        """
        if not self._enabled:
            return
        if isinstance(event, LanguageChangeEvent):
            # 缓存和发布在同一临界区内完成。快照返回独立副本，
            # 不让后续 publish 对 timestamp 的写入改变已取出的快照。
            with self._language_lock:
                self._language_revision += 1
                current = replace(event, source_id=self._language_source_id,
                                  revision=self._language_revision)
                self._last_language_event = current
                if self._server._pub_socket is not None:
                    self._server.publish(LanguageChangeEvent, current)
            return
        if self._server._pub_socket is None:  # type: ignore[attr-defined]
            return  # 服务未启动，跳过（如命令行加载录像时）
        self._server.publish(event.__class__, event)

    def _language_snapshot(self) -> LanguageChangeEvent:
        with self._language_lock:
            if self._last_language_event is None:
                raise RuntimeError("Language has not been synchronized yet")
            return replace(self._last_language_event)
