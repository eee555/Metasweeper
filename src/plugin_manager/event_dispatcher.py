"""
事件分发器

负责将事件分发给订阅了该事件的插件
- 非阻塞：dispatch() 将事件投递到各插件的独立队列后立即返回
- 每个插件在自己的线程中串行消费事件（由 BasePlugin.run() 负责）
- 支持优先级排序和异常隔离
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import loguru

from .service_registry import ServiceRegistry

if TYPE_CHECKING:
    from .plugin_base import BasePlugin

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
    - 背压控制：队列满时丢弃事件并记录警告
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
                # 投递到插件队列（非阻塞）
                success = entry.plugin._enqueue_event(entry.handler, event)
                if not success:
                    logger.warning(
                        f"Dropped event '{event_type}' for plugin "
                        f"'{entry.plugin.name}' (queue full)"
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
