from datetime import datetime, timedelta
import sys
import threading
from typing import Callable, Dict, List, Optional, TypeVar, Generic, Sequence
from threading import RLock
from .base import (
    PluginContext,
    BaseContext,
    BaseEvent,
    MessageMode,
    Message,
    Error,
    PluginStatus,
)
import zmq
from .base._data import _BaseData
from queue import Queue
import time
import msgspec
from .plugin_process import PluginProcess
from .base.config import BaseConfig, BaseSetting, Get_settings
import pathlib
import json

_Event = TypeVar("_Event", bound=BaseEvent)


class PluginManager(object):

    __instance: Optional["PluginManager"] = None
    __lock = RLock()
    __plugins_context: Dict[str, PluginContext] = {}
    __plugins_process: Dict[str, PluginProcess] = {}
    __plugins_config_path: Dict[str, pathlib.Path] = {}
    __context: BaseContext
    __event_dict: Dict[str, List[BaseEvent]] = {}
    __message_queue: Queue[Message] = Queue()
    __running: bool = False

    def __init__(self) -> None:
        context = zmq.Context()

        self.__router = context.socket(zmq.ROUTER)
        self.__port = self.__router.bind_to_random_port("tcp://127.0.0.1")
        self.__error_callback = None

    @property
    def port(self):
        return self.__port

    @classmethod
    def instance(cls) -> "PluginManager":
        if cls.__instance is None:
            with cls.__lock:
                if cls.__instance is None:
                    cls.__instance = cls()
        return cls.__instance

    def start(self, plugin_dir: pathlib.Path, env: Dict[str, str]):
        with self.__lock:
            if self.__running:
                return
            self.__running = True
        plugin_dir.mkdir(parents=True, exist_ok=True)
        for plugin_path in plugin_dir.iterdir():
            if plugin_path.is_dir():
                if plugin_path.name.startswith("__"):
                    continue
                self.__plugins_config_path[plugin_path.name] = plugin_path / (
                    plugin_path.name + ".json"
                )
                # 先判断是否有exe
                if (plugin_path / (plugin_path.name + ".exe")).exists():
                    plugin_path = plugin_path / (plugin_path.name + ".exe")
                else:
                    plugin_path = plugin_path / (plugin_path.name + ".py")
                process = PluginProcess(plugin_path)
                process.start("127.0.0.1", self.__port, env=env)
                self.__plugins_process[str(process.pid)] = process

        t = threading.Thread(target=self.__message_dispatching, daemon=True)
        self.__request_thread = t
        t2 = threading.Thread(target=self.__async_send_message, daemon=True)
        self.__response_thread = t2
        t3 = threading.Thread(target=self.__send_heartbeat, daemon=True)
        self.__heartbeat_thread = t3
        t3.start()
        t.start()
        t2.start()
        print("Plugin manager started")

    def stop(self):
        with self.__lock:
            if not self.__running:
                return
            self.__running = False
        for process in self.__plugins_process.values():
            process.stop()
        self.__request_thread.join(10)
        self.__response_thread.join(10)
        self.__heartbeat_thread.join(10)
        self.__router.close()
        print("Plugin manager stopped")

    @property
    def plugin_contexts(self):
        for context in self.__plugins_context.values():
            yield context.copy()

    @property
    def context(self) -> BaseContext:
        return self.__context

    @context.setter
    def context(self, context: BaseContext):
        self.__context = context

    def send_event(
        self, event: _Event, timeout: int = 10, response_count: int = 1
    ) -> Sequence[_Event]:
        message = Message(
            data=event, mode=MessageMode.Event, class_name=event.__class__.__name__
        )
        self.__event_dict[message.id] = []
        self.__send_message(message)
        current_time = datetime.now()
        while datetime.now() - current_time < timedelta(seconds=timeout) and (
            len(self.__event_dict.get(message.id, [])) < response_count
        ):
            time.sleep(0.1)
        result = []
        if message.id in self.__event_dict:
            for response in self.__event_dict[message.id]:
                result.append(response)
        with self.__lock:
            del self.__event_dict[message.id]
        return result

    def __send_heartbeat(self):
        while self.__running:
            time.sleep(5)
            for context in self.__plugins_context.values():
                if datetime.now().timestamp() - context.heartbeat > 3000:
                    context.status = PluginStatus.Dead
                if context.status == PluginStatus.Running:
                    self.__send_message(Message(mode=MessageMode.Heartbeat))

    def __send_message(self, message: Message):
        self.__message_queue.put(message)

    def bind_error(self, func: Callable[[Error], None]):
        self.__error_callback = func

    def __message_dispatching(self) -> None:
        while self.__running:
            time.sleep(0.1)
            try:
                identity, _, data = self.__router.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                continue
            if not data:
                continue
            if identity.decode() in self.__plugins_context:
                self.__plugins_context[identity.decode()].heartbeat = (
                    datetime.now().timestamp()
                )
            message = msgspec.json.decode(data, type=Message)
            if message.mode == MessageMode.Event:
                with self.__lock:
                    if message.id in self.__event_dict and isinstance(
                        message.data, BaseEvent
                    ):
                        self.__event_dict[message.id].append(message.data)
            elif message.mode == MessageMode.Error:
                if self.__error_callback is not None and isinstance(
                    message.data, Error
                ):
                    self.__error_callback(message.data)
            elif message.mode == MessageMode.Heartbeat:
                pass
            elif message.mode == MessageMode.Context:
                if isinstance(message.data, PluginContext):
                    with self.__lock:
                        self.__plugins_context[identity.decode()] = message.data
                        self.__send_message(
                            Message(
                                data=self.context,
                                mode=MessageMode.Context,
                                class_name=self.context.__class__.__name__,
                            )
                        )

    def __async_send_message(self):
        while self.__running:
            time.sleep(0.1)
            if self.__message_queue.empty():
                continue
            message = self.__message_queue.get()
            if message.mode == MessageMode.Event:
                for context in self.__plugins_context.values():
                    event_name = message.data.__class__.__name__
                    if (
                        event_name in context.subscribers
                        and context.status == PluginStatus.Running
                    ):
                        self.__router.send_multipart(
                            [
                                str(context.pid).encode(),
                                b"",
                                msgspec.json.encode(message),
                            ]
                        )
            elif message.mode == MessageMode.Heartbeat:
                for context in self.__plugins_context.values():
                    if context.status == PluginStatus.Running:
                        self.__router.send_multipart(
                            [
                                str(context.pid).encode(),
                                b"",
                                msgspec.json.encode(message),
                            ]
                        )
            elif message.mode == MessageMode.Context:
                for context in self.__plugins_context.values():
                    if context.status == PluginStatus.Running:
                        self.__router.send_multipart(
                            [
                                str(context.pid).encode(),
                                b"",
                                msgspec.json.encode(message),
                            ]
                        )

    def Get_Settings(self, plugin_name: str):
        if plugin_name not in self.__plugins_config_path:
            return {}
        if not self.__plugins_config_path[plugin_name].exists():
            return {}

        data = json.loads(self.__plugins_config_path[plugin_name].read_text("utf-8"))

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
