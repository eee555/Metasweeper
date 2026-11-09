from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future
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


class ZMQClient:
    """ZMQ 客户端，运行在插件管理器进程中"""

    def __init__(
        self,
        endpoint: str,
        on_connected: Callable[[], Any] | None = None,
        on_disconnected: Callable[[], Any] | None = None,
        log_handler: LogHandler | None = None,
        pub_endpoint: str | None = None,
        ctrl_endpoint: str | None = None,
    ) -> None:
        self._endpoint = endpoint
        derived_pub, derived_ctrl = _derive_endpoints(endpoint)
        # 显式端点优先（主进程随机端口模式通过命令行传入真实地址）；
        # 未提供时回退到旧的 base+1 / base+2 派生，兼容固定端口与测试。
        self._pub_endpoint = pub_endpoint or derived_pub
        self._ctrl_endpoint = ctrl_endpoint or derived_ctrl
        self._serializer = Serializer()
        self._serializer.register_command_types(SyncCommand)
        self._log: LogHandler = log_handler or NullHandler()

        self._subscribers: dict[str, list[Callable[[BaseEvent], None]]] = {}
        self._pending_requests: dict[str, Future[CommandResponse]] = {}
        self._pending_queries: dict[str, Future[BaseQueryResult]] = {}
        self._pending_lock = threading.Lock()
        self._sync_topics: dict[str, str] = {}  # request_id → topic

        self._ctx: zmq.Context | None = None
        self._sub_socket: zmq.Socket | None = None
        self._dealer_socket: zmq.Socket | None = None
        self._poller: zmq.Poller | None = None
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()

        self.on_connected: Callable[[], Any] | None = on_connected
        self.on_disconnected: Callable[[], Any] | None = on_disconnected

        # 连接状态追踪
        self._is_connected = False
        self._reconnect_count = 0
        self._has_ever_connected = False  # 是否曾经真正连接过服务端

    # ── 类型注册 ──

    def register_event_types(self, *types: type[BaseEvent]) -> None:
        self._serializer.register_event_types(*types)

    def register_command_types(self, *types: type[BaseCommand]) -> None:
        self._serializer.register_command_types(*types)

    def register_query_types(
            self, *types: type[BaseQuery],
            result_types: tuple[type[BaseQueryResult], ...] = ()) -> None:
        """注册查询请求类型；同时可注册响应用于解析"""
        self._serializer.register_query_types(*types)
        if result_types:
            self._serializer.register_query_result_types(*result_types)

    # ── 连接管理 ──

    def connect(self) -> None:
        self._stopped.clear()
        self._ctx = zmq.Context()
        self._create_sockets()

        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

        # 不在此处标记已连接 —— ZMQ connect 是非阻塞的，
        # 即使服务端不存在也不会报错。
        # 改为延迟确认：首次收到服务端响应 / 心跳成功后，
        # 由 _on_first_activity() 触发 on_connected。

        for topic in list(self._subscribers):
            self._request_snapshot(topic)

        # 启动后立即发一次心跳作为探测
        self._probe_connection()

    def disconnect(self) -> None:
        self._stopped.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._close_sockets()
        if self._ctx:
            self._ctx.term()
        self._ctx = None
        self._thread = None
        self._is_connected = False

    def _create_sockets(self) -> None:
        if self._ctx is None:
            return
        self._sub_socket = self._ctx.socket(zmq.SUB)
        self._dealer_socket = self._ctx.socket(zmq.DEALER)
        if self._dealer_socket is None:
            return
        self._dealer_socket.setsockopt_string(zmq.IDENTITY, uuid.uuid4().hex)

        # 启用 ZMQ 原生心跳，自动检测服务端断开
        # HEARTBEAT_IVL: 每 5 秒发送一次心跳
        # HEARTBEAT_TIMEOUT: 5 秒内没收到回复视为断连
        # HEARTBEAT_TTL: 心跳包存活时间
        self._dealer_socket.setsockopt(zmq.HEARTBEAT_IVL, 5000)
        self._dealer_socket.setsockopt(zmq.HEARTBEAT_TIMEOUT, 5000)
        self._dealer_socket.setsockopt(zmq.HEARTBEAT_TTL, 10000)
        if self._sub_socket is None:
            return
        self._sub_socket.connect(self._pub_endpoint)
        self._dealer_socket.connect(self._ctrl_endpoint)

        self._poller = zmq.Poller()
        self._poller.register(self._sub_socket, zmq.POLLIN)
        self._poller.register(self._dealer_socket, zmq.POLLIN)

        for topic in self._subscribers:
            self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)

    def _close_sockets(self) -> None:
        if self._sub_socket:
            self._sub_socket.close(linger=0)
        if self._dealer_socket:
            self._dealer_socket.close(linger=0)
        self._sub_socket = None
        self._dealer_socket = None
        self._poller = None

    # ── 事件订阅 ──

    def subscribe(self, topic: type[BaseEvent], callback: Callable[[BaseEvent], None]) -> None:
        tag = get_event_tag(topic)
        if tag not in self._subscribers:
            self._subscribers[tag] = []
        self._subscribers[tag].append(callback)
        if self._sub_socket:
            self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, tag)
            self._request_snapshot(tag)

    def unsubscribe(self, topic: type[BaseEvent]) -> None:
        tag = get_event_tag(topic)
        self._subscribers.pop(tag, None)
        if self._sub_socket:
            self._sub_socket.setsockopt_string(zmq.UNSUBSCRIBE, tag)

    def _request_snapshot(self, topic: str) -> None:
        """异步发送快照同步请求"""
        if self._dealer_socket is None:
            return
        rid = uuid.uuid4().hex
        self._sync_topics[rid] = topic
        cmd = SyncCommand(request_id=rid, topic=topic)
        payload = self._serializer.encode_command(cmd)
        try:
            self._dealer_socket.send(payload)
        except zmq.ZMQError:
            self._log.warning(
                "Failed to send sync request for topic: %s", topic)
            self._sync_topics.pop(rid, None)

    # ── 指令发送（可在任意线程调用） ──

    def send_command(self, cmd: BaseCommand) -> None:
        if self._dealer_socket is None:
            raise RuntimeError("Client is not connected")
        payload = self._serializer.encode_command(cmd)
        self._dealer_socket.send(payload)

    def request(
        self, cmd: BaseCommand, timeout: float = 5.0
    ) -> CommandResponse:
        if self._dealer_socket is None:
            raise RuntimeError("Client is not connected")
        cmd.request_id = uuid.uuid4().hex
        future: Future[CommandResponse] = Future()
        with self._pending_lock:
            self._pending_requests[cmd.request_id] = future
        payload = self._serializer.encode_command(cmd)
        self._dealer_socket.send(payload)
        return future.result(timeout=timeout)

    def query(
        self, query: BaseQuery, timeout: float = 5.0
    ) -> BaseQueryResult:
        """发送只读查询并等待强类型响应（不经过控制授权）"""
        if self._dealer_socket is None:
            raise RuntimeError("Client is not connected")
        query.request_id = uuid.uuid4().hex
        future: Future[BaseQueryResult] = Future()
        with self._pending_lock:
            self._pending_queries[query.request_id] = future
        payload = self._serializer.encode_query(query)
        self._dealer_socket.send(payload)
        return future.result(timeout=timeout)

    # ── 后台轮询 ──

    def _poll_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                events = self._poller.poll(timeout=200)  # type: ignore
            except zmq.ZMQError:
                self._handle_reconnect(0.1)
                continue

            if not events:
                continue

            for socket, _ in events:
                try:
                    if socket is self._sub_socket:
                        self._handle_sub_message()
                    elif socket is self._dealer_socket:
                        self._handle_dealer_message()
                    # 收到消息 = 服务端存活，确认连接
                    self._on_first_activity()
                except zmq.ZMQError as e:
                    self._log.warning("Socket error during recv: %s", e)
                    self._handle_reconnect(0.5)

    def _on_first_activity(self) -> None:
        """首次收到服务端数据时确认连接（防止虚假已连）"""
        if self._is_connected:
            return
        self._is_connected = True
        self._has_ever_connected = True
        self._log.info("Server connection confirmed (first activity)")
        if self.on_connected:
            self.on_connected()

    def _probe_connection(self) -> bool:
        """发送探测包测试服务端是否在线"""
        if self._dealer_socket is None:
            return False
        try:
            cmd = SyncCommand(request_id=uuid.uuid4().hex, topic="__probe__")
            payload = self._serializer.encode_command(cmd)
            self._dealer_socket.send(payload, flags=zmq.NOBLOCK)
            return True
        except (zmq.ZMQError, zmq.Again):
            return False

    def _handle_sub_message(self) -> None:
        try:
            msg = self._sub_socket.recv_multipart(zmq.NOBLOCK)  # type: ignore
        except zmq.Again:
            return
        if len(msg) < 2:
            return
        topic = msg[0].decode("utf-8", errors="replace")
        try:
            event = self._serializer.decode_event(msg[1])
        except Exception as e:
            self._log.warning(
                f"Failed to decode event for topic: {topic}, Exception: {e}",
                exc_info=True,
            )
            return
        self._notify_subscribers(topic, event)

    def _handle_dealer_message(self) -> None:
        try:
            msg = self._dealer_socket.recv_multipart(  # type: ignore
                zmq.NOBLOCK)
        except zmq.Again:
            return
        if len(msg) < 2:
            return
        payload = msg[1] if msg[0] == b"" else msg[-1]
        tag = peek_struct_tag(payload)
        if self._serializer.is_query_result_tag(tag):
            try:
                query_result = self._serializer.decode_query_result(payload)
            except Exception:
                self._log.warning(
                    "Failed to decode query result", exc_info=True)
                return
            self._resolve_query_result(query_result)
            return
        try:
            resp = self._serializer.decode_response(payload)
        except Exception:
            self._log.warning("Failed to decode response", exc_info=True)
            return

        if resp.request_id and resp.data and resp.success:
            topic = self._sync_topics.pop(resp.request_id, None)
            if topic:
                try:
                    snapshot = self._serializer.decode_event(resp.data)
                    self._notify_subscribers(topic, snapshot)
                except Exception:
                    self._log.warning(
                        "Failed to decode snapshot", exc_info=True)
        else:
            self._sync_topics.pop(resp.request_id, None)

        self._resolve_pending(resp)

    def _notify_subscribers(self, topic: str, event: BaseEvent) -> None:
        for cb in self._subscribers.get(topic, []):
            try:
                cb(event)
            except Exception:
                self._log.error("Subscriber callback error", exc_info=True)

    def _resolve_pending(self, resp: CommandResponse) -> None:
        with self._pending_lock:
            future = self._pending_requests.pop(resp.request_id, None)
        if future:
            future.set_result(resp)

    def _resolve_query_result(self, result: BaseQueryResult) -> None:
        with self._pending_lock:
            future = self._pending_queries.pop(result.request_id, None)
        if future:
            future.set_result(result)

    # ── 重连 ──

    def _handle_reconnect(self, backoff: float) -> None:
        was_connected = self._is_connected
        if was_connected:
            self._is_connected = False
            self._reconnect_count += 1
            if self.on_disconnected:
                self.on_disconnected()

        self._stopped.wait(timeout=backoff)
        if self._stopped.is_set():
            return

        self._close_sockets()
        try:
            self._create_sockets()
        except zmq.ZMQError:
            self._log.warning("Reconnect failed", exc_info=True)
            # 重连失败且之前是已连接状态，保持断开
            return

        for topic in self._subscribers:
            self._request_snapshot(topic)

        # 发送探测包，等待 _on_first_activity 确认
        self._probe_connection()

        # 注意：不在这里设置 _is_connected = True / 调用 on_connected()
        # 必须等到真正收到服务端响应后才确认

    @property
    def is_connected(self) -> bool:
        """当前连接状态"""
        return self._is_connected

    @property
    def reconnect_count(self) -> int:
        """重连次数"""
        return self._reconnect_count

    @property
    def endpoint(self) -> str:
        """当前端点地址"""
        return self._endpoint

    @property
    def pub_endpoint(self) -> str:
        """PUB 端点地址"""
        return self._pub_endpoint

    @property
    def ctrl_endpoint(self) -> str:
        """CTRL 端点地址"""
        return self._ctrl_endpoint
