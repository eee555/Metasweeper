from __future__ import annotations

import copy
import queue
import threading
import time
import uuid
from typing import Callable
from urllib.parse import urlparse

import zmq

from lib_zmq_plugins.serializer import Serializer
from lib_zmq_plugins.shared.base import (
    BaseCommand, BaseQuery, BaseQueryResult, CommandResponse, peek_struct_tag,
)
from shared_types.queries import QUERY_RESULT_TYPES, QUERY_TYPES

from .mcp_server import MAX_CONNECTIONS, PendingCall, RequestBridge


# 255×255 自定义棋盘的 JSON 快照约 260 KB，原 64 KiB 上限会让 libzmq 直接断开
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class CommandNotSentError(TimeoutError):
    send_state = "not_sent"


class CommandIO:
    def __init__(self, endpoint: str, authorize: Callable[[BaseCommand], bool],
                 execute: Callable[[str, dict], dict]):
        parsed = urlparse(endpoint)
        if parsed.scheme == "tcp" and parsed.hostname and parsed.port and parsed.port <= 65533:
            host = parsed.hostname
            if ":" in host:
                host = f"[{host}]"
            self.endpoint = f"tcp://{host}:{parsed.port + 2}"
        elif parsed.scheme == "ipc" and parsed.path:
            self.endpoint = f"ipc://{parsed.path}_ctrl"
        else:
            raise ValueError("Unsupported SDK endpoint")
        self.authorize = authorize
        self.execute = execute
        self.queue: queue.Queue[PendingCall] = queue.Queue(MAX_CONNECTIONS)
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.error: Exception | None = None
        self.active: PendingCall | None = None
        self.thread = threading.Thread(
            target=self._run, name="metasweeper-mcp-io", daemon=True)
        self._context = None
        self._socket = None
        self._serializer = Serializer()
        self._serializer.register_query_types(*QUERY_TYPES)
        self._serializer.register_query_result_types(*QUERY_RESULT_TYPES)

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(1) or self.error is not None:
            self.stop()
            raise RuntimeError("Private command transport could not start")

    def submit(self, call: PendingCall) -> None:
        with self.lock:
            if self.stopped.is_set():
                raise RuntimeError("Command transport stopped")
            self.queue.put_nowait(call)

    def stop(self) -> None:
        with self.lock:
            self.stopped.set()
            if self.active is not None:
                RequestBridge._cancel(
                    self.active, "Service stopped; do not retry automatically")
            while True:
                try:
                    call = self.queue.get_nowait()
                except queue.Empty:
                    break
                RequestBridge._cancel(
                    call, "Service stopped; do not retry automatically")
        if self.thread.ident is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=1)

    def _open_socket(self) -> None:
        self._socket = self._context.socket(zmq.DEALER)
        for option, value in ((zmq.LINGER, 0), (zmq.SNDHWM, MAX_CONNECTIONS),
                              (zmq.RCVHWM, MAX_CONNECTIONS), (zmq.MAXMSGSIZE,
                                                              MAX_RESPONSE_BYTES),
                              (zmq.IMMEDIATE, 1), (zmq.SNDTIMEO, 0), (zmq.RCVTIMEO, 0)):
            self._socket.setsockopt(option, value)
        self._socket.connect(self.endpoint)

    def _close_socket(self) -> None:
        if self._socket is not None:
            self._socket.close(linger=0)
            self._socket = None

    def report_progress(self, result: dict) -> None:
        call = self.active
        if call is None or threading.current_thread() is not self.thread:
            raise RuntimeError("Progress must be reported by the active I/O owner")
        with call.lock:
            if call.future.done() or self.stopped.is_set() or time.monotonic() >= call.deadline:
                raise TimeoutError("Batch cancelled or expired")
            call.progress = copy.deepcopy(result)

    def _run(self) -> None:
        try:
            self._context = zmq.Context()
            self._open_socket()
            self.ready.set()
            while not self.stopped.is_set():
                try:
                    call = self.queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                with self.lock:
                    if self.stopped.is_set():
                        RequestBridge._cancel(call, "Service stopped")
                        continue
                    self.active = call
                RequestBridge.execute(call, self.execute)
                with self.lock:
                    self.active = None
        except Exception as error:
            self.error = error
        finally:
            self.ready.set()
            self.stop()
            self._close_socket()
            if self._context is not None:
                self._context.term()
                self._context = None

    def _exchange(self, payload: bytes, request_id: str, timeout: float,
                  pre_send: Callable[[], object] | None = None) -> bytes:
        """在 I/O owner 线程发送并等待匹配的响应帧"""
        if threading.current_thread() is not self.thread:
            raise RuntimeError(
                "Transport calls must run on the private I/O owner")
        call = self.active
        if call is None:
            raise RuntimeError("No active tool request")
        deadline = min(call.deadline, time.monotonic() + timeout)
        if self._socket is None:
            self._open_socket()
        while time.monotonic() < deadline:
            if self.stopped.is_set() or call.future.done():
                raise TimeoutError("Request cancelled")
            if self._socket.poll(50, zmq.POLLOUT):
                with call.lock:
                    if (self.stopped.is_set() or call.future.done()
                            or time.monotonic() >= deadline):
                        raise TimeoutError("Request cancelled")
                    blocked = pre_send() if pre_send is not None else None
                    if blocked is not None:
                        return b"__blocked__"
                    try:
                        self._socket.send(payload, flags=zmq.NOBLOCK)
                    except zmq.Again as error:
                        raise CommandNotSentError("Transport backpressure; command not sent") from error
                    if pre_send is not None and call.progress is not None:
                        progress = call.progress
                        index = progress["completed"]
                        click = call.arguments["clicks"][index]
                        error = "Click sent without confirmation; do not retry automatically"
                        progress["results"].append({
                            "index": index, **click, "button": click.get("button", "left"),
                            "success": False, "outcome": "unknown", "error": error})
                        progress.update(success=False, outcome="unknown", error=error,
                                        stopped_index=index, unattempted=progress["requested"] - index - 1)
                break
        else:
            raise CommandNotSentError("Transport unavailable")
        while time.monotonic() < deadline:
            if self.stopped.is_set() or call.future.done():
                raise TimeoutError("Request cancelled")
            if not self._socket.poll(50, zmq.POLLIN):
                continue
            message = self._socket.recv_multipart(flags=zmq.NOBLOCK)
            if len(message) not in (1, 2) or (len(message) == 2 and message[0] != b""):
                raise ValueError("Invalid response framing")
            raw = message[-1]
            try:
                if self._serializer.is_query_result_tag(peek_struct_tag(raw)):
                    response = self._serializer.decode_query_result(raw)
                else:
                    response = self._serializer.decode_response(raw)
                response_id = response.request_id
            except Exception:
                continue
            with call.lock:
                if (response_id == request_id
                        and time.monotonic() < deadline and not call.future.done()
                        and not self.stopped.is_set()):
                    if (pre_send is not None and call.progress is not None
                            and isinstance(response, CommandResponse)):
                        progress = call.progress
                        entry = progress["results"][-1]
                        entry.update(success=response.success,
                                     outcome="confirmed" if response.success else "not_executed",
                                     request_id=response.request_id)
                        if response.success:
                            entry.pop("error", None)
                            progress.pop("error", None)
                            progress["completed"] += 1
                            complete = progress["completed"] == progress["requested"]
                            progress.update(success=complete,
                                            outcome="confirmed" if complete else "partial",
                                            stopped_index=None if complete else len(progress["results"]))
                        else:
                            error = response.error or "Main process rejected command"
                            entry["error"] = progress["error"] = error
                            progress["outcome"] = "partial" if progress["completed"] else "not_executed"
                    return raw
        raise TimeoutError("Response timed out")

    def request(self, command: BaseCommand, timeout: float = 3.0) -> CommandResponse:
        command.request_id = uuid.uuid4().hex
        payload = self._serializer.encode_command(command)

        def check_authorization() -> CommandResponse | None:
            if self.authorize(command):
                return None
            return CommandResponse(request_id=command.request_id, success=False,
                                   error="Official SDK permission revoked")

        try:
            raw = self._exchange(payload, command.request_id,
                                 timeout, check_authorization)
            if raw == b"__blocked__":
                return CommandResponse(
                    request_id=command.request_id, success=False,
                    error="Official SDK permission revoked")
            return self._serializer.decode_response(raw)
        except Exception:
            if threading.current_thread() is self.thread:
                self._close_socket()
            raise

    def query(self, query: BaseQuery, timeout: float = 3.0) -> BaseQueryResult:
        """发送只读查询（不检查控制授权）"""
        query.request_id = uuid.uuid4().hex
        payload = self._serializer.encode_query(query)
        try:
            raw = self._exchange(payload, query.request_id, timeout)
            return self._serializer.decode_query_result(raw)
        except Exception:
            if threading.current_thread() is self.thread:
                self._close_socket()
            raise
