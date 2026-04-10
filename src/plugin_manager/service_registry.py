"""
插件间服务通讯机制

提供类型安全的服务注册和获取，无需字符串反射，IDE 可完整推断类型。

使用方式：

1. 定义服务接口 (在 shared_types/services_xxx.py):
    @runtime_checkable
    class HistoryService(Protocol):
        def query_records(self, limit: int) -> list[GameRecord]: ...

2. 服务提供者:
    class HistoryPlugin(BasePlugin, HistoryService):
        def query_records(self, limit: int) -> list[GameRecord]:
            return self._db.query(limit)
        
        def on_initialized(self):
            self.register_service(self)  # 注册

3. 服务使用者:
    class StatsPlugin(BasePlugin):
        def _update(self):
            history = self.get_service(HistoryService)
            records = history.query_records(100)  # IDE 完整补全
"""
from __future__ import annotations

import threading
from typing import TypeVar, runtime_checkable, Protocol
from dataclasses import dataclass

import loguru

logger = loguru.logger.bind(name="ServiceRegistry")

_T = TypeVar("_T")


class ServiceNotFoundError(Exception):
    """服务未找到异常"""
    def __init__(self, protocol: type):
        self.protocol = protocol
        super().__init__(f"Service not found: {protocol.__name__}")


class ServiceAlreadyRegisteredError(Exception):
    """服务已注册异常"""
    def __init__(self, protocol: type):
        self.protocol = protocol
        super().__init__(f"Service already registered: {protocol.__name__}")


@dataclass
class ServiceEntry:
    """服务注册条目"""
    protocol: type  # Protocol 类型
    provider: object  # 服务提供者实例
    plugin_name: str  # 提供者插件名


class ServiceRegistry:
    """
    服务注册表（线程安全）
    
    管理插件间服务的注册和获取，支持：
    - 类型安全：通过 Protocol 类型获取服务
    - IDE 友好：返回类型可推断
    - 线程安全：使用 RLock 保护
    
    Usage::
    
        registry = ServiceRegistry()
        
        # 注册服务
        registry.register(HistoryService, history_plugin, "history")
        
        # 获取服务（类型安全）
        history = registry.get(HistoryService)
        records = history.query_records(100)  # IDE 完整补全
    """
    
    def __init__(self):
        self._providers: dict[type, ServiceEntry] = {}
        self._lock = threading.RLock()
    
    def register(
        self,
        protocol: type[_T],
        provider: _T,
        plugin_name: str = "",
    ) -> None:
        """
        注册服务
        
        Args:
            protocol: 服务接口类型（Protocol）
            provider: 服务提供者实例
            plugin_name: 提供者插件名（用于日志）
            
        Raises:
            ServiceAlreadyRegisteredError: 服务已注册
        """
        with self._lock:
            if protocol in self._providers:
                raise ServiceAlreadyRegisteredError(protocol)
            
            self._providers[protocol] = ServiceEntry(
                protocol=protocol,
                provider=provider,
                plugin_name=plugin_name,
            )
            logger.debug(
                f"Service registered: {protocol.__name__} "
                f"(provider: {plugin_name or 'unknown'})"
            )
    
    def unregister(self, protocol: type) -> bool:
        """
        注销服务
        
        Args:
            protocol: 服务接口类型
            
        Returns:
            True 表示成功注销，False 表示服务不存在
        """
        with self._lock:
            if protocol in self._providers:
                entry = self._providers.pop(protocol)
                logger.debug(
                    f"Service unregistered: {protocol.__name__} "
                    f"(provider: {entry.plugin_name})"
                )
                return True
            return False
    
    def get(self, protocol: type[_T]) -> _T:
        """
        获取服务实例（类型安全）
        
        Args:
            protocol: 服务接口类型
            
        Returns:
            服务提供者实例（IDE 可推断类型）
            
        Raises:
            ServiceNotFoundError: 服务未注册
            
        WARNING - 生命周期风险:
            返回的服务实例引用在锁释放后可能被其他线程注销。
            调用方应确保在使用期间服务不会被注销，
            或使用 BasePlugin.get_service_proxy() 获取代理对象。
            
        Usage::
        
            history = registry.get(HistoryService)
            records = history.query_records(100)  # IDE 完整补全
        """
        with self._lock:
            entry = self._providers.get(protocol)
            if entry is None:
                raise ServiceNotFoundError(protocol)
            return entry.provider  # type: ignore[return-value]
    
    def try_get(self, protocol: type[_T]) -> _T | None:
        """
        尝试获取服务实例（不抛异常）
        
        Args:
            protocol: 服务接口类型
            
        Returns:
            服务实例或 None
        """
        with self._lock:
            entry = self._providers.get(protocol)
            if entry is None:
                return None
            return entry.provider  # type: ignore[return-value]
    
    def has(self, protocol: type) -> bool:
        """
        检查服务是否已注册
        
        Args:
            protocol: 服务接口类型
            
        Returns:
            True 表示已注册
        """
        with self._lock:
            return protocol in self._providers
    
    def list_services(self) -> list[tuple[type, str]]:
        """
        列出所有已注册的服务
        
        Returns:
            [(protocol, plugin_name), ...]
        """
        with self._lock:
            return [
                (entry.protocol, entry.plugin_name)
                for entry in self._providers.values()
            ]
    
    def clear(self) -> None:
        """清除所有服务注册"""
        with self._lock:
            self._providers.clear()
            logger.debug("All services unregistered")
    
    def __repr__(self) -> str:
        with self._lock:
            return f"<ServiceRegistry: {len(self._providers)} service(s)>"
