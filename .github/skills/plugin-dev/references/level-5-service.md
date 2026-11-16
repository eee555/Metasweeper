# Level 5: 服务系统

## 什么是服务系统？

服务系统允许插件之间进行类型安全的方法调用。服务方法在**服务提供者线程**执行，调用方无需关心线程安全。

## 定义服务接口

在 `plugins/services/` 目录下创建接口定义文件：

```python
# plugins/services/my_service.py
from typing import Protocol, runtime_checkable
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class MyData:
    """数据类型（frozen 保证不可变，线程安全）"""
    id: int
    name: str

@runtime_checkable
class MyService(Protocol):
    """服务接口定义"""
    def get_data(self, id: int) -> MyData | None: ...
    def list_data(self, limit: int = 100) -> list[MyData]: ...
```

## 注册服务（服务提供者）

```python
from plugins.services.my_service import MyService

class ProviderPlugin(BasePlugin):
    
    def on_initialized(self):
        # 注册服务，显式指定 Protocol 类型
        self.register_service(self, protocol=MyService)
        self.logger.info("MyService 已注册")
    
    # 实现服务接口方法
    def get_data(self, id: int) -> MyData | None:
        return self._db.query(id)
    
    def list_data(self, limit: int = 100) -> list[MyData]:
        return self._db.query_all(limit)
```

## 使用服务（服务消费者）

### 方式一：等待服务就绪（推荐）

```python
from plugins.services.my_service import MyService

class ConsumerPlugin(BasePlugin):
    
    def on_initialized(self):
        # 等待服务就绪，最多 10 秒
        self._service = self.wait_for_service(MyService, timeout=10.0)
        if self._service is None:
            self.logger.warning("MyService 未就绪")
    
    def _do_something(self):
        if self._service:
            # 调用服务方法（在提供者线程执行）
            data = self._service.get_data(123)
            all_data = self._service.list_data(100)
```

### 方式二：检查服务可用

```python
def on_initialized(self):
    if self.has_service(MyService):
        self._service = self.get_service_proxy(MyService)

def _do_something(self):
    if self._service:
        data = self._service.get_data(123)
```

## 异步调用

```python
def _async_call(self):
    # 异步调用，返回 Future
    future = self.call_service_async(MyService, "get_data", 123)
    
    # 做其他事情...
    
    # 阻塞等待结果
    result = future.result(timeout=5.0)
```

## 服务相关 API

| 方法 | 说明 |
|------|------|
| `register_service(self, protocol=ServiceClass)` | 注册服务 |
| `has_service(ServiceClass)` | 检查服务是否可用 |
| `wait_for_service(ServiceClass, timeout)` | 等待服务就绪并获取代理（推荐） |
| `get_service_proxy(ServiceClass)` | 获取服务代理对象 |
| `call_service_async(ServiceClass, "method", *args)` | 异步调用，返回 Future |

## 注意事项

1. **死锁风险**：不要让两个插件互相调用对方的服务
2. **线程安全**：服务方法在提供者线程执行，调用方无需关心
3. **删除接口**：不要在服务接口中暴露删除等敏感操作
4. **超时处理**：服务调用默认超时 10 秒，可配置
