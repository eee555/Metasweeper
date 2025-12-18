import time
from abc import ABC, abstractmethod
import ctypes
import inspect
from pathlib import Path
from msgspec import json
from datetime import datetime, timedelta
from .error import Error
import os
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    TypeVar,
    Generic,
    ParamSpec,
)
from .message import Message, BaseData, MessageMode
from ._data import _BaseData, get_subclass_by_name
from .event import BaseEvent
from .context import BaseContext, PluginContext
from queue import Queue
import zmq
from .mode import PluginStatus
from .config import BaseConfig, BaseSetting


P = ParamSpec("P")
R = TypeVar("R")

# 引入 Windows 多媒体计时器函数
timeBeginPeriod = ctypes.windll.winmm.timeBeginPeriod
timeEndPeriod = ctypes.windll.winmm.timeEndPeriod


class BasePlugin(ABC):
    """
    插件基类
    """

    _context: BaseContext
    _plugin_context: PluginContext = PluginContext()
    _config: BaseConfig

    @abstractmethod
    def build_plugin_context(self) -> None: ...

    @staticmethod
    def event_handler(
        event: Type[BaseEvent],
    ) -> Callable[[Callable[P, BaseEvent]], Callable[P, BaseEvent]]:
        """
        装饰器：标记方法为事件 handler
        """

        def decorator(func: Callable[P, BaseEvent]) -> Callable[P, BaseEvent]:
            func.__event_handler__ = event
            return func

        return decorator

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._event_handlers: Dict[
            Type[BaseEvent], List[Callable[[BasePlugin, BaseEvent], BaseEvent]]
        ] = {}
        event_set: set[str] = set()
        for _, value in cls.__dict__.items():
            if hasattr(value, "__event_handler__"):
                if value.__event_handler__ not in cls._event_handlers:
                    cls._event_handlers[value.__event_handler__] = []
                event_set.add(value.__event_handler__.__name__)
                cls._event_handlers[value.__event_handler__].append(value)
        cls._plugin_context.subscribers = list(event_set)
        cls._plugin_context.pid = os.getpid()

    def __init__(self) -> None:
        super().__init__()
        context = zmq.Context(5)
        self.dealer = context.socket(zmq.DEALER)
        self.__message_queue: Queue[Message] = Queue()
        self.__heartbeat_time = datetime.now()
        self._is_running: bool = False
        self.build_plugin_context()

    @abstractmethod
    def initialize(self) -> None:
        self.init_config(self._config)

    @abstractmethod
    def shutdown(self) -> None:
        self._plugin_context.status = PluginStatus.Stopped
        self.refresh_context()

    def run(self, host: str, port: int) -> None:
        self.dealer.setsockopt_string(
            zmq.IDENTITY, str(self._plugin_context.pid))
        self.dealer.connect(f"tcp://{host}:{port}")
        self._is_running = True
        self._plugin_context.status = PluginStatus.Running
        self.refresh_context()
        poller = zmq.Poller()
        poller.register(self.dealer, zmq.POLLIN)
        timeBeginPeriod(1)
        while self._is_running:
            # 轮询是否有数据，超时 1ms
            events = dict(poller.poll(timeout=0))

            # ---- 接收消息 -----------------------------------------------------
            if self.dealer in events:
                data = self.dealer.recv()
                message = json.decode(data, type=Message)
                self.__message_dispatching(message)

            # ---- 发送消息 -----------------------------------------------------
            if not self.__message_queue.empty():
                msg = self.__message_queue.get()
                self.dealer.send(json.encode(msg))

            # ---- 心跳检查 -----------------------------------------------------
            if datetime.now() - self.__heartbeat_time > timedelta(seconds=10):
                break

            time.sleep(0.001)

        # ---------------------------------------------------------------------
        timeEndPeriod(1)
        self.shutdown()
        self.dealer.close()

    # -------------------------------------------------------------------------

    def __message_dispatching(self, message: Message) -> None:
        """
        消息分发
        """
        message.Source = self.__class__.__name__
        self.__heartbeat_time = datetime.now()

        if message.mode == MessageMode.Event:
            if isinstance(message.data, BaseEvent) and message.data is not None:
                if message.data.__class__ not in self._event_handlers:
                    self.send_error(
                        type="Event Subscribe",
                        error=f"{self.__class__.__name__} not Subscribe {message.data.__class__.__name__}",
                    )
                    return
                for handler in self._event_handlers[message.data.__class__]:
                    event = handler(self, message.data)
                    message.data = event
                    self.__message_queue.put(message)
            else:
                self.send_error(
                    type="Event Validation",
                    error=f"{message.data} is not a valid event",
                )
        elif message.mode == MessageMode.Context:
            if isinstance(message.data, BaseContext) and message.data is not None:
                if hasattr(self, "_context"):
                    self._context = message.data
                    self.initialize()
                self._context = message.class_name
        elif message.mode == MessageMode.Error:
            pass
        elif message.mode == MessageMode.Unknown:
            pass
        elif message.mode == MessageMode.Heartbeat:
            self.__message_queue.put(message)

    def refresh_context(self):
        self._plugin_context.heartbeat = datetime.now().timestamp()
        self.__message_queue.put(
            Message(
                data=self._plugin_context,
                mode=MessageMode.Context,
                Source=self.__class__.__name__,
                class_name=self._plugin_context.__class__.__name__,
            )
        )

    @property
    def context(self):
        return self._context

    def send_error(self, type: str, error: str):
        self.__message_queue.put(
            Message(
                data=Error(type=type, message=error),
                mode=MessageMode.Error,
                Source=self.__class__.__name__,
            )
        )

    def init_config(self, config: BaseConfig):
        self._config = config
        old_config = self.config
        config_path = self.context.plugin_dir + \
            f'/{self.__class__.__name__}/{self.__class__.__name__}.json'
        if old_config is None:
            with open(config_path, "w", encoding="utf-8") as f:
                b = json.encode(config)
                f.write(b.decode("utf-8"))

    @property
    def config(self):
        config_path = self.context.plugin_dir + \
            f'/{self.__class__.__name__}/{self.__class__.__name__}.json'
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.decode(f.read(), type=self._config.__class__)
                    return config
            except:
                return None

    @property
    def path(self) -> Path:
        if hasattr(self, "_context"):
            return Path(self._context.plugin_dir) / self.__class__.__name__
        return Path(os.path.dirname(os.path.abspath(__file__)))

    def stop(self):
        self._is_running = False
