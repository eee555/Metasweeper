"""第二轮 ZMQ 传输层定点补测的共享 fake 组件与数据类型。

约定：全部为纯内存对象 —— 不创建真实 ZMQ Context / Socket / Poller，
不启动真实 OS 线程，不绑定端口，不 fork 进程。所有 fixture 在测试文件内
局部定义，本模块只提供可复用的构造块。
"""
from __future__ import annotations

import threading as _threading
from types import SimpleNamespace

import msgspec

from lib_zmq_plugins.shared.base import (
    BaseCommand, BaseEvent, BaseQuery, BaseQueryResult,
)


# ── 带 tag 的强类型消息（用于走真实 Serializer 编解码） ──

class CovEvent(BaseEvent, tag="covz.evt"):
    value: int = 0


class CovCommand(BaseCommand, tag="covz.cmd"):
    value: int = 0


class CovQuery(BaseQuery, tag="covz.query"):
    value: int = 0


class CovResult(BaseQueryResult, tag="covz.result"):
    value: int = 0


class TagAsType:
    """__struct_config__.tag 是一个 type，用于覆盖 `tag = tag.__name__` 分支。"""
    __struct_config__ = SimpleNamespace(tag=ValueError)


def encode(obj: object) -> bytes:
    return msgspec.msgpack.encode(obj)


def tagged(tag: str, **fields: object) -> bytes:
    """构造带 type 标记但字段类型错误的 msgpack 负载，用于触发解码异常。"""
    return msgspec.msgpack.encode({"type": tag, **fields})


# ── 记录型日志处理器 ──

class RecLog:
    def __init__(self) -> None:
        self.records: list[tuple[str, object, tuple, dict]] = []

    def _add(self, level: str, msg: object, args: tuple, kwargs: dict) -> None:
        self.records.append((level, msg, args, kwargs))

    def debug(self, msg: str, /, *args: object, **kwargs: object) -> None:
        self._add("debug", msg, args, kwargs)

    def info(self, msg: str, /, *args: object, **kwargs: object) -> None:
        self._add("info", msg, args, kwargs)

    def warning(self, msg: str, /, *args: object, **kwargs: object) -> None:
        self._add("warning", msg, args, kwargs)

    def error(self, msg: str, /, *args: object, **kwargs: object) -> None:
        self._add("error", msg, args, kwargs)

    def levels(self) -> list[str]:
        return [r[0] for r in self.records]

    def messages(self) -> list[str]:
        return [str(r[1]) for r in self.records]


# ── 假 socket ──

class FakeSocket:
    def __init__(self, name: str = "sock", log: list | None = None) -> None:
        self.name = name
        self.log = log if log is not None else []
        self.closed = False
        self.close_linger: object = None
        self.send_error: BaseException | None = None
        self.send_multipart_error: BaseException | None = None
        self.recv_error: BaseException | None = None
        self.recv_messages: list = []
        self.bound: list = []
        self.connected: list = []
        self.random_ports: list = []

    def _rec(self, *args: object) -> None:
        self.log.append((self.name,) + args)

    def setsockopt_string(self, opt: object, value: object) -> None:
        self._rec("setsockopt_string", opt, value)

    def setsockopt(self, opt: object, value: object) -> None:
        self._rec("setsockopt", opt, value)

    def connect(self, endpoint: str) -> None:
        self._rec("connect", endpoint)
        self.connected.append(endpoint)

    def bind(self, endpoint: str) -> None:
        self._rec("bind", endpoint)
        self.bound.append(endpoint)

    def bind_to_random_port(
        self, prefix: str, min_port: int = 0, max_port: int = 0,
        max_tries: int = 100,
    ) -> int:
        self._rec("bind_to_random_port", prefix, min_port, max_port, max_tries)
        return self.random_ports.pop(0) if self.random_ports else 0

    def send(self, payload: bytes, flags: int = 0) -> None:
        self._rec("send", payload, flags)
        if self.send_error is not None:
            raise self.send_error

    def send_multipart(self, parts: list, flags: int = 0) -> None:
        self._rec("send_multipart", parts, flags)
        if self.send_multipart_error is not None:
            raise self.send_multipart_error

    def recv_multipart(self, flags: int = 0) -> list:
        self._rec("recv_multipart", flags)
        if self.recv_messages:
            msg = self.recv_messages.pop(0)
            if isinstance(msg, BaseException):
                raise msg
            return msg
        if self.recv_error is not None:
            raise self.recv_error
        return []

    def close(self, linger: int = 0) -> None:
        self._rec("close", linger)
        self.closed = True
        self.close_linger = linger


# ── 假 Poller ──

class FakePoller:
    """results 中每项可以是事件列表、异常实例，或返回列表/None 的 callable。

    stop_event: results 耗尽时自动 set()，让被驱动的轮询循环能自然退出，
    避免纯内存测试陷入无限循环。
    """

    def __init__(
        self, results: list | None = None, default: list | None = None,
        stop_event=None,
    ) -> None:
        self.results = list(results or [])
        self.default = default if default is not None else []
        self.stop_event = stop_event
        self.registered: list = []
        self.poll_calls: list = []
        self.exhausted = False

    def register(self, socket: object, flags: object) -> None:
        self.registered.append((socket, flags))

    def poll(self, timeout: object) -> list:
        self.poll_calls.append(timeout)
        if self.results:
            item = self.results.pop(0)
            if not self.results and self.stop_event is not None:
                self.stop_event.set()
        else:
            self.exhausted = True
            if self.stop_event is not None:
                self.stop_event.set()
            item = self.default
        if callable(item):
            value = item()
            return value if value is not None else []
        if isinstance(item, BaseException):
            raise item
        return item


# ── 假 Context ──

class FakeContext:
    def __init__(self, socket_map: dict | None = None, log: list | None = None) -> None:
        self.socket_map = socket_map or {}
        self.created: list = []
        self.terminated = False
        self.log = log if log is not None else []

    def socket(self, socket_type: int, **kwargs: object) -> object:
        value = self.socket_map.get(socket_type, "AUTO")
        if value == "AUTO":
            value = FakeSocket(name=f"sock-{socket_type}", log=self.log)
        elif callable(value) and not isinstance(value, FakeSocket):
            value = value()
        self.created.append((socket_type, value))
        return value

    def term(self) -> None:
        self.terminated = True
        self.log.append(("ctx", "term"))


# ── 假线程（不创建 OS 线程） ──

class InlineThread:
    """start() 在当前调用线程同步执行 target。"""

    def __init__(
        self, target=None, name=None, daemon=None, args=(), kwargs=None,
    ) -> None:
        self._target = target
        self.name = name
        self.daemon = daemon
        self._args = args or ()
        self._kwargs = kwargs or {}
        self.started = False
        self._alive = False
        self.joined: list = []

    def start(self) -> None:
        self.started = True
        self._alive = True
        try:
            if self._target is not None:
                self._target(*self._args, **self._kwargs)
        finally:
            self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout=None) -> None:
        self.joined.append(timeout)
        self._alive = False


class StubThread:
    """不执行 target 的假线程，用于断言 join / 存活分支。"""

    def __init__(self, alive: bool = True, join_keeps_alive: bool = False) -> None:
        self.alive = alive
        self.join_keeps_alive = join_keeps_alive
        self.started = False
        self.joined: list = []
        self.name = "stub"
        self.daemon = True

    def start(self) -> None:
        self.started = True

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout=None) -> None:
        self.joined.append(timeout)
        if not self.join_keeps_alive:
            self.alive = False


# ── 假 Event / Future ──

class FakeEvent:
    def __init__(self, flag: bool = False, wait_result: bool = True) -> None:
        self._flag = flag
        self.wait_result = wait_result
        self.waits: list = []
        self.sets = 0
        self.clears = 0

    def is_set(self) -> bool:
        return self._flag

    def set(self) -> None:
        self._flag = True
        self.sets += 1

    def clear(self) -> None:
        self._flag = False
        self.clears += 1

    def wait(self, timeout=None) -> bool:
        self.waits.append(timeout)
        return self.wait_result


class FakeFuture:
    def __init__(
        self, value: object = None, result_error: BaseException | None = None,
        done: bool = False,
    ) -> None:
        self.value = value
        self.result_error = result_error
        self._done = done
        self.set_results: list = []
        self.set_exceptions: list = []
        self.result_timeouts: list = []

    def set_result(self, value: object) -> None:
        self.set_results.append(value)
        self._done = True

    def set_exception(self, error: BaseException) -> None:
        self.set_exceptions.append(error)
        self._done = True

    def done(self) -> bool:
        return self._done

    def result(self, timeout=None) -> object:
        self.result_timeouts.append(timeout)
        if self.result_error is not None:
            raise self.result_error
        return self.value


# ── 模块级名字替换助手（把 patch 限定到目标模块的全局名字） ──

def fake_zmq(real_zmq, context=None, poller=None) -> SimpleNamespace:
    ns = SimpleNamespace(
        **{k: v for k, v in vars(real_zmq).items() if k.isidentifier()}
    )
    ns.Context = context if context is not None else (lambda: FakeContext())
    ns.Poller = poller if poller is not None else (lambda: FakePoller())
    return ns


def fake_threading(thread_cls) -> SimpleNamespace:
    return SimpleNamespace(
        Thread=thread_cls,
        Event=_threading.Event,
        Lock=_threading.Lock,
        RLock=_threading.RLock,
        current_thread=_threading.current_thread,
    )


def fake_time(*, monotonic=None, wall=None) -> SimpleNamespace:
    return SimpleNamespace(
        monotonic=monotonic if monotonic is not None else (lambda: 0.0),
        time=wall if wall is not None else (lambda: 0.0),
    )


def fake_uuid(hex_value: str = "rid") -> SimpleNamespace:
    return SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=hex_value))
