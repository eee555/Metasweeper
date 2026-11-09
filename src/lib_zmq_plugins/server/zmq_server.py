from __future__ import annotations

import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

import zmq

from lib_zmq_plugins.log import LogHandler, NullHandler
from lib_zmq_plugins.serializer import Serializer
from lib_zmq_plugins.shared.base import (
    BaseCommand,
    BaseEvent,
    BaseQuery,
    BaseQueryResult,
    CommandResponse,
    SyncCommand,
    get_event_tag,
    get_struct_tag,
    peek_struct_tag,
)


def _derive_endpoints(base: str) -> tuple[str, str]:
    """根据基础 endpoint 派生 PUB 和 CTRL 地址"""
    parsed = urlparse(base)
    if parsed.scheme == "ipc":
        path = parsed.path
        return (
            f"ipc://{path}_pub",
            f"ipc://{path}_ctrl",
        )
    elif parsed.scheme == "tcp":
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 5555
        return (
            f"tcp://{host}:{port + 1}",
            f"tcp://{host}:{port + 2}",
        )
    else:
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")


def _extract_host_prefix(endpoint: str) -> str:
    """提取端点的 host 前缀（不含端口），用于随机端口绑定。

    - tcp://127.0.0.1:5555 -> tcp://127.0.0.1
    - tcp://127.0.0.1      -> tcp://127.0.0.1
    - tcp://[::1]:5555     -> tcp://[::1]（IPv6 字面量保留方括号）
    - ipc:///tmp/foo       -> ipc:///tmp/foo
    """
    parsed = urlparse(endpoint)
    if parsed.scheme == "tcp":
        host = parsed.hostname or "127.0.0.1"
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"tcp://{host}"
    if parsed.scheme == "ipc":
        return f"ipc://{parsed.path}"
    raise ValueError(f"Unsupported scheme for random port: {parsed.scheme}")


class ZMQServer:
    """ZMQ 服务端，运行在游戏主进程中"""

    def __init__(
        self,
        endpoint: str,
        log_handler: LogHandler | None = None,
        *,
        bind_to_random_port: bool = False,
        random_port_min: int = 20000,
        random_port_max: int = 60000,
    ) -> None:
        """
        Args:
            endpoint: 基准端点。固定模式下为完整地址（如 tcp://127.0.0.1:5555）；
                随机模式下只需提供 scheme + host，端口由系统分配。
            bind_to_random_port: 为真时 PUB / CTRL 各自向系统申请独立的空闲随机
                端口（默认关闭以保持库层兼容；主进程通过桥接器显式开启）。
            random_port_min/max: 随机端口的范围。
        """
        self._endpoint = endpoint
        self._pub_endpoint, self._ctrl_endpoint = _derive_endpoints(endpoint)
        self._bind_to_random_port = bind_to_random_port
        self._random_port_min = random_port_min
        self._random_port_max = random_port_max
        self._serializer = Serializer()
        self._serializer.register_command_types(SyncCommand)
        self._handlers: dict[str, Callable[[
            BaseCommand], CommandResponse | None]] = {}
        self._query_handlers: dict[str, Callable[[
            BaseQuery], BaseQueryResult]] = {}
        self._snapshot_providers: dict[str, Callable[[], BaseEvent]] = {}
        self._log: LogHandler = log_handler or NullHandler()

        self._ctx: zmq.Context | None = None
        self._pub_socket: zmq.Socket | None = None
        self._router_socket: zmq.Socket | None = None
        self._poller: zmq.Poller | None = None
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()

    # ── 类型注册 ──

    def register_event_types(self, *types: type[BaseEvent]) -> None:
        self._serializer.register_event_types(*types)

    def register_command_types(self, *types: type[BaseCommand]) -> None:
        self._serializer.register_command_types(*types)

    def register_query_types(self, *types: type[BaseQuery]) -> None:
        self._serializer.register_query_types(*types)

    def register_query_result_types(self, *types: type[BaseQueryResult]) -> None:
        self._serializer.register_query_result_types(*types)

    # ── Handler / Snapshot 注册 ──

    def register_handler(
        self,
        command_type: type[BaseCommand],
        handler: Callable[[BaseCommand], CommandResponse | None],
    ) -> None:
        tag = command_type.__struct_config__.tag
        if isinstance(tag, type):
            tag = tag.__name__
        self._handlers[str(tag)] = handler

    def register_query_handler(
        self,
        query_type: type[BaseQuery],
        handler: Callable[[BaseQuery], BaseQueryResult],
    ) -> None:
        """注册只读查询处理器（不经过控制授权）"""
        self._query_handlers[get_struct_tag(query_type)] = handler

    def register_snapshot_provider(
        self, topic: type[BaseEvent], provider: Callable[[], BaseEvent]
    ) -> None:
        self._snapshot_providers[get_event_tag(topic)] = provider

    # ── 属性 ──

    @property
    def endpoint(self) -> str:
        """基准端点。随机端口模式下该值不用于连接，请用 pub/ctrl_endpoint。"""
        return self._endpoint

    @property
    def pub_endpoint(self) -> str:
        """PUB 实际绑定的端点（随机端口模式下由系统分配）。"""
        return self._pub_endpoint

    @property
    def ctrl_endpoint(self) -> str:
        """ROUTER/CTRL 实际绑定的端点（随机端口模式下由系统分配）。"""
        return self._ctrl_endpoint

    # ── 随机端口绑定 ──

    def _bind_random_ports(self) -> None:
        """PUB / ROUTER 各自独立向系统申请空闲随机端口并绑定。

        「全随机」：两个 socket 互不依赖，不要求端口连续，也不会伪造一个
        可供 +1/+2 派生的基准端点。调用方必须通过 pub_endpoint /
        ctrl_endpoint 把真实地址显式传给客户端（命令行参数）。
        """
        prefix = _extract_host_prefix(self._endpoint)
        if self._pub_socket is None or self._router_socket is None:
            raise RuntimeError("Sockets are not initialized")

        # 两个端口各自交给 ZMQ 挑选，避免自行探测带来的 TOCTOU 竞态。
        pub_port = self._pub_socket.bind_to_random_port(
            prefix, min_port=self._random_port_min,
            max_port=self._random_port_max, max_tries=100)
        ctrl_port = self._router_socket.bind_to_random_port(
            prefix, min_port=self._random_port_min,
            max_port=self._random_port_max, max_tries=100)

        self._pub_endpoint = f"{prefix}:{pub_port}"
        self._ctrl_endpoint = f"{prefix}:{ctrl_port}"

    # ── 生命周期 ──

    def start(self) -> None:
        self._stopped.clear()
        self._ctx = zmq.Context()
        self._pub_socket = self._ctx.socket(zmq.PUB)
        self._router_socket = self._ctx.socket(zmq.ROUTER)
        if self._pub_socket is None or self._router_socket is None:
            raise RuntimeError("Failed to create socket")
        # 启用 ZMQ 原生心跳，与客户端匹配
        # HEARTBEAT_IVL: 每 5 秒发送心跳
        # HEARTBEAT_TIMEOUT: 5 秒内没收到回复视为断连
        # HEARTBEAT_TTL: 心跳包存活时间
        self._router_socket.setsockopt(zmq.HEARTBEAT_IVL, 5000)
        self._router_socket.setsockopt(zmq.HEARTBEAT_TIMEOUT, 5000)
        self._router_socket.setsockopt(zmq.HEARTBEAT_TTL, 10000)

        self._poller = zmq.Poller()

        if self._bind_to_random_port:
            self._bind_random_ports()
        else:
            self._pub_socket.bind(self._pub_endpoint)
            self._router_socket.bind(self._ctrl_endpoint)

        self._poller.register(self._router_socket, zmq.POLLIN)

        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

        self._log.info("Server started: endpoint=%s, pub=%s, ctrl=%s",
                       self._endpoint, self._pub_endpoint, self._ctrl_endpoint)

    def stop(self) -> None:
        self._stopped.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._pub_socket:
            self._pub_socket.close(linger=0)
        if self._router_socket:
            self._router_socket.close(linger=0)
        if self._ctx:
            self._ctx.term()
        self._pub_socket = None
        self._router_socket = None
        self._ctx = None
        self._poller = None
        self._thread = None

    # ── 事件发布（可在任意线程调用） ──

    def publish(self, topic: type[BaseEvent], event: BaseEvent) -> None:
        if self._pub_socket is None:
            raise RuntimeError("Server is not started")
        tag = get_event_tag(topic)
        event.timestamp = time.time()
        payload = self._serializer.encode_event(event)
        self._pub_socket.send_multipart([tag.encode("utf-8"), payload])

    # ── 后台轮询 ──

    def _poll_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                events = self._poller.poll(timeout=100)  # type: ignore
            except zmq.ZMQError:
                break

            for socket, _ in events:
                if socket is self._router_socket:
                    try:
                        msg = self._router_socket.recv_multipart(  # type: ignore
                            zmq.NOBLOCK)
                    except zmq.Again:
                        continue
                    if len(msg) < 2:
                        continue
                    client_id = msg[0]
                    payload = msg[1]
                    tag = peek_struct_tag(payload)
                    if self._serializer.is_query_tag(tag):
                        try:
                            query = self._serializer.decode_query(payload)
                        except Exception:
                            self._log.warning(
                                "Failed to decode query", exc_info=True)
                            continue
                        self._dispatch_query(client_id, query)
                        continue
                    try:
                        cmd = self._serializer.decode_command(payload)
                    except Exception:
                        self._log.warning(
                            "Failed to decode command", exc_info=True)
                        continue
                    self._dispatch(client_id, cmd)

    def _dispatch(self, client_id: bytes, cmd: BaseCommand) -> None:
        tag = cmd.__struct_config__.tag
        if isinstance(tag, type):
            tag = tag.__name__
        tag = str(tag)

        self._log.info("[Server] 收到命令: tag=%s, request_id=%s",
                       tag, cmd.request_id)

        if tag == "__sync__":
            self._handle_sync(client_id, cmd)  # type: ignore
            return

        handler = self._handlers.get(tag)
        if handler is None:
            self._log.warning("No handler for command: %s", tag)
            return

        try:
            result = handler(cmd)
            self._log.info(
                "[Server] handler 执行完成: tag=%s, result=%s", tag, result)
        except Exception as e:
            self._log.error("Handler error for %s: %s", tag, e, exc_info=True)
            if cmd.request_id:
                resp = CommandResponse(
                    request_id=cmd.request_id, success=False, error=str(e)
                )
                self._send_to_client(client_id, resp)
            return

        if result is not None and cmd.request_id:
            self._send_to_client(client_id, result)

    def _dispatch_query(self, client_id: bytes, query: BaseQuery) -> None:
        """分发只读查询，不检查控制授权"""
        tag = get_struct_tag(query)
        self._log.info("[Server] 收到查询: tag=%s", tag)
        handler = self._query_handlers.get(tag)
        if handler is None:
            result: BaseQueryResult = BaseQueryResult(
                request_id=query.request_id, success=False,
                error=f"No handler for query: {tag}")
        else:
            try:
                result = handler(query)
            except Exception as e:
                self._log.error(
                    "Query handler error for %s: %s", tag, e, exc_info=True)
                result = BaseQueryResult(
                    request_id=query.request_id, success=False, error=str(e))
        if query.request_id:
            self._send_query_result(client_id, result)

    def _send_query_result(self, client_id: bytes, result: BaseQueryResult) -> None:
        if self._router_socket is None:
            return
        try:
            payload = self._serializer.encode_query_result(result)
            self._router_socket.send_multipart(
                [client_id, b"", payload], flags=zmq.NOBLOCK)
        except zmq.ZMQError:
            self._log.warning("Failed to send query result", exc_info=True)

    def _handle_sync(self, client_id: bytes, cmd: SyncCommand) -> None:
        topic = cmd.topic
        provider = self._snapshot_providers.get(topic)
        if provider is None:
            resp = CommandResponse(
                request_id=cmd.request_id,
                success=False,
                error=f"No snapshot provider for topic: {topic}",
            )
        else:
            try:
                snapshot = provider()
                payload = self._serializer.encode_event(snapshot)
                resp = CommandResponse(
                    request_id=cmd.request_id, success=True, data=payload
                )
            except Exception as e:
                self._log.error(
                    "Snapshot provider error for %s: %s", topic, e, exc_info=True)
                resp = CommandResponse(
                    request_id=cmd.request_id, success=False, error=str(e)
                )
        self._send_to_client(client_id, resp)

    def _send_to_client(self, client_id: bytes, resp: CommandResponse) -> None:
        if self._router_socket is None:
            return
        try:
            self._router_socket.send_multipart(
                [client_id, b"", self._serializer.encode_response(resp)]
            )
        except zmq.ZMQError:
            self._log.warning(
                "Failed to send response to client", exc_info=True)
