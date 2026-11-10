from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Empty, Full, Queue
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


@dataclass
class _Outgoing:
    payload: bytes
    deadline: float
    request_id: str = ""
    future: Future[Any] | None = None


class ZMQClient:
    """客户端。仅 I/O 线程创建、收发、订阅和关闭 ZMQ socket。"""

    _QUEUE_LIMIT = 1024
    _POLL_INTERVAL_MS = 20
    _SEND_TIMEOUT = 5.0
    _PROBE_INTERVAL = 1.0
    _CONNECTION_TIMEOUT = 12.0

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
        self._sync_deadlines: dict[str, float] = {}
        self._subscribers_lock = threading.Lock()
        self._subscription_revision = 0
        self._subscription_versions: dict[str, int] = {}
        self._active_versions: dict[str, int] = {}
        self._state_lock = threading.RLock()
        self._outgoing: Queue[_Outgoing] = Queue(self._QUEUE_LIMIT)
        self._deferred_send: _Outgoing | None = None
        self._active_topics: set[str] = set()
        self._snapshot_waiting: set[str] = set()
        self._accepting = False
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._last_activity = 0.0
        self._next_probe = 0.0

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
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                if self._accepting:
                    return
                raise RuntimeError("Client is still stopping")
            self._stopped.clear()
            self._ready.clear()
            self._startup_error = None
            self._accepting = True
            self._thread = threading.Thread(
                target=self._run, name="ZMQClientIO", daemon=True)
            self._thread.start()
        if not self._ready.wait(timeout=5.0):
            self.disconnect()
            raise TimeoutError("Client I/O initialization timed out")
        if self._startup_error is not None:
            self.disconnect()
            raise self._startup_error

    def disconnect(self) -> None:
        with self._state_lock:
            self._accepting = False
            self._stopped.set()
            thread = self._thread
        self._fail_pending(ConnectionError("Client disconnected"))
        if thread is threading.current_thread():
            return
        if thread:
            thread.join(timeout=3.0)
            if thread.is_alive():
                # 不跨线程强行关闭仍在使用的 socket。
                raise RuntimeError("Client I/O thread did not stop")
        with self._state_lock:
            if self._thread is thread:
                self._thread = None
            self._is_connected = False

    def _run(self) -> None:
        try:
            self._ctx = zmq.Context()
            self._create_sockets()
            self._ready.set()
            self._poll_loop()
        except BaseException as exc:
            if not self._ready.is_set():
                self._startup_error = exc
            else:
                self._log.error("Client I/O failed", exc_info=True)
        finally:
            with self._state_lock:
                self._accepting = False
                self._stopped.set()
            self._fail_pending(ConnectionError("Client I/O stopped"))
            self._discard_outgoing()
            self._close_sockets()
            if self._ctx is not None:
                self._ctx.term()
                self._ctx = None
            self._is_connected = False
            self._ready.set()

    def _create_sockets(self) -> None:
        if self._ctx is None:
            return
        self._sub_socket = self._ctx.socket(zmq.SUB)
        self._dealer_socket = self._ctx.socket(zmq.DEALER)
        if self._dealer_socket is None:
            return
        self._dealer_socket.setsockopt_string(zmq.IDENTITY, uuid.uuid4().hex)
        self._dealer_socket.setsockopt(zmq.IMMEDIATE, 1)
        self._dealer_socket.setsockopt(zmq.SNDTIMEO, 0)

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

        self._last_activity = time.monotonic()
        self._next_probe = 0.0
        self._update_subscriptions()

    def _close_sockets(self) -> None:
        if self._sub_socket:
            self._sub_socket.close(linger=0)
        if self._dealer_socket:
            self._dealer_socket.close(linger=0)
        self._sub_socket = None
        self._dealer_socket = None
        self._poller = None
        self._active_topics.clear()
        self._active_versions.clear()
        self._snapshot_waiting.clear()
        self._sync_topics.clear()
        self._sync_deadlines.clear()

    # ── 事件订阅 ──

    def subscribe(self, topic: type[BaseEvent], callback: Callable[[BaseEvent], None]) -> None:
        tag = get_event_tag(topic)
        with self._subscribers_lock:
            self._subscribers.setdefault(tag, []).append(callback)
            self._subscription_revision += 1
            self._subscription_versions[tag] = self._subscription_revision

    def unsubscribe(self, topic: type[BaseEvent]) -> None:
        tag = get_event_tag(topic)
        with self._subscribers_lock:
            self._subscribers.pop(tag, None)
            self._subscription_versions.pop(tag, None)

    def _update_subscriptions(self) -> None:
        if self._sub_socket is None:
            return
        with self._subscribers_lock:
            topics = set(self._subscribers)
            versions = dict(self._subscription_versions)
        for tag in self._active_topics - topics:
            self._sub_socket.setsockopt_string(zmq.UNSUBSCRIBE, tag)
            self._snapshot_waiting.discard(tag)
        for tag in topics - self._active_topics:
            self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, tag)
        for tag in topics:
            if versions[tag] != self._active_versions.get(tag):
                self._snapshot_waiting.add(tag)
        self._active_topics = topics
        self._active_versions = versions

    def _request_snapshot(self, topic: str) -> bool:
        """异步发送快照同步请求"""
        if self._dealer_socket is None:
            return False
        rid = uuid.uuid4().hex
        cmd = SyncCommand(request_id=rid, topic=topic)
        payload = self._serializer.encode_command(cmd)
        try:
            self._dealer_socket.send(payload, flags=zmq.NOBLOCK)
        except zmq.Again:
            return False
        self._sync_topics[rid] = topic
        self._sync_deadlines[rid] = time.monotonic() + self._SEND_TIMEOUT
        return True

    # ── 指令发送（可在任意线程调用） ──

    def send_command(self, cmd: BaseCommand) -> None:
        """非阻塞入队；队列已满时抛出 BufferError，异步命令不跨断线重放。"""
        payload = self._serializer.encode_command(cmd)
        self._enqueue(_Outgoing(payload, time.monotonic() + self._SEND_TIMEOUT))

    def _enqueue(self, item: _Outgoing) -> None:
        with self._state_lock:
            if not self._accepting or self._stopped.is_set():
                raise RuntimeError("Client is not connected")
            try:
                self._outgoing.put_nowait(item)
            except Full:
                raise BufferError("Client send queue is full") from None

    def _wait_for_response(
        self, payload: bytes, request_id: str,
        deadline: float, pending: dict[str, Any],
    ) -> Any:
        if threading.current_thread() is self._thread:
            raise RuntimeError("Cannot wait for a response on the client I/O thread")
        future: Future[Any] = Future()
        with self._state_lock:
            if not self._accepting or self._stopped.is_set():
                raise RuntimeError("Client is not connected")
            with self._pending_lock:
                pending[request_id] = future
            try:
                self._enqueue(_Outgoing(payload, deadline, request_id, future))
            except BaseException:
                with self._pending_lock:
                    pending.pop(request_id, None)
                raise
        try:
            return future.result(timeout=max(0.0, deadline - time.monotonic()))
        finally:
            with self._pending_lock:
                pending.pop(request_id, None)

    def request(
        self, cmd: BaseCommand, timeout: float = 5.0
    ) -> CommandResponse:
        deadline = time.monotonic() + timeout
        cmd.request_id = uuid.uuid4().hex
        payload = self._serializer.encode_command(cmd)
        return self._wait_for_response(
            payload, cmd.request_id, deadline, self._pending_requests)

    def query(
        self, query: BaseQuery, timeout: float = 5.0
    ) -> BaseQueryResult:
        """发送只读查询并等待强类型响应（不经过控制授权）"""
        deadline = time.monotonic() + timeout
        query.request_id = uuid.uuid4().hex
        payload = self._serializer.encode_query(query)
        return self._wait_for_response(
            payload, query.request_id, deadline, self._pending_queries)

    # ── 后台轮询 ──

    def _poll_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                if self._poller is None:
                    self._create_sockets()
                if self._poller is None:
                    raise RuntimeError("Client poller is not initialized")
                self._update_subscriptions()
                self._send_queued()
                now = time.monotonic()
                if now >= self._next_probe:
                    self._probe_connection()
                    self._next_probe = now + self._PROBE_INTERVAL
                if self._is_connected:
                    for topic in list(self._snapshot_waiting):
                        if self._request_snapshot(topic):
                            self._snapshot_waiting.discard(topic)
                for rid, deadline in list(self._sync_deadlines.items()):
                    if now >= deadline:
                        self._sync_deadlines.pop(rid, None)
                        self._sync_topics.pop(rid, None)
                events = self._poller.poll(timeout=self._POLL_INTERVAL_MS)
                for socket, _ in events:
                    if self._stopped.is_set():
                        break
                    if socket is self._sub_socket:
                        self._handle_sub_message()
                    elif socket is self._dealer_socket:
                        self._handle_dealer_message()
                        self._on_first_activity()
                if time.monotonic() - self._last_activity >= self._CONNECTION_TIMEOUT:
                    self._handle_reconnect(0.1)
            except zmq.ZMQError:
                self._log.warning("Client transport error", exc_info=True)
                self._handle_reconnect(0.1)

    def _send_queued(self) -> None:
        if self._dealer_socket is None:
            return
        for _ in range(64):
            item = self._deferred_send
            if item is None:
                try:
                    item = self._outgoing.get_nowait()
                except Empty:
                    return
            self._deferred_send = item
            # 与 enqueue/disconnect 采用一致的锁顺序。发送为 NOBLOCK，
            # 确保断开取消生效后，不会再发出先前已取出的队列项。
            with self._state_lock:
                if self._stopped.is_set():
                    return
                with self._pending_lock:
                    if item.future is not None:
                        active = (self._pending_requests.get(item.request_id) is item.future
                                  or self._pending_queries.get(item.request_id) is item.future)
                        if not active:
                            self._deferred_send = None
                            continue
                    if time.monotonic() >= item.deadline:
                        self._deferred_send = None
                        if item.future is None:
                            self._log.warning("Queued command expired before sending")
                        continue
                    try:
                        self._dealer_socket.send(item.payload, flags=zmq.NOBLOCK)
                    except zmq.Again:
                        return
                    self._deferred_send = None

    def _on_first_activity(self) -> None:
        """首次收到服务端数据时确认连接（防止虚假已连）"""
        self._last_activity = time.monotonic()
        if self._is_connected:
            return
        self._is_connected = True
        self._has_ever_connected = True
        self._log.info("Server connection confirmed (first activity)")
        self._notify_connection(self.on_connected)

    def _notify_connection(self, callback: Callable[[], Any] | None) -> None:
        if callback is not None:
            try:
                callback()
            except Exception:
                self._log.error("Connection callback error", exc_info=True)

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
            self._sync_deadlines.pop(resp.request_id, None)
            if topic:
                try:
                    snapshot = self._serializer.decode_event(resp.data)
                    self._notify_subscribers(topic, snapshot)
                except Exception:
                    self._log.warning(
                        "Failed to decode snapshot", exc_info=True)
        else:
            self._sync_topics.pop(resp.request_id, None)
            self._sync_deadlines.pop(resp.request_id, None)

        self._resolve_pending(resp)

    def _notify_subscribers(self, topic: str, event: BaseEvent) -> None:
        with self._subscribers_lock:
            callbacks = list(self._subscribers.get(topic, []))
        for cb in callbacks:
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

    def _fail_pending(self, error: Exception) -> None:
        with self._pending_lock:
            futures = list(self._pending_requests.values()) + list(self._pending_queries.values())
            self._pending_requests.clear()
            self._pending_queries.clear()
        for future in futures:
            if not future.done():
                future.set_exception(error)

    def _discard_outgoing(self) -> None:
        self._deferred_send = None
        while True:
            try:
                self._outgoing.get_nowait()
            except Empty:
                return

    def _handle_reconnect(self, backoff: float) -> None:
        was_connected = self._is_connected
        if was_connected:
            self._is_connected = False
            self._reconnect_count += 1
        # 已发送的命令执行状态可能未知，禁止恢复后自动重放。
        with self._state_lock:
            self._fail_pending(ConnectionError("Server connection lost"))
            self._discard_outgoing()
        self._close_sockets()
        if was_connected:
            self._notify_connection(self.on_disconnected)
        # 由下一轮统一重建；创建失败继续退避，绝不访问 None poller。
        self._stopped.wait(timeout=backoff)

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
