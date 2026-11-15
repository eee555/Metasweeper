"""
事件分发器

负责将事件分发给订阅了该事件的插件
- 非阻塞：dispatch() 将事件投递到各插件的独立队列后立即返回
- 每个插件在自己的线程中串行消费事件（由 BasePlugin.run() 负责）
- 支持优先级排序和异常隔离

真实投递语义（#27）：插件队列是无界 Qt QueuedConnection，投递本身不会
因「队列满」返回 False。`_enqueue_event` 返回 False 只表示插件正在关闭或
已停止（生命周期拒绝），不是有界队列背压。跨进程 PUB/SUB 的水位丢弃由
ZMQ 的 SNDHWM/RCVHWM 处理（见 zmq_server/zmq_client）。此处不做丢包计数，
以免改动事件协议。
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import loguru

from plugin_sdk.service_registry import ServiceRegistry

if TYPE_CHECKING:
    from plugin_sdk.plugin_base import BasePlugin

logger = loguru.logger.bind(name="EventDispatcher")


@dataclass
class HandlerEntry:
    """事件处理函数条目"""
    handler: Callable[[Any], None]
    priority: int
    plugin: BasePlugin | None = None


class EventDispatcher:
    """
    事件分发器（非阻塞投递模式）
    
    功能：
    - 管理事件订阅
    - 按优先级分发事件
    - dispatch() 不阻塞：将事件投递到各插件的队列，立即返回
    - 异常隔离通过各插件线程自行处理
    - 投递拒绝：仅当插件正在关闭/已停止时 _enqueue_event 返回 False；
      插件内队列无界，不做「队列满丢弃」，ZMQ PUB/SUB 侧由 HWM 约束
    - 服务注册：管理插件间服务通讯
    """
    
    def __init__(self):
        self._handlers: dict[str, list[HandlerEntry]] = defaultdict(list)
        self._lock = threading.RLock()
        # 服务注册表（用于插件间通讯）
        self._service_registry = ServiceRegistry()
    
    @property
    def services(self) -> ServiceRegistry:
        """
        获取服务注册表
        
        用法::
        
            # 注册服务
            dispatcher.services.register(HistoryService, provider, "history")
            
            # 获取服务
            history = dispatcher.services.get(HistoryService)
        """
        return self._service_registry
    
    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Any], None],
        priority: int = 100,
        plugin: BasePlugin | None = None,
    ) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型名称
            handler: 事件处理函数
            priority: 优先级（数值越小越先执行）
            plugin: 所属插件（用于取消订阅和队列投递）
        """
        with self._lock:
            entry = HandlerEntry(
                handler=handler,
                priority=priority,
                plugin=plugin,
            )
            self._handlers[event_type].append(entry)
            # 按优先级排序
            self._handlers[event_type].sort(key=lambda e: e.priority)
            logger.debug(
                f"Subscribed to '{event_type}' with priority {priority}"
            )
    
    def unsubscribe(self, event_type: str, plugin: BasePlugin) -> None:
        """
        取消插件对某事件的所有订阅
        
        Args:
            event_type: 事件类型名称
            plugin: 要取消订阅的插件
        """
        with self._lock:
            handlers = self._handlers.get(event_type)
            if handlers:
                self._handlers[event_type] = [
                    entry for entry in handlers
                    if entry.plugin != plugin
                ]
                logger.debug(f"Unsubscribed plugin '{plugin.name}' from '{event_type}'")
    
    def unsubscribe_all(self, plugin: BasePlugin) -> None:
        """
        取消插件的所有事件订阅
        
        Args:
            plugin: 要取消订阅的插件
        """
        with self._lock:
            for event_type in list(self._handlers.keys()):
                self._handlers[event_type] = [
                    entry for entry in self._handlers[event_type]
                    if entry.plugin != plugin
                ]
    
    def dispatch(self, event_type: str, event: Any) -> None:
        """
        非阻塞分发事件：将事件投递到各插件的独立队列，立即返回
        
        Args:
            event_type: 事件类型名称
            event: 事件数据
        """
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        
        if not handlers:
            logger.debug(f"No handlers for event '{event_type}'")
            return
        
        logger.debug(
            f"Dispatching '{event_type}' to {len(handlers)} handler(s)"
        )
        
        for entry in handlers:
            # 检查插件是否启用
            if entry.plugin and not entry.plugin.is_enabled:
                continue
            
            if entry.plugin is not None:
                # 投递到插件队列（非阻塞）。_enqueue_event 返回 False 只代表
                # 插件已停止/正在关闭（生命周期拒绝），并非有界队列「满」；
                # 事件不会被本层主动丢弃计数，保留警告以便排障（#27）。
                success = entry.plugin._enqueue_event(entry.handler, event)
                if not success:
                    logger.warning(
                        f"Rejected event '{event_type}' for plugin "
                        f"'{entry.plugin.name}' (queue full / plugin stopping)"
                    )
            else:
                # 无归属插件的 handler（兜底），在调用者线程同步执行
                try:
                    entry.handler(event)
                except Exception as e:
                    logger.error(
                        f"Handler error (no-plugin) for event "
                        f"'{event_type}': {e}",
                        exc_info=True,
                    )

    def get_handlers(self, event_type: str) -> list[HandlerEntry]:
        """获取某事件的所有处理函数"""
        with self._lock:
            return list(self._handlers.get(event_type, []))
    
    def clear(self) -> None:
        """清除所有订阅"""
        with self._lock:
            self._handlers.clear()
    
    def __repr__(self) -> str:
        total = sum(len(handlers) for handlers in self._handlers.values())
        return f"<EventDispatcher: {len(self._handlers)} event types, {total} handlers>"
