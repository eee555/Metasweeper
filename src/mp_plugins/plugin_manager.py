import asyncio
import ctypes
from datetime import datetime, timedelta
import sys
import threading
from typing import Callable, Dict, List, Optional, TypeVar, Generic, Sequence
from threading import RLock
import zmq
from queue import Queue
import time
import msgspec
import pathlib
import json

from .base import (
    PluginContext,
    BaseContext,
    BaseEvent,
    MessageMode,
    Message,
    Error,
    PluginStatus,
)
from .plugin_process import PluginProcess
from .base.config import BaseConfig, BaseSetting, Get_settings


_Event = TypeVar("_Event", bound=BaseEvent)

# 引入 Windows 多媒体计时器函数
timeBeginPeriod = ctypes.windll.winmm.timeBeginPeriod
timeEndPeriod = ctypes.windll.winmm.timeEndPeriod


class PluginManager(object):

    __instance: Optional["PluginManager"] = None
    __lock = RLock()

    def __init__(self) -> None:
        context = zmq.Context(3)

        self.__router = context.socket(zmq.ROUTER)
        self.__poller = zmq.Poller()
        self.__poller.register(self.__router, zmq.POLLIN)

        self.__port = self.__router.bind_to_random_port("tcp://*")

        self.__plugins_context: Dict[str, PluginContext] = {}
        self.__plugins_process: Dict[str, PluginProcess] = {}
        self.__plugins_config_path: Dict[str, pathlib.Path] = {}

        self.__event_dict: Dict[str, List[BaseEvent]] = {}
        self.__message_queue: Queue[Message] = Queue()

        self.__error_callback = None

        self.__running = False
        self.__context: BaseContext = None

    # -------------------------
    # 单例
    # -------------------------
    @classmethod
    def instance(cls) -> "PluginManager":
        if cls.__instance is None:
            with cls.__lock:
                if cls.__instance is None:
                    cls.__instance = cls()
        return cls.__instance

    # -------------------------
    # 公开属性
    # -------------------------
    @property
    def port(self):
        return self.__port

    @property
    def context(self) -> BaseContext:
        return self.__context

    @context.setter
    def context(self, context: BaseContext):
        self.__context = context

    @property
    def plugin_contexts(self):
        for context in self.__plugins_context.values():
            yield context.copy()

    # -------------------------
    # 启动 / 停止
    # -------------------------
    def start(self, plugin_dir: pathlib.Path, env: Dict[str, str]):
        timeBeginPeriod(1)
        if self.__running:
            return

        self.__running = True

        plugin_dir.mkdir(parents=True, exist_ok=True)
        self._load_plugins(plugin_dir, env)

        # 后台线程执行单线程循环
        self.__loop_thread = threading.Thread(
            target=self.run_loop, daemon=True)
        self.__loop_thread.start()

        print("Plugin manager started (non-blocking)")

    def stop(self):
        timeEndPeriod(1)
        self.__running = False
        if hasattr(self, "__loop_thread"):
            self.__loop_thread.join(2)
        for process in self.__plugins_process.values():
            process.stop()
        print("Plugin manager stopped")

    # -------------------------
    # 加载插件（保持原逻辑）
    # -------------------------
    def _load_plugins(self, plugin_dir, env):
        for plugin_path in plugin_dir.iterdir():
            if plugin_path.is_dir():
                if plugin_path.name.startswith("__"):
                    continue

                self.__plugins_config_path[plugin_path.name] = plugin_path / (
                    plugin_path.name + ".json"
                )

                # exe 优先
                if (plugin_path / (plugin_path.name + ".exe")).exists():
                    path = plugin_path / (plugin_path.name + ".exe")
                else:
                    path = plugin_path / (plugin_path.name + ".py")

                process = PluginProcess(path)
                process.start("localhost", self.__port, env=env)

                self.__plugins_process[str(process.pid)] = process

    # -------------------------
    # 单线程事件循环（核心）
    # -------------------------
    def run_loop(self):
        heartbeat_timer = time.time()

        while self.__running:

            # 1. 收消息
            events = dict(self.__poller.poll(0))
            if self.__router in events:
                identity, data = self.__router.recv_multipart()
                self._handle_incoming(identity, data)

            # 2. 发消息
            if not self.__message_queue.empty():
                message = self.__message_queue.get()
                self._send_message_internal(message)

            # 3. 心跳
            now = time.time()
            if now - heartbeat_timer > 5:
                self._send_heartbeat()
                heartbeat_timer = now
            time.sleep(0.001)

    # -------------------------
    # 消息解包逻辑
    # -------------------------
    def _handle_incoming(self, identity, data):
        pid = identity.decode()

        if pid in self.__plugins_context:
            self.__plugins_context[pid].heartbeat = time.time()

        message = msgspec.json.decode(data, type=Message)

        # Event
        if message.mode == MessageMode.Event:
            if message.id in self.__event_dict and isinstance(message.data, BaseEvent):
                self.__event_dict[message.id].append(message.data)

        # Error
        elif message.mode == MessageMode.Error:
            if self.__error_callback and isinstance(message.data, Error):
                self.__error_callback(message.data)

        # 初次 Context
        elif message.mode == MessageMode.Context:
            if isinstance(message.data, PluginContext):
                self.__plugins_context[pid] = message.data
                # 把主 Context 返回插件
                self.__send_message(
                    Message(
                        data=self.context,
                        mode=MessageMode.Context,
                        class_name=self.context.__class__.__name__,
                    )
                )

    # -------------------------
    # 事件发射
    # -------------------------
    def send_event(
        self, event: _Event, timeout: int = 10, response_count: int = 1
    ) -> Sequence[_Event]:

        message = Message(
            data=event,
            mode=MessageMode.Event,
            class_name=event.__class__.__name__,
        )

        self.__event_dict[message.id] = []

        self.__send_message(message)

        expire = datetime.now() + timedelta(seconds=timeout)

        while datetime.now() < expire and (
            len(self.__event_dict.get(message.id, [])) < response_count
        ):
            time.sleep(0.0001)

        result = self.__event_dict.get(message.id, [])
        if message.id in self.__event_dict:
            del self.__event_dict[message.id]

        return result

    # -------------------------
    # 发消息入口（入队）
    # -------------------------
    def __send_message(self, message: Message):
        self.__message_queue.put(message)

    # -------------------------
    # 发消息逻辑（内部）
    # -------------------------
    def _send_message_internal(self, message: Message):
        if message.mode in (
            MessageMode.Event,
            MessageMode.Context,
            MessageMode.Heartbeat,
        ):
            for ctx in self.__plugins_context.values():
                if ctx.status == PluginStatus.Running:
                    if message.mode == MessageMode.Event:
                        if message.class_name not in ctx.subscribers:
                            continue
                    self.__router.send_multipart(
                        [
                            str(ctx.pid).encode(),
                            msgspec.json.encode(message),
                        ]
                    )

    # -------------------------
    # 心跳
    # -------------------------
    def _send_heartbeat(self):
        msg = Message(mode=MessageMode.Heartbeat)
        for ctx in self.__plugins_context.values():
            if ctx.status == PluginStatus.Running:
                self.__router.send_multipart(
                    [str(ctx.pid).encode(), msgspec.json.encode(msg)]
                )

    # -------------------------
    # 错误回调
    # -------------------------
    def bind_error(self, func: Callable[[Error], None]):
        self.__error_callback = func

    # -------------------------
    # 配置操作（原样）
    # -------------------------
    def Get_Settings(self, plugin_name: str):
        if plugin_name not in self.__plugins_config_path:
            return {}
        if not self.__plugins_config_path[plugin_name].exists():
            return {}

        data = json.loads(
            self.__plugins_config_path[plugin_name].read_text("utf-8"))
        return Get_settings(data)

    def Set_Settings(self, plugin_name: str, name: str, setting: BaseSetting):
        data = self.Get_Settings(plugin_name)

        new_data = {}
        data[name] = setting
        for key, value in data.items():
            if isinstance(value, BaseSetting):
                new_data[key] = msgspec.structs.asdict(value)

        self.__plugins_config_path[plugin_name].write_text(
            json.dumps(new_data, indent=4)
        )

    # -------------------------
    # 查找插件 Context
    # -------------------------
    def Get_Context_By_Name(self, plugin_name: str) -> Optional[PluginContext]:
        for ctx in self.__plugins_context.values():
            if ctx.name == plugin_name:
                return ctx.copy()
        return None

    def Get_Plugin_Names(self) -> List[str]:
        return [ctx.name for ctx in self.__plugins_context.values()]
